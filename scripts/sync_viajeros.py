#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_viajeros.py — publica en Firebase los viajeros en casa con sus dietas,
alergias y restricciones, agrupados por habitación. Alimenta el módulo
"Viajeros" del ATA Handbook (el reemplazo digital del corcho de tarjetas).

Fuentes reales (fase 2): PGO, un portal web. El script inicia sesión con
Playwright y lee las tablas HTML de los reportes del día:
  · Reporte "Dietas"      → hab, nombre, edad, nac, grupo, observaciones
  · "Reporte Geos" diario → hab, viajero, nac, IN/OUT, edad, excursión, grupo
  Ver la sección "Fase 2 · PGO" abajo. El resto del pipeline
  (cruce → normalización → doc Firebase) es el mismo que el seed.

Fase 1 (actual): SEED_ROWS — transcripción manual de los reportes REALES del
día (2026-07-29). El roster completo (hab, nombre, edad, nac, grupo, IN/OUT)
sale del "Reporte Geos" del 29-07; las observaciones de dieta/alergia se cruzan
por nombre desde el reporte "Dietas" del mismo día y se pegan verbatim sobre el
viajero que corresponde. Mientras no llegue el link del Excel (fase 2), este
bloque se reemplaza a mano con el reporte de cada día. 48 habs · 101 viajeros.

Escribe UN solo doc (sobrescrito por cada sync, como staffing):

  viajeros/current = {
    date: "YYYY-MM-DD",            ← fecha del reporte
    updatedAt: <ms epoch>,
    source: "seed" | "excel",
    habs: { "01": [ { id, nombre, edad, nac, grupo,
                      in: "YYYY-MM-DD", out: "YYYY-MM-DD",
                      tags: ["alergia-mariscos", ...],   ← taxonomía canónica
                      obs: "texto original del reporte",
                      foto: <url|ausente> }, ... ], ... }
  }

Taxonomía canónica de tags (compartida con la app — ver VJ_TAGS en index.html):
  alergia-{mariscos,gluten,lactosa,sesamo,pescado,ajo,frutos-secos,frutillas,pina,
           cilantro,quinoa,trufa,champinones,pollo}
  dieta-{vegetariana,vegana,pescetariana,sin-gluten,sin-lactosa,sin-cerdo,
         sin-carnes-rojas,sin-cordero,sin-mariscos,sin-pescado,sin-fritura,
         sin-azucar}
  cond-{diabetico,embarazada}
"niño" no es tag: la app lo deriva de edad ≤ 12.

Secrets requeridos solo para escribir (GitHub → Settings → Secrets → Actions):
  FIREBASE_KEY → contenido completo del JSON de la service account

Modos:
  python scripts/sync_viajeros.py --seed                 → escribe el seed en Firebase
  python scripts/sync_viajeros.py --from-pgo [--date D]  → login en PGO + reportes del día y escribe (fase 2)
  python scripts/sync_viajeros.py --debug                → imprime resumen, no escribe
  python scripts/sync_viajeros.py --emit-json out.json   → dump del doc (dev local)
  python scripts/sync_viajeros.py --explore --introspect         → lista las queries GraphQL del backend de PGO
  python scripts/sync_viajeros.py --explore                     → perfila los reportes NUEVOS (arrival/birthday/comedor) sin escribir nada
  python scripts/sync_viajeros.py --explore arrival             → sólo uno (o "arrival,comedor")
  python scripts/sync_viajeros.py --from-pgo --dump-html --debug → guarda el HTML de PGO para ajustar selectores
  python scripts/sync_viajeros.py --from-pgo --trace-net --debug → lista las llamadas XHR de la SPA (descubrir API)
  (combinables: --from-pgo --debug lee PGO y muestra el resumen sin tocar Firebase;
   --date YYYY-MM-DD elige la fecha del reporte, por defecto hoy)
"""

import json, os, re, sys, datetime, unicodedata

DB_URL = "https://explora-cafe-orders-default-rtdb.firebaseio.com"

REPORT_DATE = "2026-07-29"   # fecha nominal del seed (día del Reporte Geos)


# ── Roster real del día ───────────────────────────────────────────────────────
# (hab, nombre, edad, nac, grupo, in, out, observación textual del reporte)
# Roster (hab/nombre/edad/nac/grupo/IN-OUT) desde el "Reporte Geos" 29-07-2026;
# las observaciones se cruzan por nombre desde el reporte "Dietas" del mismo día
# y se pegan verbatim (mayúsculas y mezcla ES/EN tal como llegan) para que la
# normalización obs_to_tags() trabaje sobre el texto original. Los viajeros sin
# fila en Dietas quedan con obs "" (sin restricción alimentaria informada).

SEED_ROWS = [
    ('02', 'Maia Nusynkier', 10, 'ARGE', 'NUSYNKIER', '2026-07-26', '2026-08-01', ''),
    ('02', 'Tobias Nusynkier', 8, 'ARGE', 'NUSYNKIER', '2026-07-26', '2026-08-01', ''),
    ('03', 'Mariela Colorado', 48, 'ARGE', 'NUSYNKIER', '2026-07-26', '2026-08-01', ''),
    ('03', 'Hernan Nusynkier', 48, 'ARGE', 'NUSYNKIER', '2026-07-26', '2026-08-01', ''),
    ('04', 'Veronica Maranhao Machado Guimaraes', 59, 'BRAZ', 'MACHADO', '2026-07-26', '2026-08-01', ''),
    ('04', 'Rafaela Machado Borges De Miranda', 26, 'BRAZ', 'MACHADO', '2026-07-26', '2026-08-01', ''),
    ('05', 'Nilson Candido De Oliveira Faria', 76, 'BRAZ', 'FURLAN', '2026-07-25', '2026-07-31', ''),
    ('05', 'Lucila Maria Furlan', 72, 'BRAZ', 'FURLAN', '2026-07-25', '2026-07-31', ''),
    ('06', 'Jose Roldao De Almeida Souza', 78, 'BRAZ', 'FURLAN', '2026-07-25', '2026-07-31', ''),
    ('06', 'Diva Helena Furlan', 77, 'BRAZ', 'FURLAN', '2026-07-25', '2026-07-31', ''),
    ('07', 'Joao Lobo Hadad Bastos', 16, 'BRAZ', 'PEREIRA', '2026-07-25', '2026-07-30', ''),
    ('07', 'Renata Pereira Lobo E Silva', 48, 'BRAZ', 'PEREIRA', '2026-07-25', '2026-07-30', ''),
    ('08', 'Marcos Vinicius Santana Dias', 50, 'BRAZ', 'TAVARES', '2026-07-26', '2026-07-31', ''),
    ('08', 'Karina Rachel Tavares Santos', 47, 'BRAZ', 'TAVARES', '2026-07-26', '2026-07-31', ''),
    ('09', 'Leonardo Tavares Santos Dias', 14, 'BRAZ', 'TAVARES', '2026-07-26', '2026-07-31', ''),
    ('09', 'Manuela Tavares Santos Dias', 15, 'BRAZ', 'TAVARES', '2026-07-26', '2026-07-31', ''),
    ('10', 'Robert Shoiti Seichi', 57, 'BRAZ', 'FURLAN', '2026-07-25', '2026-07-30', ''),
    ('10', 'Leila Maria Furlan', 70, 'BRAZ', 'FURLAN', '2026-07-25', '2026-07-30', ''),
    ('11', 'Daniella Posselt Furlan', 9, 'BRAZ', 'FURLAN', '2026-07-25', '2026-07-31', ''),
    ('11', 'Rafaella Furlan Villares', 12, 'BRAZ', 'FURLAN', '2026-07-25', '2026-07-31', ''),
    ('11', 'Isabella Furlan Villares', 15, 'BRAZ', 'FURLAN', '2026-07-25', '2026-07-31', ''),
    ('12', 'Gabriella Furlan Villares', 53, 'BRAZ', 'FURLAN', '2026-07-25', '2026-07-31', ''),
    ('12', 'Caio Weil Villares', 54, 'BRAZ', 'FURLAN', '2026-07-25', '2026-07-31', ''),
    ('13', 'Elisangela Marcondes Dos Santos Fusaro', 46, 'BRAZ', 'MARCONDES', '2026-07-27', '2026-07-30', ''),
    ('13', 'Eduardo Fusaro', 44, 'BRAZ', 'MARCONDES', '2026-07-27', '2026-07-30', ''),
    ('13', 'Mariana Marcondes Fusaro', 11, 'BRAZ', 'MARCONDES', '2026-07-27', '2026-07-30', ''),
    ('14', 'Alice Marcondes Fusaro', 16, 'BRAZ', 'MARCONDES', '2026-07-27', '2026-07-30', ''),
    ('14', 'Maria Eduarda Marcondes Fusaro', 19, 'BRAZ', 'MARCONDES', '2026-07-27', '2026-07-30', ''),
    ('15', 'Luc Brentener', 54, 'LUXE', 'BRENTENER', '2026-07-26', '2026-07-29', ''),
    ('15', 'Tessy Weber', 50, 'LUXE', 'BRENTENER', '2026-07-26', '2026-07-29', ''),
    ('16', 'Joao Santos Almeida', 20, 'BRAZ', 'LOPEZ', '2026-07-25', '2026-07-30', ''),
    ('16', 'Tomaz Santos Almeida', 20, 'BRAZ', 'LOPEZ', '2026-07-25', '2026-07-30', ''),
    ('17', 'Sueli Fatima Santos Almeida', 61, 'BRAZ', 'LOPEZ', '2026-07-25', '2026-07-30', ''),
    ('17', 'Walter Lopez De Almeida', 71, 'BRAZ', 'LOPEZ', '2026-07-25', '2026-07-30', ''),
    ('18', 'Dmitry Ermolaev', 56, 'RUSS', 'TROFIMOV', '2026-07-27', '2026-07-29', ''),
    ('19', 'Adriana Sandra Milena Daza Gil', 50, 'CHIL', 'DAZA', '2026-07-24', '2026-07-29', ''),
    ('19', 'Patricio Esteban Maraboli Valenzuela', 44, 'CHIL', 'DAZA', '2026-07-24', '2026-07-29', ''),
    ('21', 'Gabriela Muniz Barreto', 47, 'BRAZ', 'CAROSELLA', '2026-07-23', '2026-07-29', ''),
    ('22', 'Igor Pichkalev', 58, 'RUSS', 'TROFIMOV', '2026-07-27', '2026-07-29', ''),
    ('23', 'Nikolay Veselovskiy', 59, 'RUSS', 'TROFIMOV', '2026-07-27', '2026-07-29', ''),
    ('24', 'Karolina Litvintseva', 39, 'RUSS', 'TROFIMOV', '2026-07-27', '2026-07-29', 'ALERGIA AL POLLO. Alergias: POLLO'),
    ('24', 'Alexey Trofimov', 56, 'RUSS', 'TROFIMOV', '2026-07-27', '2026-07-29', ''),
    ('25', 'Julio Cesar Mazzetto Junior', 68, 'BRAZ', 'FURLAN', '2026-07-25', '2026-07-31', ''),
    ('25', 'Cidalia Maria Mazzetto', 71, 'BRAZ', 'FURLAN', '2026-07-25', '2026-07-31', ''),
    ('26', 'Eduardo Furlan Villares', 23, 'BRAZ', 'FURLAN', '2026-07-25', '2026-07-31', ''),
    ('26', 'Felipe Furlan Villares', 21, 'BRAZ', 'FURLAN', '2026-07-25', '2026-07-31', ''),
    ('27', 'Luiz Fernando Furlan', 80, 'BRAZ', 'FURLAN', '2026-07-25', '2026-07-31', ''),
    ('28', 'Giulia Ellis Ramalho', 15, 'BRAZ', 'GALANTE', '2026-07-28', '2026-07-30', ''),
    ('28', 'Max Schwarz', 14, 'BRAZ', 'GALANTE', '2026-07-28', '2026-07-30', ''),
    ('28', 'Patrizia Galante', 78, 'ITAL', 'GALANTE', '2026-07-28', '2026-07-30', ''),
    ('29', 'Luis Ramirez Vera', 30, 'PARA', 'CEUPPENS', '2026-07-27', '2026-07-30', ''),
    ('29', 'Blanca Irene Ceuppens Rios', 31, 'PARA', 'CEUPPENS', '2026-07-27', '2026-07-30', ''),
    ('30', 'Lara Haddad Kairalla', 41, 'BRAZ', 'FUAD', '2026-07-24', '2026-07-30', ''),
    ('30', 'Luciano Fuad Kairalla', 40, 'BRAZ', 'FUAD', '2026-07-24', '2026-07-30', 'LIBRE DE LACTOSA - SOLO COME QUESO SIN LACTOSA. Requerimientos alimentarios: Libre de Lactosa'),
    ('31', 'Maria Cecilia Cavalcante Ciampolini', 72, 'BRAZ', 'FURLAN', '2026-07-25', '2026-07-31', ''),
    ('32', 'Francesca Carosella Aldrovandi', 14, 'ITAL', 'CAROSELLA', '2026-07-23', '2026-07-29', 'VEGETARIANA COME PESCADO. Requerimientos alimentarios: Vegetariana'),
    ('32', 'Letizia Rinaldini', 59, 'ITAL', 'MARENGO', '2026-07-29', '2026-08-01', ''),
    ('32', 'Gabriel Pires Demarchi', 15, 'BRAZ', 'CAROSELLA', '2026-07-23', '2026-07-29', ''),
    ('32', 'Enrico Bufalini', 59, 'ITAL', 'MARENGO', '2026-07-29', '2026-08-01', ''),
    ('33', 'Guilhermina Meggiolaro Paes De Azevedo', 17, 'BRAZ', 'MEGGIOLARO', '2026-07-27', '2026-08-02', ''),
    ('33', 'Leticia Meggiolaro Paes De Azevedo', 15, 'BRAZ', 'MEGGIOLARO', '2026-07-27', '2026-08-02', ''),
    ('34', 'Diego Quintas Paes De Azevedo', 49, 'BRAZ', 'MEGGIOLARO', '2026-07-27', '2026-08-02', ''),
    ('34', 'Daniella Meggiolaro Paes De Azevedo', 49, 'BRAZ', 'MEGGIOLARO', '2026-07-27', '2026-08-02', ''),
    ('35', 'Adriana Elisa Wilk', 52, 'BRAZ', 'WILK', '2026-07-26', '2026-07-29', 'ALERGIA A TRUFA Y PENICILINA'),
    ('35', 'Claudia Merlin', 55, 'ITAL', 'MARENGO', '2026-07-29', '2026-08-01', ''),
    ('35', 'Giovana Schallenberger', 52, 'BRAZ', 'WILK', '2026-07-26', '2026-07-29', ''),
    ('35', 'Emilio Marengo', 67, 'ITAL', 'MARENGO', '2026-07-29', '2026-08-01', ''),
    ('36', 'Cristianna Moreira Martins De Almeida', 53, 'BRAZ', 'INNECCO', '2026-07-26', '2026-07-30', ''),
    ('36', 'Eduardo Correa Innecco', 57, 'BRAZ', 'INNECCO', '2026-07-26', '2026-07-30', ''),
    ('37', 'Elisa Ibanez Bulnes', 44, 'CHIL', 'IBANEZ', '2026-07-27', '2026-07-31', ''),
    ('37', 'Leopoldine Hugues', 35, 'CHIL', 'IBANEZ', '2026-07-27', '2026-07-31', ''),
    ('38', 'Bernardo De Almeida Innecco', 20, 'BRAZ', 'INNECCO', '2026-07-26', '2026-07-30', 'ALERGIA CAMARONES'),
    ('38', 'Felipe Ruas Martins De Almeida', 31, 'BRAZ', 'INNECCO', '2026-07-26', '2026-07-30', ''),
    ('39', 'Charles Edward Shepperson Robottom', 59, 'ENGL', 'ROBOTTOM', '2026-07-28', '2026-07-31', ''),
    ('39', 'Matilda Victoria Robottom', 16, 'ENGL', 'ROBOTTOM', '2026-07-28', '2026-07-31', ''),
    ('39', 'Andrea Joan Robottom', 56, 'ENGL', 'ROBOTTOM', '2026-07-28', '2026-07-31', ''),
    ('40', 'Pedro Ospina Molina', 16, 'ECUA', 'OSPINA', '2026-07-29', '2026-08-01', ''),
    ('40', 'Juan Camilo Ospina Molina', 18, 'ECUA', 'OSPINA', '2026-07-29', '2026-08-01', ''),
    ('41', 'Joao Pedro Nogueira De Sa Santos Pereira', 8, 'BRAZ', 'NOGUEIRA', '2026-07-23', '2026-07-30', ''),
    ('41', 'Maria Clara Comparini Nogueira De Sa Santos Pereira', 41, 'BRAZ', 'NOGUEIRA', '2026-07-23', '2026-07-30', ''),
    ('42', 'Rosa Maria Dos Santos', 55, 'BRAZ', 'NOGUEIRA', '2026-07-23', '2026-07-30', ''),
    ('42', 'Luiz Eduardo Nogueira De Sá Santos Pereira', 4, 'BRAZ', 'NOGUEIRA', '2026-07-23', '2026-07-30', ''),
    ('43', 'Alondra Reyes Garza', 10, 'MEXI', 'GARZA', '2026-07-28', '2026-08-01', ''),
    ('43', 'Juan Carlos Reyes Oropeza', 51, 'MEXI', 'GARZA', '2026-07-28', '2026-08-01', ''),
    ('43', 'Guadalupe Arlette Garza Serrano', 47, 'MEXI', 'GARZA', '2026-07-28', '2026-08-01', ''),
    ('44', 'Pedro Ospina', 45, 'ECUA', 'OSPINA', '2026-07-29', '2026-08-01', ''),
    ('44', 'Paola Florencia Carosella', 53, 'ARGE', 'CAROSELLA', '2026-07-23', '2026-07-29', ''),
    ('44', 'Cayetana Ospina', 11, 'SPAI', 'OSPINA', '2026-07-29', '2026-08-01', ''),
    ('44', 'Ana Molina', 45, 'SPAI', 'OSPINA', '2026-07-29', '2026-08-01', ''),
    ('45', 'Laura Riehm', 55, 'CANA', 'RIEHM', '2026-07-28', '2026-08-01', ''),
    ('46', 'Gustavo Osorio Posselt Furlan', 4, 'BRAZ', 'FURLAN', '2026-07-25', '2026-07-31', ''),
    ('46', 'Leonardo Osorio Posselt Furlan', 1, 'BRAZ', 'FURLAN', '2026-07-25', '2026-07-31', ''),
    ('46', 'Heliene Reis Santos', 50, 'BRAZ', 'FURLAN', '2026-07-25', '2026-07-31', ''),
    ('47', 'Luiz Gotardo Furlan', 42, 'BRAZ', 'FURLAN', '2026-07-25', '2026-07-31', ''),
    ('47', 'Thais Posselt Furlan', 40, 'BRAZ', 'FURLAN', '2026-07-25', '2026-07-31', 'NO CHAMPIS. Requerimientos alimentarios: Vegetariana'),
    ('48', 'Maria Teresa Nogueira De Sá Santos Pereira', 10, 'BRAZ', 'NOGUEIRA', '2026-07-23', '2026-07-30', ''),
    ('48', 'Renato Junqueira Santos Pereira', 49, 'BRAZ', 'NOGUEIRA', '2026-07-23', '2026-07-30', ''),
    ('48', 'Marco Antonio Nogueira De Sá Santos Pereira', 6, 'BRAZ', 'NOGUEIRA', '2026-07-23', '2026-07-30', ''),
    ('49', 'Silvio Franca Torres', 80, 'BRAZ', 'FURLAN', '2026-07-25', '2026-07-30', ''),
    ('49', 'Vera Lucia Torres', 74, 'BRAZ', 'FURLAN', '2026-07-25', '2026-07-31', ''),
    ('50', 'Ilyas Mukhtarov', 58, 'RUSS', 'TROFIMOV', '2026-07-27', '2026-07-29', ''),
]


# ── Normalización de observaciones → tags canónicos ──────────────────────────
# La observación llega como texto libre en ES/EN/PT y mayúsculas irregulares.
# Se parte en fragmentos, cada fragmento se clasifica por MODO (alergia si
# menciona alergia/celiaquía/intolerancia; dieta si es preferencia/"no come")
# y por TEMA (qué alimento). El texto original se conserva verbatim en `obs`
# — los tags filtran, la observación completa manda en el detalle.

# Temas de alimento → (regex, slug canónico). Camarones/ostras/erizos caen
# bajo el paraguas "mariscos" para que el filtro responda la pregunta real
# del salón ("¿alérgicos a mariscos?"); el detalle específico queda en obs.
FOOD_TOPICS = [
    (r"MARISC|CAMARON|OSTRA|ERIZO|FRUTOS? DEL? MAR|F\. ?DEL? MAR|SEAFOOD|SHELLFISH", "mariscos"),
    (r"GLUTEN|CELIAC",                       "gluten"),
    (r"LACTOS|LACTO\b|LACTEOS?|DAIRY",       "lactosa"),
    (r"SESAM",                               "sesamo"),
    (r"PESCADO|\bFISH\b",                    "pescado"),
    (r"\bAJO\b|GARLIC",                      "ajo"),
    (r"FRUTOS SECOS|NUEZ|NUECES|\bMANI\b|ALMENDRA|NUTS?\b", "frutos-secos"),
    (r"FRUTILLA|FRESA|STRAWBERR",            "frutillas"),
    (r"\bPINA\b|ANANA|PINEAPPLE|ABACAXI",    "pina"),
    (r"CILANTRO|CULANTRO|CORIANDER",         "cilantro"),
    (r"QUINOA|QUINUA",                       "quinoa"),
    (r"TRUFA|TRUFFLE|TARTUFO",               "trufa"),
    (r"CHAMPI|HONGO|SETA\b|MUSHROOM|COGUMELO|FUNGH", "champinones"),
    (r"\bPOLLO\b|CHICKEN|\bFRANGO\b",        "pollo"),
    # --- ampliación 2026-08-17, auditoría contra el reporte real de PGO ---
    # Pistacho y castaña de cajú entran al paraguas "frutos secos" por la misma
    # razón que camarón entra en mariscos: la pregunta del salón es del grupo;
    # el detalle exacto queda en obs, que se muestra completo.
    (r"PISTACH|CAJU|CASHEW|CASTANHA|CASTANA|ANACARDO|AVELLANA|HAZELNUT|PECAN|MACADAMIA", "frutos-secos"),
    (r"\bKIWI\b",                            "kiwi"),
    (r"TOMATE|TOMATO",                       "tomate"),
    (r"\bHUEVO\b|\bEGGS?\b|\bOVO\b",         "huevo"),
    (r"\bSOJA\b|\bSOYA\b|\bSOY\b",           "soja"),
    (r"\bCAFE\b|COFFEE",                     "cafe"),
    (r"PICANTE|\bAJI\b|SPICY|CHILI",         "picante"),
    (r"ALCOHOL|\bALCOOL\b",                  "alcohol"),
    (r"\bCEBOLLA\b|\bONION\b|\bCEBOLA\b",    "cebolla"),
    (r"PALTA|AGUACATE|AVOCADO",              "palta"),
    (r"\bMIEL\b|\bHONEY\b",                  "miel"),
    (r"\bAPIO\b|CELERY",                     "apio"),
    (r"MOSTAZA|MUSTARD",                     "mostaza"),
    (r"CITRIC|\bLIMON\b|NARANJA",            "citricos"),
    (r"\bMANGO\b",                           "mango"),
    (r"\bCEREZA\b|CHERRY",                   "cereza"),
    (r"\bMELON\b|\bSANDIA\b",                "melon"),
]

# Temas que siempre son dieta (preferencia) o condición, sin importar el modo.
DIET_TOPICS = [
    (r"VEGETARIAN",                          "vegetariana"),
    (r"VEGAN[OA]?\b",                        "vegana"),
    (r"PESCETARIAN|PESCATARIAN",             "pescetariana"),
    (r"CERDO|CHANCHO|\bPORK\b",              "sin-cerdo"),
    (r"CARNES? ROJAS?|RED MEAT|\bBEEF\b",    "sin-carnes-rojas"),
    (r"CORDERO|\bLAMB\b",                    "sin-cordero"),
    (r"FRITURA|FRITOS?\b|FRIED",             "sin-fritura"),
    (r"\bAZUCAR\b|\bSUGAR\b|SEM ACUCAR",     "sin-azucar"),
]
COND_TOPICS = [
    (r"DIABET",                              "diabetico"),
    (r"EMBARAZ|PREGNAN",                     "embarazada"),
]

# ALEG(IA) sin R y ALERJ con J son erratas reales del reporte de PGO. Sin
# contemplarlas, "ALEGIA PISTACHOS" se clasificaba como preferencia y no como
# ALERGIA — el chip salía ámbar en vez de rojo.
ALLERGY_MODE = re.compile(r"ALERG|ALEG[IU]|ALERJ|ALLERG|ALLERY|CELIAC|INTOLERAN|ANAFILA")
# Guard de negación: "I am not allergic to Gluten" NO es una alergia — sin esto
# el ALLERGY_MODE lo marcaría en rojo. La observación completa manda en el obs.
NEG_ALLERGY  = re.compile(r"NO ALERG|NOT ALLERGIC|NO SOY ALERG")
SPLIT_FRAGS  = re.compile(r"[;,·/]|\.\s|\n|\s[-–]\s|\sY\s|\sAND\s|\sE\s")
# Afirmación de consumo: "come pescado" (sí lo come) NO es evitación → no debe
# generar un tag "sin-pescado". Sólo aplica cuando el fragmento dice "come" sin
# ninguna marca de evitación; "no come", "libre de", "sin", "alergia" sí lo son
# ("vegetariana come pescado" = pescetariana; queda vegetariana + obs completa).
EATS_AFFIRM  = re.compile(r"\bCOME[NS]?\b")
AVOID_MARK   = re.compile(r"\bNO\b|LIBRE|\bSIN\b|EVITA|ALERG|INTOLER|CELIAC")


def _fold(s):
    """Mayúsculas sin tildes — 'Alergia al ajo' → 'ALERGIA AL AJO'."""
    return unicodedata.normalize("NFD", str(s)).encode("ascii", "ignore").decode().upper()


# Etiquetas del propio reporte, no contenido. Si sacándolas no queda nada, la
# observación estaba vacía; si queda texto, ese texto DICE algo.
_OBS_ETIQUETAS = re.compile(
    r"OBSERVACIONES?|REQUERIMIENTOS? ALIMENTARIOS?|ALERGIAS?|COMENTARIOS?|"
    r"SIN RESTRICCIONES? ALIMENTICIAS?|SIN RESTRICCIONES?|NINGUNA|NINGUNO|N/?A", re.I)


def obs_significativa(obs):
    """¿La observación dice algo, más allá de sus propias etiquetas?"""
    t = _OBS_ETIQUETAS.sub(" ", _fold(obs))
    return len(re.sub(r"[^A-Z0-9]", "", t)) >= 3


def obs_to_tags(obs):
    """Texto libre → lista ordenada de tags canónicos (sin duplicados)."""
    tags = []
    if not obs:
        return tags
    for frag in SPLIT_FRAGS.split(_fold(obs)):
        frag = frag.strip()
        if not frag:
            continue
        allergy = bool(ALLERGY_MODE.search(frag)) and not NEG_ALLERGY.search(frag)
        affirm  = bool(EATS_AFFIRM.search(frag)) and not AVOID_MARK.search(frag)
        for rx, slug in FOOD_TOPICS:
            if re.search(rx, frag):
                if affirm:            # "come pescado" = sí lo come, no es restricción
                    continue
                tags.append(f"alergia-{slug}" if allergy else f"dieta-sin-{slug}")
        for rx, slug in DIET_TOPICS:
            if re.search(rx, frag):
                tags.append(f"dieta-{slug}")
        for rx, slug in COND_TOPICS:
            if re.search(rx, frag):
                tags.append(f"cond-{slug}")
    # Dedup conservando orden; si el mismo tema salió como alergia Y dieta
    # (p.ej. "Libre de Gluten - CELIACA"), la alergia gana y la dieta se cae.
    seen, out = set(), []
    for t in tags:
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    for t in list(out):
        if t.startswith("alergia-") and f"dieta-sin-{t[8:]}" in seen:
            out.remove(f"dieta-sin-{t[8:]}")
    return out


# ── Construcción del doc ──────────────────────────────────────────────────────

# Firebase Realtime Database rechaza como clave: vacío y cualquier cosa con
# . $ # [ ] / o caracteres de control — devuelve 400 y NO escribe nada. La hab
# viene del reporte, así que una celda rara (vacía, "S/N", "12.A") tiraba abajo
# el sync entero. Pasó el 2026-08-07: PGO leyó las 71 filas y el PUT murió.
_FB_BAD_KEY = re.compile(r"[.$#\[\]/\x00-\x1f\x7f]")

def fb_key(valor, fallback="SIN HAB"):
    k = _FB_BAD_KEY.sub("", str(valor or "")).strip()
    return k or fallback


def build_doc(rows, date_str, source, horas=None, totales=None, comedor=None, cumples=None):
    habs = {}
    for i, (hab, nombre, edad, nac, grupo, in_d, out_d, obs) in enumerate(rows):
        hab_ok = fb_key(hab)
        if hab_ok != str(hab or "").strip():
            print(f"[sync-viajeros] Aviso: hab '{hab}' no sirve como clave → '{hab_ok}'.")
        hab = hab_ok
        traveler = {
            "id":     f"h{hab}-{i}",
            "nombre": nombre,
            "edad":   edad,
            "nac":    nac,
            "grupo":  grupo,
            "in":     in_d,
            "out":    out_d,
            "tags":   obs_to_tags(obs),
            "obs":    obs.strip(),
            # revisar = la observación DICE algo que el script no supo mapear.
            # Es la red de seguridad: ampliar la taxonomía nunca va a alcanzar
            # (siempre aparece un alimento nuevo), pero esto garantiza que nada
            # se pierda EN SILENCIO. La app lo muestra en ámbar en vez de
            # pintar un tranquilizador "sin restricciones".
            **({"revisar": True} if (obs_significativa(obs) and not obs_to_tags(obs)) else {}),
            # "foto": <url> — hook para la cédula futura; ausente = avatar iniciales
        }
        # Horas REALES de movimiento (GraphQL reportInOut), por habitación: la
        # app las usa para contar quién está de verdad a esta hora en vez de
        # descontar desde medianoche a todo el que sale hoy. Se agregan sólo si
        # existen — el shape viejo (in/out por fecha) queda intacto.
        # OJO: la hora se aplica SÓLO a quien efectivamente se mueve hoy. Una
        # habitación se reocupa el mismo día (sale uno 07:00, entra otro 17:30);
        # cruzar por hab a secas le pegaba el outAt del que se fue al que recién
        # llegaba, y el intervalo quedaba invertido — esa persona no aparecía
        # presente en NINGÚN servicio.
        h = (horas or {}).get(hab) or {}
        if in_d and in_d != date_str:
            h = {k: v for k, v in h.items() if not k.startswith("in")}
        if out_d and out_d != date_str:
            h = {k: v for k, v in h.items() if not k.startswith("out")}
        if h.get("inAt"):
            traveler["inAt"]  = h["inAt"]
            traveler["inSrc"] = h.get("inSrc", "")
        if h.get("outAt"):
            traveler["outAt"]  = h["outAt"]
            traveler["outSrc"] = h.get("outSrc", "")
        cum = (cumples or {}).get(norm_key(nombre))
        if cum:
            traveler["cumple"] = cum      # 'DD-MM', sin año: la app compara el día
        for k in ("inFlightAt", "inFlight", "outFlightAt", "outFlight"):
            if h.get(k):
                traveler[k] = h[k]
        habs.setdefault(hab, []).append(traveler)
    doc_extra = {}
    if comedor and comedor.get("grupos"):
        doc_extra["comedor"] = comedor
    if totales:
        # Contadores del propio PGO. No reemplazan el conteo por hora de la app
        # (que es el que envejece bien), pero sirven de contraste: si difieren
        # mucho, algo se está perdiendo en el cruce.
        doc_extra["pgoCounts"] = {k: v for k, v in totales.items() if v is not None}
    return {
        **doc_extra,
        "date":      date_str,
        # utcnow() devuelve un datetime NAIVE, y .timestamp() interpreta los
        # naive como hora LOCAL: corrido desde Chile el updatedAt salía +4h en
        # el futuro. En el runner de GitHub (UTC) daba bien de casualidad. Ahora
        # que la app usa este valor para el indicador de frescura, un timestamp
        # futuro haría que el punto de estado se escondiera solo.
        "updatedAt": int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000),
        "source":    source,
        "habs":      habs,
    }


# ── Fase 2 · PGO (portal web) ────────────────────────────────────────────────
# Los reportes NO son un Excel de SharePoint: viven en PGO, una aplicación web.
# Los PDFs que se bajaban a mano son "Imprimir a PDF" del navegador (los meta
# dicen Title:PGO · Producer:Skia/PDF · Creator:…Edg…). Por eso la fase 2 inicia
# sesión en PGO con Playwright (Chromium headless), abre el "Reporte Geos" y
# "Dietas" del día y LEE LAS TABLAS HTML directamente (dato limpio, sin parsear
# PDF). El resto (cruce por nombre → build_doc → obs_to_tags → fb_put) es igual
# que el seed.
#
# Secrets (GitHub → Settings → Secrets and variables → Actions):
#   PGO_USER      → usuario de PGO
#   PGO_PASS      → contraseña de PGO
#   PGO_BASE_URL  → URL base de PGO (ej. https://pgo.ejemplo.com). Va como secret
#                   para no dejar el host interno en el repo.
#   FIREBASE_KEY  → (ya existente) service account de Firebase.
#
# Config de la UI de PGO — se confirma UNA vez contra el HTML real. Todo es
# sobrescribible por variable de entorno, así que se afina sin tocar el código.
# Para descubrir selectores/rutas cuando falten:
#   PGO_BASE_URL=… PGO_USER=… PGO_PASS=… \
#     python scripts/sync_viajeros.py --from-pgo --dump-html --debug
#   → guarda el HTML de login y de cada reporte en ./pgo-dump/ (no escribe Firebase).
#
# Rutas CONFIRMADAS con capturas del portal (2026-07-31):
#   https://www.pgo-explora.com/report-geos → Reporte Geos
#   https://www.pgo-explora.com/dietas      → Reporte Dietas
# (el navegador esconde el "www."; el DNS público sólo tiene el host con www)
# La FECHA NO viaja en la URL: es una SPA con un datepicker (formato DD-MM-YYYY)
# y un botón REFRESCAR. Por eso el script setea la fecha en el input y refresca,
# en vez de armar un link con querystring.
PGO_BASE_URL    = (os.environ.get("PGO_BASE_URL") or "https://www.pgo-explora.com").rstrip("/")
PGO_GEOS_PATH   = os.environ.get("PGO_GEOS_PATH")   or "/report-geos"
PGO_DIETAS_PATH = os.environ.get("PGO_DIETAS_PATH") or "/dietas"
# Reportes que todavía NO alimentan el doc: se leen sólo con --explore mientras
# se calibran los mapeos de columnas. Cuando cada uno entre al pipeline, pasa a
# usarse en pgo_fetch como los dos de arriba.
PGO_ARRIVAL_PATH  = os.environ.get("PGO_ARRIVAL_PATH")  or "/arrival-report"
PGO_BIRTHDAY_PATH = os.environ.get("PGO_BIRTHDAY_PATH") or "/birthday-report"
PGO_COMEDOR_PATH  = os.environ.get("PGO_COMEDOR_PATH")  or "/comedor"
PGO_EXPLORE_PATHS = {
    "inout":    "(GraphQL reportInOut)",
    "arrival":  PGO_ARRIVAL_PATH,
    "birthday": PGO_BIRTHDAY_PATH,
    "comedor":  PGO_COMEDOR_PATH,
}
# Ventana del reporte de llegadas. Hacia atrás lo suficiente para alcanzar a
# todos los que siguen en casa (estadía típica de 3-4 noches, con margen);
# hacia adelante para ver quién llega hoy más tarde y mañana.
PGO_ARRIVAL_BACK = int(os.environ.get("PGO_ARRIVAL_BACK") or 10)
PGO_ARRIVAL_FWD  = int(os.environ.get("PGO_ARRIVAL_FWD")  or 1)
# Atacama = 2 (code EATA). Torres del Paine es el 1: pedirle al hotel equivocado
# devuelve datos válidos DE OTRO LODGE y no se nota mirando el resultado.
PGO_HOTEL_ID = int(os.environ.get("PGO_HOTEL_ID") or 2)
PGO_GQL_URL  = os.environ.get("PGO_GQL_URL") or "https://backend.pgo-explora.com"
PGO_DATE_FMT    = os.environ.get("PGO_DATE_FMT")    or "%d-%m-%Y"   # como se ve en el input: 31-07-2026
# Selector del input de fecha y del botón refrescar (texto visible, robusto a
# cambios de clases). Sobrescribibles por env si el markup cambia.
PGO_SEL_DATE    = os.environ.get("PGO_SEL_DATE",    "input[value*='-20'], input[placeholder*='-'], .ant-picker-input input, input[type='text']")
PGO_SEL_REFRESH = os.environ.get("PGO_SEL_REFRESH") or "REFRESCAR"   # se busca por texto (case-insensitive)
PGO_TABLE_SEL   = os.environ.get("PGO_TABLE_SEL",   "")   # vacío = autodetecta la tabla con más filas
# PGO abre siempre en Torres del Paine: hay que cambiar el destino antes de
# pedir cualquier reporte, o la grilla llega sin filas (dibuja el encabezado
# igual, que es lo que despistaba). El destino se elige en la barra superior.
PGO_DESTINO     = os.environ.get("PGO_DESTINO")     or "Atacama"
# TODO(pgo): login — falta ver la pantalla de acceso. Si PGO ya deja sesión por
# cookie, el script igual funciona: si al abrir el reporte NO estamos logueados,
# intenta el formulario con estos selectores. Confirmar con --dump-html.
PGO_LOGIN_PATH  = os.environ.get("PGO_LOGIN_PATH")  or "/login"
PGO_SEL_USER    = os.environ.get("PGO_SEL_USER",    "input[name='usuario'], input[name='username'], input[type='email']")
PGO_SEL_PASS    = os.environ.get("PGO_SEL_PASS",    "input[name='clave'], input[name='password'], input[type='password']")
PGO_SEL_SUBMIT  = os.environ.get("PGO_SEL_SUBMIT",  "button[type='submit'], input[type='submit']")


def norm_key(s):
    """Texto sin tildes en minúscula — para cruzar Dietas ↔ Geos por nombre."""
    return unicodedata.normalize("NFD", str(s)).encode("ascii", "ignore").decode().lower().strip()


def _pgo_require():
    """Sólo el usuario y la clave son obligatorios: la URL base tiene default.
    Ojo: en Actions un secret inexistente llega como env var VACÍA, por eso
    todas las constantes de arriba usan `or default` y acá se valida el valor
    ya resuelto (PGO_BASE_URL), no el env crudo."""
    faltan = [k for k in ("PGO_USER", "PGO_PASS") if not os.environ.get(k)]
    if not PGO_BASE_URL:
        faltan.insert(0, "PGO_BASE_URL")
    if faltan:
        raise SystemExit(
            "[sync-viajeros] Fase 2 PGO no configurada: faltan " + ", ".join(faltan)
            + ".\n  Definí esos secrets/variables (nunca en el código) y reintentá."
        )


# JS que extrae una tabla HTML → {headers:[...], rows:[[celda,...],...]}.
# Autodetecta la tabla con más filas si no se pasó un selector explícito.
_PGO_TABLE_JS = r"""
(sel) => {
  const norm = s => (s || '').replace(/\s+/g, ' ').trim();
  const fold = s => norm(s).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  const WANT = ['hab','nombre','viajero','nac','edad','grupo','observacion','in/out'];
  const DOW  = ['sun','mon','tue','wed','thu','fri','sat',
                'dom','lun','mar','mie','jue','vie','sab'];

  const rowsOf = (el, cellSel) =>
    [...el.querySelectorAll('tr,[role=row]')].map(r =>
      [...r.querySelectorAll(cellSel)].map(c => norm(c.innerText)));

  // Encabezados y filas de un contenedor (tabla clásica o grilla ARIA)
  const parse = el => {
    const isTable = el.tagName === 'TABLE';
    const hdrSel  = isTable ? 'th' : '[role=columnheader]';
    const cellSel = isTable ? 'td,th' : '[role=gridcell],[role=cell],[role=columnheader]';
    const trs = [...el.querySelectorAll('tr,[role=row]')];
    if (!trs.length) return null;
    let hi = trs.findIndex(r => r.querySelector(hdrSel));
    if (hi < 0) hi = -1;                        // sin encabezado: sólo cuerpo
    const headers = hi >= 0
      ? [...trs[hi].querySelectorAll(hdrSel + ',td')].map(c => norm(c.innerText))
      : [];
    const rows = [];
    for (let i = hi + 1; i < trs.length; i++) {
      const cells = [...trs[i].querySelectorAll(cellSel)].map(c => norm(c.innerText));
      if (cells.some(x => x)) rows.push(cells);
    }
    return {headers, rows, el};
  };

  const score = d => {
    if (!d || !d.headers.length) return -1;
    const h = d.headers.map(fold);
    if (h.every(x => DOW.includes(x))) return -1;          // calendario
    return WANT.filter(w => h.some(x => x.includes(w))).length;
  };

  // Los calendarios de Element UI nunca son candidatos (ni como encabezado ni
  // como cuerpo): se descartan por clase antes de puntuar.
  const esCalendario = el =>
    /date-table|year-table|month-table|picker|calendar/i.test(el.className || '') ||
    !!el.closest('.el-date-picker,.el-picker-panel,[class*=picker],[class*=calendar]');
  const cands = [...document.querySelectorAll('table,[role=table],[role=grid]')]
                  .filter(el => !esCalendario(el))
                  .map(parse).filter(Boolean);
  if (sel) {
    const el = document.querySelector(sel);
    const d = el && parse(el);
    if (d) return {headers: d.headers, rows: d.rows};
  }

  let best = null, bestScore = 0;
  for (const d of cands) {
    const sc = score(d);
    if (sc > bestScore) { bestScore = sc; best = d; }
  }
  if (!best) return null;

  // Element UI (y otros) parten la tabla en DOS: una sólo con los títulos
  // (header fijo) y otra sólo con los datos. Si la mejor candidata no trae
  // filas, se le pega el cuerpo de la tabla hermana cuyo Nº de columnas coincida.
  if (!best.rows.length) {
    const nCols = best.headers.length;
    let body = null;
    const wrap = best.el.closest('div');
    const pool = cands.filter(d => d !== best && d.rows.length);
    const near = pool.filter(d => wrap && wrap.contains(d.el));
    for (const d of (near.length ? near : pool)) {
      const cols = d.rows[0].length;
      if (cols === nCols) { body = d; break; }
      if (!body && Math.abs(cols - nCols) <= 2) body = d;
    }
    if (body) return {headers: best.headers, rows: body.rows};
  }
  return {headers: best.headers, rows: best.rows};
}
"""


def _pgo_dump(page, name):
    """Guarda el HTML de la página para ajustar selectores.
    OJO: el HTML contiene DATOS PERSONALES de huéspedes (nombres, alergias).
    Los artifacts del workflow se suben con retención corta; no publicar."""
    import pathlib
    d = pathlib.Path("pgo-dump"); d.mkdir(exist_ok=True)
    (d / f"{name}.html").write_text(page.content(), encoding="utf-8")
    print(f"[sync-viajeros] HTML guardado en pgo-dump/{name}.html")


def _pgo_fecha_visible(page):
    """Fecha que PGO está mostrando (DD-MM-YYYY) → ISO, o None."""
    try:
        v = page.evaluate(
            "() => { const rx = /^\\s*\\d{1,2}[-\\/]\\d{1,2}[-\\/]\\d{2,4}\\s*$/;"
            "  const i = [...document.querySelectorAll('input')]"
            "    .find(x => x.offsetParent !== null && rx.test(x.value||''));"
            "  return i ? i.value.trim() : null; }")
        if not v:
            return None
        d, m, a = re.split(r"[-/]", v)
        return f"{int(a):04d}-{int(m):02d}-{int(d):02d}"
    except Exception:
        return None


def _pgo_refrescar(page):
    """Aprieta REFRESCAR sin tocar la fecha (PGO ya muestra el día operativo)."""
    try:
        btn = page.get_by_text(re.compile(PGO_SEL_REFRESH, re.I)).first
        if btn.count() > 0:
            btn.click(timeout=8000)
            print("[sync-viajeros] REFRESCAR clickeado (fecha por defecto de PGO).")
        page.wait_for_load_state("networkidle", timeout=60000)
    except Exception as e:
        print(f"[sync-viajeros] Aviso: no pude refrescar ({e}).")


def _pgo_fecha_ok(page, esperada):
    """¿La página quedó en la fecha pedida? Compara contra lo que MUESTRA.

    PGO abre por defecto en el día SIGUIENTE. Si fijar la fecha falla y nadie
    verifica, el reporte se lee igual y trae el día equivocado — un error que
    no se nota porque la app sólo muestra la fecha como etiqueta.
    """
    if not esperada:
        return True
    try:
        visible = _pgo_fecha_visible(page)
    except Exception:
        visible = None
    if not visible:
        print("[sync-viajeros] Aviso: no pude leer la fecha en pantalla para verificarla.")
        return False
    # _pgo_fecha_visible devuelve ISO; `esperada` viene en el formato del input.
    try:
        esp_iso = datetime.datetime.strptime(esperada, PGO_DATE_FMT).date().isoformat()
    except ValueError:
        esp_iso = esperada
    if visible == esp_iso:
        return True
    print(f"[sync-viajeros] ⚠ La página quedó en {visible} y se pidió {esp_iso}.")
    return False


def _pgo_set_date(page, fecha):
    """Fija la fecha del reporte y refresca.

    El campo se ubica POR CONTENIDO: el input visible cuyo valor ya tiene forma
    de fecha (DD-MM-YYYY). Antes se buscaba por CSS y el comodín acababa
    agarrando el BUSCADOR de la página — se tipeaba la fecha ahí, la grilla
    filtraba por ese texto y quedaba vacía. Element UI, además, no usa las
    clases de Ant Design que se habían supuesto.
    """
    try:
        info = page.evaluate("""
          () => {
            const vis = el => el && el.offsetParent !== null;
            const rx = /^\\s*\\d{1,2}[-\\/]\\d{1,2}[-\\/]\\d{2,4}\\s*$/;
            const ins = [...document.querySelectorAll('input')].filter(vis);
            let el = ins.find(i => rx.test(i.value || ''));                 // ya trae una fecha
            if (!el) el = ins.find(i => /fecha|date/i.test(
                          (i.getAttribute('placeholder')||'') + ' ' +
                          (i.className||'') + ' ' + (i.id||'')));
            if (!el) return null;
            el.setAttribute('data-pgo-date', '1');
            return {valor: el.value || '', cls: (el.className||'').slice(0,50),
                    ph: el.getAttribute('placeholder')||''};
          }
        """)
        if not info:
            print("[sync-viajeros] Aviso: no identifiqué el campo de fecha; leo lo que muestre el reporte.")
            return False
        print(f"[sync-viajeros] Campo de fecha detectado (valor actual '{info['valor']}', "
              f"clase '{info['cls']}').")
        if (info["valor"] or "").strip() != fecha:
            loc = page.locator("input[data-pgo-date='1']").first
            loc.click()
            loc.press("Control+a")
            loc.press("Delete")
            loc.type(fecha, delay=45)
            page.keyboard.press("Enter")
            page.wait_for_timeout(400)
        page.keyboard.press("Escape")   # cierra el calendario: si queda abierto tapa la tabla
        page.wait_for_timeout(200)
        # El botón primero como ROLE y recién después por texto: get_by_text
        # suele agarrar un <span> interior que no recibe el click y se va a
        # timeout (pasaba en /comedor). force=True salta el overlay del
        # calendario si quedó abierto por encima.
        clickeado = False
        for intento in (
            lambda: page.get_by_role("button", name=re.compile(PGO_SEL_REFRESH, re.I)).first,
            lambda: page.get_by_text(re.compile(PGO_SEL_REFRESH, re.I)).first,
        ):
            try:
                b = intento()
                if b.count() > 0:
                    b.click(timeout=6000)
                    clickeado = True
                    break
            except Exception:
                continue
        if not clickeado:
            try:
                page.get_by_text(re.compile(PGO_SEL_REFRESH, re.I)).first.click(timeout=4000, force=True)
                clickeado = True
            except Exception:
                pass
        print(f"[sync-viajeros] {'REFRESCAR clickeado.' if clickeado else 'Aviso: no pude clickear REFRESCAR.'}")
        page.wait_for_load_state("networkidle", timeout=60000)
        # POST-CONDICIÓN: que la página quedó de verdad en la fecha pedida. Sin
        # esto el reporte cae a la fecha por defecto de PGO (que es MAÑANA) y
        # los datos salen del día equivocado sin que nada lo denuncie.
        return _pgo_fecha_ok(page, fecha)
    except Exception as e:
        print(f"[sync-viajeros] Aviso: no pude fijar la fecha ({e}); leo lo que muestre el reporte.")
        return False


def _pgo_set_destino(page, destino):
    """Cambia el destino activo (PGO arranca en Torres del Paine).

    En la barra superior está el destino actual; al tocarlo se despliega la
    lista de todos (Torres del Paine, Atacama, Rapanui, …). Sin este cambio los
    reportes salen vacíos: la grilla dibuja su encabezado pero no trae filas,
    porque se consulta otro destino.
    """
    DESTINOS = ["Torres del Paine", "Atacama", "Rapanui", "Valle Sagrado",
                "Santiago", "El Chaltén", "Parque Nacional Patagonia", "Uyuni",
                "Explora Expediciones"]
    # El menú vive en el DOM desde el arranque (Bootstrap: .dropdown-menu con un
    # <a> por destino) pero está oculto hasta tocar el disparador. Por eso se
    # busca el menú primero y desde ahí se deduce el disparador, en vez de
    # adivinar el texto de la cabecera (que trae la inicial del avatar pegada).
    _JS = """
          ([dests, destino]) => {
            // OJO: el menú está oculto hasta que se lo abre, y para un elemento
            // sin layout innerText devuelve ''. Todo el matcheo va por
            // textContent, que sí trae el texto de lo oculto.
            const norm = s => (s||'').replace(/\\s+/g,' ').trim();
            const tiene = t => dests.some(d => norm(t).toLowerCase().includes(d.toLowerCase()));
            let menu = null, hits = 0;
            for (const m of document.querySelectorAll('[class*=dropdown-menu],ul,div')) {
              const items = [...m.children].filter(c => norm(c.textContent));
              if (items.length < 4) continue;
              const n = items.filter(c => tiene(c.textContent)).length;
              if (n > hits) { hits = n; menu = m; }
            }
            if (!menu || hits < 4) return {ok: false};
            // Opción buscada dentro del menú.
            const opt = [...menu.children].concat([...menu.querySelectorAll('*')])
              .find(c => norm(c.textContent).toLowerCase() === destino.toLowerCase());
            if (opt) opt.setAttribute('data-pgo-dest-opt', '1');
            // Disparador: el hermano/ancestro clickeable que abre este menú.
            let trg = menu.previousElementSibling;
            if (!trg && menu.parentElement) {
              trg = menu.parentElement.querySelector(
                '.dropdown-toggle,[data-toggle=dropdown],[aria-haspopup]');
            }
            if (trg) trg.setAttribute('data-pgo-dest-trg', '1');
            return {ok: true, hits, menuCls: (menu.className||'').slice(0,60),
                    opt: !!opt, trg: trg ? norm(trg.textContent).slice(0,40) : null,
                    items: [...menu.children].map(c => norm(c.textContent).slice(0,30))};
          }
        """
    try:
        info = {}
        for _ in range(20):        # la SPA monta la cabecera unos segundos tarde
            info = page.evaluate(_JS, [DESTINOS, destino])
            if info.get("ok"):
                break
            page.wait_for_timeout(1000)
        if not info.get("ok"):
            print("[sync-viajeros] Aviso: no encontré el menú de destinos.")
            return False
        print(f"[sync-viajeros] Menú de destinos: {info['hits']} opciones "
              f"(clase '{info['menuCls']}', disparador '{info.get('trg')}').")
        if not info.get("opt"):
            print(f"[sync-viajeros] Aviso: el menú no trae '{destino}'. "
                  f"Opciones vistas: {info.get('items')}")
            return False
        # Abrir el menú (si el disparador existe) y elegir. El click va por JS
        # porque Playwright rechaza clickear lo que aún está oculto.
        if info.get("trg"):
            page.eval_on_selector("[data-pgo-dest-trg='1']", "el => el.click()")
            page.wait_for_timeout(600)
        try:
            page.locator("[data-pgo-dest-opt='1']").first.click(timeout=4000)
        except Exception:
            page.eval_on_selector("[data-pgo-dest-opt='1']", "el => el.click()")
        page.wait_for_load_state("networkidle", timeout=60000)
        page.wait_for_timeout(1500)
        print(f"[sync-viajeros] Destino cambiado a {destino}.")
        return True
    except Exception as e:
        print(f"[sync-viajeros] Aviso: no pude cambiar el destino ({e}).")
        return False


def _pgo_structure_report(page):
    """Mapa de la estructura de la página cuando no aparece la grilla esperada.

    Sólo títulos de columna y nombres de clase — nunca datos de huéspedes.
    """
    try:
        info = page.evaluate("""
          () => {
            const norm = s => (s||'').replace(/\\s+/g,' ').trim();
            const out = {tables: [], aria: [], repes: []};
            for (const t of document.querySelectorAll('table')) {
              const tr = t.querySelector('tr');
              out.tables.push({filas: t.querySelectorAll('tr').length,
                               cls: (t.className||'').slice(0,60),
                               head: tr ? norm(tr.innerText).slice(0,120) : ''});
            }
            for (const g of document.querySelectorAll('[role=table],[role=grid]')) {
              out.aria.push({rol: g.getAttribute('role'),
                             filas: g.querySelectorAll('[role=row]').length,
                             cls: (g.className||'').slice(0,60)});
            }
            for (const el of document.querySelectorAll('div,ul,tbody')) {
              const n = el.children.length;
              if (n < 8) continue;
              const tags = new Set([...el.children].map(c => c.tagName));
              if (tags.size !== 1) continue;
              const c0 = el.children[0];
              out.repes.push({hijos: n, tag: [...tags][0],
                              cls: (el.className||'').slice(0,60),
                              muestra: norm(c0.innerText || c0.textContent).slice(0,90)});
            }
            out.repes = out.repes.sort((a,b)=>b.hijos-a.hijos).slice(0,5);
            return out;
          }
        """)
    except Exception as e:
        print(f"[sync-viajeros] (no pude mapear la estructura: {e})")
        return
    print("[sync-viajeros] --- estructura de la página ---")
    for t in info.get("tables", []):
        print(f"[sync-viajeros]   <table> filas={t['filas']} clase='{t['cls']}' encabezado='{t['head']}'")
    for g in info.get("aria", []):
        print(f"[sync-viajeros]   grilla ARIA role={g['rol']} filas={g['filas']} clase='{g['cls']}'")
    for r in info.get("repes", []):
        print(f"[sync-viajeros]   contenedor repetido <{r['tag']}> hijos={r['hijos']} "
              f"clase='{r['cls']}' 1er_hijo='{r['muestra']}'")


def _pgo_read_report(page, path, fecha, dump_name=None, kind=None, date_iso=None):
    """Abre un reporte, fija la fecha y devuelve [{encabezado_normalizado: valor}].

    `kind` (arrival/birthday) selecciona un preparador de filtros propio: esos
    reportes NO usan el input DD-MM-YYYY + REFRESCAR de los demás. Sin `kind`
    el comportamiento es exactamente el de siempre.
    """
    url = PGO_BASE_URL + path
    page.goto(url, wait_until="networkidle", timeout=60000)
    fecha_ok = True
    if kind in ("arrival", "birthday"):
        _pgo_prepare_report(page, kind, date_iso)
    elif fecha:
        fecha_ok = _pgo_set_date(page, fecha)
    else:
        _pgo_refrescar(page)
    if dump_name:
        _pgo_dump(page, dump_name)
    data = None
    for intento in range(30):                     # hasta ~30 s
        data = page.evaluate(_PGO_TABLE_JS, PGO_TABLE_SEL or None)
        if data and data.get("rows"):
            break
        page.wait_for_timeout(1000)
    if not data or not data.get("rows"):
        _pgo_structure_report(page)
        raise SystemExit(
            f"[sync-viajeros] No encontré la grilla de datos en {url}.\n"
            "  Arriba va un mapa de la estructura de la página para ajustar el"
            " extractor (o fijá PGO_TABLE_SEL con el selector correcto)."
        )
    headers = [norm_key(h) for h in data["headers"]]
    out = []
    for cells in data["rows"]:
        # fix_mojibake acá y no más abajo: es el ÚNICO punto por el que pasan
        # todas las tablas de PGO, así ningún reporte nuevo hereda el problema.
        # Además el cruce Geos↔Dietas es por nombre normalizado: si un lado
        # viniera con "PÃ©rez" y el otro con "Pérez", el viajero no cruzaría.
        out.append({headers[i]: fix_mojibake(cells[i])
                    for i in range(min(len(headers), len(cells)))})
    print(f"[sync-viajeros] {path}: {len(out)} filas · columnas: {', '.join(headers)}"
          + ("" if fecha_ok else "  ⚠ FECHA NO VERIFICADA"))
    _pgo_read_report.ultima_fecha_ok = fecha_ok
    return out


def _pgo_form_report(page, titulo):
    """Imprime la estructura del formulario de acceso en el log.

    Sólo metadatos del formulario (type/name/id/placeholder/estado) — nunca
    valores tipeados ni datos de huéspedes. Es lo que permite ajustar el login
    sin tener que bajarse el HTML.
    """
    try:
        info = page.evaluate("""
          () => {
            const vis = el => el && el.offsetParent !== null;
            const inputs = [...document.querySelectorAll('input,select,textarea')]
              .filter(vis).map(i => ({
                tag: i.tagName.toLowerCase(),
                type: (i.getAttribute('type')||'').toLowerCase(),
                name: i.getAttribute('name')||'', id: i.id||'',
                ph: i.getAttribute('placeholder')||'',
                maxlength: i.getAttribute('maxlength')||'',
                filled: !!(i.value && i.value.length)
              }));
            const btns = [...document.querySelectorAll('button,input[type=submit]')]
              .filter(vis).map(b => ({
                text: (b.innerText||b.value||'').trim().slice(0,40),
                type: (b.getAttribute('type')||'').toLowerCase(),
                disabled: !!b.disabled
              }));
            const f = document.querySelector('form');
            return {inputs, btns, action: f ? (f.getAttribute('action')||'') : '(sin <form>)'};
          }
        """)
    except Exception as e:
        print(f"[sync-viajeros] (no pude inspeccionar el formulario: {e})")
        return
    print(f"[sync-viajeros] --- {titulo} ---")
    print(f"[sync-viajeros]   form action: {info.get('action')}")
    for i in info.get("inputs", []):
        print("[sync-viajeros]   campo: tag={tag} type={type} name={name} id={id} "
              "placeholder={ph} maxlength={maxlength} con_valor={filled}".format(**i))
    for b in info.get("btns", []):
        print("[sync-viajeros]   boton: texto='{text}' type={type} deshabilitado={disabled}".format(**b))


def _pgo_type(page, selector, value):
    """Escribe en un campo como lo haría una persona.

    Los campos de RUT suelen llevar máscara (se formatean mientras se tipea) y
    esos componentes ignoran un `fill()` que asigna el valor de una sola vez.
    Por eso: click, limpiar y tipear tecla por tecla. Si aun así el campo queda
    vacío, se cae al setter nativo + eventos para que el framework se entere.
    """
    loc = page.locator(selector).first
    loc.click()
    try:
        loc.press("Control+a")
        loc.press("Delete")
    except Exception:
        pass
    loc.type(value, delay=45)
    try:
        if (loc.input_value() or "").strip():
            return
    except Exception:
        return
    print("[sync-viajeros] El campo quedó vacío al tipear; uso setter nativo.")
    loc.evaluate(
        "(el, v) => { const p = Object.getPrototypeOf(el);"
        " const d = Object.getOwnPropertyDescriptor(p, 'value');"
        " d && d.set ? d.set.call(el, v) : (el.value = v);"
        " el.dispatchEvent(new Event('input', {bubbles:true}));"
        " el.dispatchEvent(new Event('change', {bubbles:true})); }", value)


def _pgo_error_msg(page):
    """Texto de error visible tras un login fallido (ej. 'RUT inválido').

    Busca primero contenedores típicos de alerta y, si no hay, cualquier texto
    corto visible que mencione una palabra de error. Devuelve '' si no encuentra.
    """
    try:
        return page.evaluate("""
          () => {
            const vis = el => el && el.offsetParent !== null;
            const sels = ['.error','.alert','.ant-message','.ant-form-item-explain',
                          '.invalid-feedback','[role=alert]','.toast','.notification'];
            for (const s of sels) {
              const el = [...document.querySelectorAll(s)].find(vis);
              if (el && el.innerText.trim()) return el.innerText.trim().slice(0, 200);
            }
            const rx = /(incorrect|invalid|inv\\u00e1lid|err|no existe|no coincide|requerid|oblig)/i;
            const el = [...document.querySelectorAll('span,div,p,small,label')]
              .filter(vis)
              .find(e => e.children.length === 0 && rx.test(e.innerText||'')
                         && (e.innerText||'').trim().length < 160);
            return el ? el.innerText.trim() : '';
          }
        """) or ""
    except Exception:
        return ""


def _pgo_login(page):
    """Completa el formulario de acceso.

    No adivina el `name` del campo de usuario: ubica el input de CONTRASEÑA y
    toma el input de texto/email inmediatamente anterior dentro del mismo form.
    Es la estructura de cualquier login y sobrevive a cambios de nomenclatura.
    Si eso falla, cae a los selectores configurables PGO_SEL_USER.
    """
    user, pwd = os.environ["PGO_USER"], os.environ["PGO_PASS"]
    filled = page.evaluate("""
      () => {
        const pass = [...document.querySelectorAll("input[type='password']")]
                      .find(i => i.offsetParent !== null);
        if (!pass) return null;
        const scope = pass.closest('form') || document;
        const cands = [...scope.querySelectorAll("input")].filter(i =>
          i !== pass && i.offsetParent !== null &&
          ['text','email','tel',''].includes((i.getAttribute('type')||'').toLowerCase()));
        const idx = cands.findIndex(i => pass.compareDocumentPosition(i) & Node.DOCUMENT_POSITION_PRECEDING);
        const u = idx >= 0 ? cands[cands.length - 1] : (cands[0] || null);
        if (!u) return null;
        return {name: u.getAttribute('name') || '', id: u.id || '',
                ph: u.getAttribute('placeholder') || ''};
      }
    """)
    if filled:
        desc = filled.get("name") or filled.get("id") or filled.get("ph") or "(sin nombre)"
        print(f"[sync-viajeros] Campo de usuario detectado: {desc}")
        sel = (f"input#{filled['id']}" if filled.get("id")
               else (f"input[name='{filled['name']}']" if filled.get("name")
                     else "input:not([type='password'])"))
    else:
        sel = PGO_SEL_USER
    _pgo_type(page, sel, user)
    _pgo_type(page, PGO_SEL_PASS, pwd)
    # Enviar: botón de submit si existe, si no Enter en la contraseña.
    btn = page.locator(PGO_SEL_SUBMIT)
    if btn.count() > 0:
        btn.first.click()
    else:
        page.keyboard.press("Enter")


def _pgo_logged_in(page):
    """Heurística: si hay un campo de contraseña VISIBLE, no hay sesión.

    Ojo con las SPA: al loguearse suelen ocultar el formulario sin sacarlo del
    DOM, así que contar los inputs no alcanza — hay que mirar visibilidad
    (offsetParent nulo = oculto por display:none en él o en algún ancestro).
    """
    try:
        return not page.evaluate(
            "() => [...document.querySelectorAll(\"input[type='password']\")]"
            "        .some(i => i.offsetParent !== null)"
        )
    except Exception:
        return True


# ── Descubrimiento de reportes nuevos (--explore) ────────────────────────────
# Calibrar un extractor a ciegas cuesta una corrida de CI por suposición (§4.1
# de ARCHITECTURE). Esto imprime lo justo para acertar a la primera: qué
# columnas trae cada reporte y con QUÉ FORMATO vienen los valores.
#
# Privacidad: las letras se enmascaran con 'x' y sólo sobreviven dígitos y
# puntuación — que es exactamente lo que hace falta para leer un formato.
# "Chenjie Yuan" → "xxxxxxx xxxx"; "14:30" y "31-08-2026" quedan intactos.
_MOJIBAKE = re.compile(r"[ÃÂ][\x80-\xbf©®¡¿]|Ã©|Ã±|Ãº|Ã¡|Ã³")


# Tokens que NO son datos personales y sí son necesarios para entender la
# columna: sin esto "IN 09:45" salía como "xx 09:45" y no se sabía si la hora
# era de entrada o de salida.
_SAFE_TOKENS = {"IN", "OUT", "AM", "PM", "DT", "DR", "NO", "SI", "N/A", "-", "OK",
                "CI", "CO", "IN/OUT", "ADT", "CHD", "PAX", "VIP"}


def _mask_value(v):
    """Enmascara letras, conserva dígitos, símbolos y tokens estructurales."""
    def _tok(m):
        w = m.group(0)
        return w if w.upper() in _SAFE_TOKENS else re.sub(r"[^\W\d_]", "x", w, flags=re.UNICODE)
    return re.sub(r"[^\W\d_]+", _tok, str(v or ""), flags=re.UNICODE)


def _pgo_profile(nombre, rows, muestras=3):
    """Imprime columnas + formato enmascarado + señales de mojibake."""
    if not rows:
        print(f"[explore] {nombre}: 0 filas")
        return
    cols = list(rows[0].keys())
    print(f"[explore] ── {nombre}: {len(rows)} filas · {len(cols)} columnas ──")
    for c in cols:
        vals = [r.get(c, "") for r in rows if str(r.get(c, "")).strip()]
        ejemplos = " | ".join(_mask_value(v)[:26] for v in vals[:muestras]) or "(vacía)"
        # Señales útiles para el mapeo: ¿hay horas? ¿fechas? ¿mojibake?
        marcas = []
        if any(re.search(r"\d{1,2}:\d{2}", str(v)) for v in vals):  marcas.append("HORA")
        if any(re.search(r"\d{1,2}[-/]\d{1,2}", str(v)) for v in vals): marcas.append("FECHA")
        n_moji = sum(1 for v in vals if _MOJIBAKE.search(str(v)))
        if n_moji: marcas.append(f"MOJIBAKE×{n_moji}")
        tag = ("  ← " + " ".join(marcas)) if marcas else ""
        print(f"[explore]   {c!r:34} llenas={len(vals):>3}  {ejemplos}{tag}")


def _pgo_click_text(page, *textos):
    """Click en el primer botón visible cuyo texto coincida (case-insensitive)."""
    for txt in textos:
        try:
            btn = page.get_by_role("button", name=re.compile(txt, re.I)).first
            if btn and btn.is_visible():
                btn.click()
                print(f"[sync-viajeros] Botón '{txt}' clickeado.")
                return True
        except Exception:
            pass
    return False


def _pgo_fill_inputs(page, selector, valores):
    """Tipea valores en inputs de Element UI, tecla por tecla.

    fill() setea el valor de una sola vez y los componentes de Element UI lo
    descartan (misma trampa que el RUT del login, §4.1). Además cada campo se
    confirma con Enter, que es lo que cierra el panel del date-picker.
    """
    campos = page.query_selector_all(selector)
    if not campos:
        return 0
    n = 0
    for el, val in zip(campos, valores):
        try:
            el.click()
            page.wait_for_timeout(150)
            try:
                el.fill("")
            except Exception:
                el.press("Control+a")
            el.type(val, delay=45)
            page.wait_for_timeout(120)
            el.press("Enter")
            page.wait_for_timeout(250)
            n += 1
        except Exception as e:
            print(f"[sync-viajeros] (no pude escribir '{val}' en {selector}: {type(e).__name__})")
    return n


def _pgo_close_overlay(page):
    """Cierra el panel flotante del date-picker de Element UI.

    Si queda abierto tapa la grilla y, peor, sobrevive a la navegación: el
    reporte SIGUIENTE hereda el overlay y su propio click de fecha expira.
    """
    for _ in range(3):
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(150)
            if not page.query_selector(".el-picker-panel:not([style*='display: none'])"):
                return True
            page.mouse.click(5, 5)          # click fuera de cualquier panel
            page.wait_for_timeout(200)
        except Exception:
            break
    return False


def _pgo_fill_range(page, desde, hasta):
    """Range-picker de Element UI: los dos extremos en UNA sola interacción.

    Clickear cada input por separado reabre el panel y descarta lo tipeado. El
    flujo que funciona es: click en el primero, tipear, Enter (el foco salta al
    segundo), tipear, Enter, y recién ahí cerrar el panel.
    """
    campos = page.query_selector_all(".el-range-input")
    if len(campos) < 2:
        return 0
    try:
        campos[0].click()
        page.wait_for_timeout(250)
        for el, val in ((campos[0], desde), (campos[1], hasta)):
            try:
                el.fill("")
            except Exception:
                el.press("Control+a")
            el.type(val, delay=45)
            page.wait_for_timeout(150)
            el.press("Enter")
            page.wait_for_timeout(350)
    except Exception as e:
        print(f"[sync-viajeros] (range-picker: {type(e).__name__}: {e})")
        return 0
    _pgo_close_overlay(page)
    return 2


def _pgo_prepare_report(page, kind, date_str):
    """Prepara los filtros propios de cada reporte nuevo.

    Ninguno usa el patrón de _pgo_set_date (input DD-MM-YYYY + REFRESCAR):
      · arrival  → date-picker de RANGO (.el-range-input), formato DD-MM-YYYY
      · birthday → dos inputs de MES (.el-input__inner), formato MM-YYYY
      · comedor  → el de siempre; lo maneja _pgo_read_report
    """
    d = datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()
    if kind == "arrival":
        # Rango que cubre a los in-house: llegadas de los últimos días y las de
        # hoy. El check-out puede caer bastante más adelante que el rango.
        desde = (d - datetime.timedelta(days=PGO_ARRIVAL_BACK)).strftime("%d-%m-%Y")
        hasta = (d + datetime.timedelta(days=PGO_ARRIVAL_FWD)).strftime("%d-%m-%Y")
        n = _pgo_fill_range(page, desde, hasta)
        print(f"[sync-viajeros] arrival: rango {desde} → {hasta} ({n} campos escritos)")
    elif kind == "birthday":
        mes = d.strftime("%m-%Y")
        n = _pgo_fill_inputs(page, ".el-input__inner", [mes, mes])
        print(f"[sync-viajeros] birthday: mes {mes} ({n} campos escritos)")
    else:
        return
    _pgo_click_text(page, "buscar", "refrescar", "consultar")
    # El panel del picker sobrevive a la navegación y rompe el reporte
    # siguiente: cerrarlo SIEMPRE, aunque este reporte ya haya cargado.
    _pgo_close_overlay(page)
    page.wait_for_timeout(1200)


_SECRET_KEY_RX = re.compile(r"token|auth|password|clave|secret|jwt|apikey|api_key|bearer", re.I)


def _shape(obj, depth=0, max_depth=4):
    """Esqueleto de un JSON: claves y TIPOS, nunca valores.

    Es lo que permite entender la forma de una respuesta de la API sin volcar
    datos de huéspedes al log de CI. De las listas describe sólo el 1er ítem.
    """
    pad = "  " * depth
    if depth >= max_depth:
        return f"{pad}…"
    if isinstance(obj, dict):
        if not obj:
            return f"{pad}{{}}"
        out = []
        for k, v in list(obj.items())[:25]:
            if isinstance(v, (dict, list)):
                out.append(f"{pad}{k}:\n{_shape(v, depth + 1, max_depth)}")
            else:
                out.append(f"{pad}{k}: <{type(v).__name__}>")
        return "\n".join(out)
    if isinstance(obj, list):
        return f"{pad}[{len(obj)} ítems]" + (f"\n{_shape(obj[0], depth + 1, max_depth)}" if obj else "")
    return f"{pad}<{type(obj).__name__}>"


def _redact(s, limit=1200):
    """Enmascara valores de claves sensibles en un cuerpo de request."""
    s = str(s or "")
    s = re.sub(r'("(?:[^"]*(?:token|auth|password|clave|secret|jwt|key)[^"]*)"\s*:\s*")[^"]*',
               r"\1***", s, flags=re.I)
    return s[:limit] + ("…" if len(s) > limit else "")


def pgo_api_probe(page, api_calls):
    """Registra los POST a la API de PGO: query enviada + forma de la respuesta."""
    def _on_resp(resp):
        try:
            req = resp.request
            if req.resource_type not in ("xhr", "fetch"):
                return
            if "backend.pgo-explora.com" not in resp.url:
                return
            entry = {"pagina": page.url.rstrip("/").split("/")[-1] or "?",
                     "url": resp.url, "metodo": req.method, "status": resp.status,
                     "req": _redact(req.post_data), "shape": None}
            try:
                entry["shape"] = _shape(resp.json())
            except Exception:
                entry["shape"] = "(respuesta no-JSON)"
            api_calls.append(entry)
        except Exception:
            pass
    page.on("response", _on_resp)


def pgo_graphql(page, query, variables=None, endpoint="/api/"):
    """Ejecuta GraphQL desde el contexto de la página YA autenticada.

    Hacerlo con page.evaluate (y no con requests) es lo que evita reimplementar
    el login: el fetch sale del propio origen, heredando cookies y headers de
    la sesión que Playwright ya abrió.
    """
    return page.evaluate(
        """async ([url, q, v]) => {
             const r = await fetch(url, {
               method: 'POST',
               headers: {'Content-Type': 'application/json'},
               credentials: 'include',
               body: JSON.stringify({query: q, variables: v || {}})
             });
             try { return await r.json(); } catch(e) { return {error: 'no-json', status: r.status}; }
           }""",
        ["https://backend.pgo-explora.com" + endpoint, query, variables or {}])


# Palabras por las que vale la pena filtrar el esquema: lo que buscamos son las
# queries de llegadas/salidas, comedor y cumpleaños.
_GQL_INTERES = re.compile(
    r"arriv|llegad|checkin|check_in|checkout|check_out|inout|in_out|depart|salid|"
    r"birth|cumple|comedor|dining|meal|food|breakfast|desayun|lunch|almuerz|dinner|cena|"
    r"reserv|traveller|traveler|viajer|room|hab|occupancy|stay", re.I)


def pgo_introspect(page):
    """Lista las queries del esquema GraphQL de PGO (nombres y argumentos).

    Es lo que reemplaza a adivinar: en vez de probar selectores o nombres de
    query a ciegas, el propio backend dice qué existe y qué argumentos toma.
    """
    q = """{ __schema { queryType { name fields {
              name
              args { name type { name kind ofType { name kind } } }
              type { name kind ofType { name kind } }
            } } } }"""
    try:
        data = pgo_graphql(page, q)
    except Exception as e:
        print(f"[explore] introspección: fallo al consultar ({type(e).__name__}: {e})")
        return
    if not isinstance(data, dict) or not data.get("data", {}).get("__schema"):
        print(f"[explore] introspección no disponible. Respuesta: {str(data)[:300]}")
        return
    fields = data["data"]["__schema"]["queryType"]["fields"] or []
    print(f"\n[explore] === Esquema GraphQL: {len(fields)} queries ===")

    def _tname(t):
        if not t:
            return "?"
        return t.get("name") or (t.get("ofType") or {}).get("name") or t.get("kind") or "?"

    relevantes = [f for f in fields if _GQL_INTERES.search(f["name"])]
    print(f"[explore] --- {len(relevantes)} relacionadas con llegadas/comedor/viajeros ---")
    for f in sorted(relevantes, key=lambda x: x["name"]):
        args = ", ".join(f"{a['name']}: {_tname(a.get('type'))}" for a in (f.get("args") or []))
        print(f"[explore]   {f['name']}({args}) -> {_tname(f.get('type'))}")
    print("[explore] --- resto (sólo nombres) ---")
    otros = sorted(f["name"] for f in fields if f not in relevantes)
    for i in range(0, len(otros), 6):
        print("[explore]   " + " · ".join(otros[i:i + 6]))


# Tipos cuya forma hay que conocer para mapear los reportes nuevos. Los
# anidados (TypeTravellerIn, DetailType…) los descubre la recursión sola.
PGO_TYPES_INTERES = [
    "TypeTravellersInOut", "ReportDinningRoomType", "BirthdayReportType",
    "LuchOutType",
]
# ReservationType tiene 135 campos: se filtra a lo que sirve para horas,
# habitación, fechas y pax, o el log se vuelve ilegible.
PGO_TYPES_GRANDES = ["ReservationType", "TravellerType"]
_GQL_CAMPO_INTERES = re.compile(
    r"hour|time|hora|arriv|llegad|checkin|check_in|checkout|check_out|in$|out$|"
    r"date|fecha|room|hab|pax|adult|child|niñ|nino|name|nombre|nationality|nacional|"
    r"age|edad|group|grupo|status|estado|meal|comida|diet|breakfast|lunch|dinner", re.I)


def _gql_tname(t, depth=0):
    """Nombre legible de un tipo GraphQL, desenvolviendo NON_NULL/LIST."""
    if not t or depth > 4:
        return "?"
    n = t.get("name")
    if n:
        return n
    k = t.get("kind") or "?"
    inner = _gql_tname(t.get("ofType"), depth + 1)
    return f"[{inner}]" if k == "LIST" else (f"{inner}!" if k == "NON_NULL" else inner)


_GQL_ESCALARES = {"String", "Int", "Float", "Boolean", "ID", "Date", "DateTime",
                  "Time", "JSONString", "Decimal", "UUID"}


def pgo_introspect_types(page, nombres, max_depth=2, _vistos=None, _depth=0, _filtro=None):
    """Campos de cada tipo, siguiendo los tipos anidados de forma RECURSIVA.

    Sin recursión haría falta una corrida de CI por nivel: TypeTravellersInOut
    apunta a TypeTravellerIn, que es donde viven las horas. Sólo esquema —
    nombres y tipos de campo, jamás valores.

    `_filtro` recorta los tipos gigantes (ReservationType tiene 135 campos) a lo
    que de verdad importa, para que el log siga siendo legible.
    """
    vistos = _vistos if _vistos is not None else set()
    pendientes = []
    for nom in nombres:
        if not nom or nom in vistos or nom in _GQL_ESCALARES:
            continue
        vistos.add(nom)
        q = ('{ __type(name: "%s") { name kind fields { name type '
             '{ name kind ofType { name kind ofType { name kind } } } } } }' % nom)
        try:
            t = (pgo_graphql(page, q).get("data") or {}).get("__type")
        except Exception as e:
            print(f"[explore] tipo {nom}: error {type(e).__name__}")
            continue
        if not t:
            print(f"[explore] tipo {nom}: no existe en el esquema")
            continue
        campos = t.get("fields") or []
        campos_m = [f for f in campos if not _filtro or _filtro.search(f["name"])]
        recorte = f" (mostrando {len(campos_m)} de {len(campos)})" if len(campos_m) != len(campos) else ""
        print(f"\n[explore] === {t['name']} ({t.get('kind')}) · {len(campos)} campos{recorte} ===")
        for f in campos_m:
            tn = _gql_tname(f.get("type"))
            print(f"[explore]   {f['name']:34} {tn}")
            base = tn.strip("[]!")
            if base not in _GQL_ESCALARES and base not in vistos:
                pendientes.append(base)
    if pendientes and _depth < max_depth:
        pgo_introspect_types(page, pendientes, max_depth, vistos, _depth + 1, _filtro)


def pgo_resolve_hotel(page):
    """Lista los hoteles con su id y código.

    El dashboard pide hotelId 1 y arrival-report pide 2: consultar con el id
    equivocado devuelve datos válidos DE OTRO LODGE, y eso no se nota mirando.
    Nombres de hotel — no hay datos personales acá.
    """
    try:
        data = pgo_graphql(page, "{ hotelsList { id code name } defaultHotelSelected }")
        d = data.get("data") or {}
    except Exception as e:
        print(f"[explore] hotelsList: error {type(e).__name__}: {e}")
        return
    print(f"\n[explore] === Hoteles (defaultHotelSelected={d.get('defaultHotelSelected')}) ===")
    for h in (d.get("hotelsList") or []):
        marca = "  ← ATACAMA" if "atacama" in str(h.get("name", "")).lower() else ""
        print(f"[explore]   id={h.get('id'):>3}  code={h.get('code'):<8} {h.get('name')}{marca}")


# ── Horas de movimiento (GraphQL) ────────────────────────────────────────────
# Qué hora manda para decir que alguien "ya no está": la del TRANSPORTE, no la
# del checkout. El checkout es administrativo (mediodía nominal); lo que corta
# de verdad el consumo en el comedor es cuándo se suben a la van. Decisión del
# owner (2026-08-16). Cuando no hay transporte registrado se cae al checkout, y
# si tampoco hay, al borde del día — nunca se inventa una hora intermedia.
_INOUT_FIELDS = """
  room checkin checkout guestCount confirmationNumber
  arrivalTransportDatetime departureTransportDatetime
  arrivalTransportCarrier arrivalTransportId
  departureTransportCarrier departureTransportId
  arrivalStatus departureStatus
"""


def _vuelo(carrier, num):
    """'LA' + '147' -> 'LA 147'. En transporte terrestre PGO repite el mismo
    código en los dos campos (TUYU/TUYU), y ahí se colapsa a uno solo."""
    c, n = str(carrier or "").strip(), str(num or "").strip()
    if c and n and c != n:
        return f"{c} {n}"
    return c or n


def _iso_dt(v):
    """Normaliza los formatos de fecha-hora de PGO a 'YYYY-MM-DDTHH:MM' o ''."""
    s = str(v or "").strip()
    if not s or s.lower() in ("none", "null"):
        return ""
    s = s.replace("/", "-")
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})[T ]?(\d{2}):(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}T{m.group(4)}:{m.group(5)}"
    m = re.search(r"(\d{1,2})-(\d{1,2})-(\d{4})[T ]?(\d{2}):(\d{2})", s)   # DD-MM-YYYY
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}T{m.group(4)}:{m.group(5)}"
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)                           # sólo fecha
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return ""


# ── Reporte de comedor ───────────────────────────────────────────────────────
# Agrupa a los in-house por grupo de reserva y dice cuántos cubiertos hay por
# servicio. dt = desayuno TEMPRANO (excursión o vuelo antes de que abra el
# comedor), dr = desayuno REGULAR; los desayunos son dt + dr. Confirmado por el
# owner (2026-08-16).
PGO_COMEDOR_COLS = {
    "grupo": "grupo", "habitaciones": "habs", "habitacion": "habs",
    "n": "n", "pax": "n",
    "am in/out": "mov", "in/out": "mov",
    "dt": "dt", "dr": "dr",
    "almuerzos": "almuerzos", "almuerzo": "almuerzos",
    "cena": "cena", "cenas": "cena",
    "observaciones": "obs", "observacion": "obs",
}


def fix_mojibake(s):
    """Repara UTF-8 servido como latin-1: 'PÃ©rez' → 'Pérez'.

    PGO lo hace en varios reportes. Importa porque estos textos se muestran en
    la app, y porque cualquier cruce por nombre falla si un lado viene torcido.
    Si el round-trip no es reversible se devuelve el original: nunca se empeora.
    """
    t = str(s or "")
    if not _MOJIBAKE.search(t):
        return t
    try:
        arreglado = t.encode("latin-1").decode("utf-8")
        return arreglado if arreglado and "�" not in arreglado else t
    except (UnicodeEncodeError, UnicodeDecodeError):
        return t


PGO_CUMPLE_COLS = {
    "nombre viajero": "nombre", "nombre": "nombre", "viajero": "nombre",
    "cumpleanos": "cumple", "cumpleaños": "cumple", "fecha": "cumple",
    "habitacion": "hab", "habitación": "hab",
    "n confirmacion": "conf", "n confirmación": "conf",
}


def parse_birthday(rows):
    """Reporte de cumpleaños → {nombre_normalizado: 'DD-MM'}.

    El cruce va por NOMBRE y no por habitación: el reporte trae el mes entero
    (gente que ya se fue o todavía no llega) y una de cada cinco filas viene
    sin habitación. Con el mojibake ya reparado en _pgo_read_report, los
    nombres de los dos reportes normalizan igual.
    """
    out = {}
    for raw in rows:
        r = _remap(raw, PGO_CUMPLE_COLS)
        nombre = (r.get("nombre") or "").strip()
        m = re.search(r"(\d{1,2})[-/](\d{1,2})", str(r.get("cumple") or ""))
        if not nombre or not m:
            continue
        out[norm_key(nombre)] = f"{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return out


def parse_comedor(rows):
    """Filas del reporte → grupos + totales por servicio."""
    grupos, tot = [], {"dt": 0, "dr": 0, "almuerzos": 0, "cena": 0, "n": 0}
    for raw in rows:
        r = _remap(raw, PGO_COMEDOR_COLS)
        n = _to_int(r.get("n"))
        if not n and not (r.get("grupo") or r.get("habs")):
            continue
        habs = [h.zfill(2) for h in re.findall(r"\d+", str(r.get("habs") or ""))]
        g = {
            "grupo": fix_mojibake(r.get("grupo")).strip(),
            "habs":  habs,
            "n":     n,
            "dt":    _to_int(r.get("dt")),
            "dr":    _to_int(r.get("dr")),
            "almuerzos": _to_int(r.get("almuerzos")),
            "cena":  _to_int(r.get("cena")),
        }
        mov = str(r.get("mov") or "").strip()
        if mov:
            g["mov"] = mov            # "IN 09:45" — hora PLANIFICADA, redondeada
        obs = fix_mojibake(r.get("obs")).strip()
        if obs:
            g["obs"] = obs
        for k in ("dt", "dr", "almuerzos", "cena", "n"):
            tot[k] += g[k] if k != "n" else n
        grupos.append(g)
    tot["desayunos"] = tot["dt"] + tot["dr"]
    return {"grupos": grupos, "totales": tot}


def pgo_probe_arrival(page, date_str):
    """¿Qué campo marca la llegada AL LODGE y no la salida del vuelo?

    'arrivalTransportDatetime' puede ser la hora en que el transporte recoge en
    Calama — y de Calama a San Pedro hay más de una hora. Contar a alguien que
    todavía va en la ruta infla el almuerzo. Esta sonda lista todos los campos
    de hora del tipo y muestra sus valores para poder compararlos entre sí.
    Sólo horas, nunca ligadas a un nombre.
    """
    for tipo, lista in (("TypeTravellerIn", "travellerIn"), ("TypeTravellerOut", "travellerOut")):
        _probe_tipo(page, date_str, tipo, lista)


def _probe_tipo(page, date_str, tipo, lista):
    q = """{ __type(name: "%s") { fields { name type { name kind ofType { name } } } } }""" % tipo
    try:
        res = pgo_graphql(page, q)
        campos = [f["name"] for f in
                  (((res.get("data") or {}).get("__type") or {}).get("fields") or [])]
    except Exception as e:
        print(f"[probe] no pude introspeccionar {tipo}: {e}")
        return
    if not campos:
        print(f"[probe] {tipo}: sin campos (¿el tipo no existe?)")
        return
    print(f"\n[probe] ══ {tipo} ══")
    rx = re.compile(r"arriv|depart|checkin|checkout|check_in|check_out|transport|flight|hour|hora|time|datetime|llegad|salid|ingres", re.I)
    cand = [c for c in campos if rx.search(c)]
    print(f"[probe] {tipo}: {len(campos)} campos · {len(cand)} candidatos de hora")
    print(f"[probe] candidatos: {cand}")
    if not cand:
        return
    # Pedirlos todos juntos: si uno no es escalar, GraphQL lo dice y se descarta.
    sel = " ".join(cand)
    q2 = """query ($hotelId: ID!, $date: Date!) {
              reportInOut(hotelId: $hotelId, date: $date) { %s { room %s } }
            }""" % (lista, sel)
    try:
        res2 = pgo_graphql(page, q2, {"hotelId": str(PGO_HOTEL_ID), "date": date_str})
    except Exception as e:
        print(f"[probe] la query ampliada falló: {e}")
        return
    if res2.get("errors"):
        print(f"[probe] errores (campos no escalares se descartan): {str(res2['errors'])[:400]}")
    filas = (((res2.get("data") or {}).get("reportInOut") or {}).get(lista) or [])
    print(f"[probe] {len(filas)} filas en {lista}. Valores por campo (sin habitación):")
    for c in cand:
        vals = [str(r.get(c)) for r in filas if r.get(c) not in (None, "", "None")]
        if vals:
            print(f"[probe]   {c:34} {len(vals):>2} con dato · {vals[:4]}")
        else:
            print(f"[probe]   {c:34}  0 con dato")


def pgo_fetch_inout(page, date_str):
    """reportInOut del día → {hab: {inAt, outAt, ...}} con HORAS reales.

    Se cruza por HABITACIÓN, no por nombre: el movimiento es de la reserva
    (todos los de una hab suben a la misma van), y cruzar por nombre es
    justo lo que rompe el mojibake de PGO.
    """
    q = """query ($hotelId: ID!, $date: Date!) {
             reportInOut(hotelId: $hotelId, date: $date) {
               cantTravellerIn cantTravellerOut cantTravellerTodayNight
               travellerIn { %s }
               travellerOut { %s }
             }
           }""" % (_INOUT_FIELDS, _INOUT_FIELDS)
    try:
        res = pgo_graphql(page, q, {"hotelId": str(PGO_HOTEL_ID), "date": date_str})
    except Exception as e:
        print(f"[sync-viajeros] reportInOut: no se pudo consultar ({type(e).__name__}: {e})")
        return {}, {}
    if res.get("errors"):
        print(f"[sync-viajeros] reportInOut devolvió errores: {str(res['errors'])[:300]}")
    data = (res.get("data") or {}).get("reportInOut") or {}
    if not data:
        return {}, {}
    tot = {k: data.get(k) for k in ("cantTravellerIn", "cantTravellerOut", "cantTravellerTodayNight")}
    horas = {}
    for clave, lista in (("in", data.get("travellerIn") or []),
                         ("out", data.get("travellerOut") or [])):
        for r in lista:
            hab_raw = str(r.get("room") or "").strip()
            hab = re.sub(r"\D", "", hab_raw).zfill(2) if re.search(r"\d", hab_raw) else hab_raw
            if not hab:
                continue
            e = horas.setdefault(hab, {})
            # checkin/checkout son las horas en el LODGE; los *TransportDatetime
            # son los VUELOS en Calama (verificado con la sonda: LA 144 aterriza
            # 07:07 y el checkin es 09:55; un checkout de 08:00 vuela 11:11).
            # Contar por el vuelo sumaría gente que va en la ruta y descontaría
            # a quien todavía está desayunando acá.
            if clave == "in":
                e["inAt"]  = _iso_dt(r.get("checkin"))
                e["inSrc"] = "checkin"
                vuelo = _iso_dt(r.get("arrivalTransportDatetime"))
                if vuelo:
                    e["inFlightAt"] = vuelo          # informativo: "viene volando"
                    e["inFlight"] = _vuelo(r.get("arrivalTransportCarrier"),
                                           r.get("arrivalTransportId"))
            else:
                e["outAt"]  = _iso_dt(r.get("checkout"))
                e["outSrc"] = "checkout"
                vuelo = _iso_dt(r.get("departureTransportDatetime"))
                if vuelo:
                    e["outFlightAt"] = vuelo
                    e["outFlight"] = _vuelo(r.get("departureTransportCarrier"),
                                            r.get("departureTransportId"))
    print(f"[sync-viajeros] reportInOut: {tot} · {len(horas)} habitaciones con movimiento")
    return horas, tot


def pgo_probe_roster(page, date_str):
    """¿Puede la API reemplazar al scraping del Reporte Geos?

    No basta con que exista una query: tiene que devolver EL MISMO roster. Esta
    sonda busca las queries candidatas, muestra sus argumentos y campos, y pide
    los datos para poder contrastarlos contra las filas del HTML.
    """
    # 1) qué queries hay que huelan a roster de in-house
    q = """{ __schema { queryType { fields {
              name
              args { name type { name kind ofType { name kind } } }
              type { name kind ofType { name kind } }
            } } } }"""
    try:
        res = pgo_graphql(page, q)
        fields = (((res.get("data") or {}).get("__schema") or {}).get("queryType") or {}).get("fields") or []
    except Exception as e:
        print(f"[roster] no pude introspeccionar el schema: {e}")
        return
    rx = re.compile(r"inhouse|in_house|traveller|guest|huesped|roster|reservation", re.I)
    cand = [f for f in fields if rx.search(f["name"])]
    print(f"[roster] {len(fields)} queries en el schema · {len(cand)} candidatas:")
    for f in cand:
        args = ", ".join(f"{a['name']}: {(a['type'].get('name') or (a['type'].get('ofType') or {}).get('name') or a['type'].get('kind'))}"
                         for a in (f.get("args") or []))
        t = f.get("type") or {}
        tn = t.get("name") or (t.get("ofType") or {}).get("name") or t.get("kind")
        print(f"[roster]   {f['name']}({args}) -> {tn}")

    # 2) los campos de ReservationType, que es lo que devuelve travellersInhouse
    q2 = """{ __type(name: "ReservationType") { fields { name
              type { name kind ofType { name kind } } } } }"""
    try:
        r2 = pgo_graphql(page, q2)
        campos = (((r2.get("data") or {}).get("__type") or {}).get("fields") or [])
    except Exception as e:
        print(f"[roster] no pude leer ReservationType: {e}")
        return
    escalares, objetos = [], []
    for c in campos:
        t = c["type"]; kind = t.get("kind"); nom = t.get("name") or (t.get("ofType") or {}).get("name")
        k2 = (t.get("ofType") or {}).get("kind") or kind
        (objetos if k2 in ("OBJECT", "LIST") or (nom or "").endswith("Type") else escalares).append(c["name"])
    print(f"[roster] ReservationType: {len(campos)} campos · {len(escalares)} escalares")
    print(f"[roster]   escalares: {escalares}")
    print(f"[roster]   anidados : {objetos}")

    # 3) pedir el roster real y contar, para contrastarlo con el HTML
    rx_util = re.compile(r"room|habit|name|nombre|age|edad|nationality|nac|group|grupo|checkin|checkout|status|confirmation|pax|guest|diet|obs|comment", re.I)
    sel = [c for c in escalares if rx_util.search(c)] or escalares[:20]
    q3 = """query ($hotelId: Int!, $date: Date!) {
              travellersInhouse(hotelId: $hotelId, date: $date) { %s }
            }""" % " ".join(sel)
    try:
        r3 = pgo_graphql(page, q3, {"hotelId": PGO_HOTEL_ID, "date": date_str})
    except Exception as e:
        print(f"[roster] la query falló: {e}")
        return
    if r3.get("errors"):
        print(f"[roster] errores: {str(r3['errors'])[:400]}")
    filas = (r3.get("data") or {}).get("travellersInhouse") or []
    print(f"[roster] travellersInhouse devolvió {len(filas)} filas (campos pedidos: {sel})")
    for c in sel:
        vals = [str(f.get(c)) for f in filas if f.get(c) not in (None, "", "None")]
        if vals:
            print(f"[roster]   {c:26} {len(vals):>3} con dato · {[_mask_value(v)[:22] for v in vals[:3]]}")


# Campos del roster por API. La reserva manda hab y fechas; la persona, sus
# datos. Las observaciones NO salen de acá: medido el 2026-08-17, los campos de
# dieta de la API traen 4-5 casos contra 9 del reporte HTML — migrarlas perdería
# restricciones. Ver §4.2.
PGO_ROSTER_QUERY = """query ($hotelId: Int!, $date: Date!) {
  travellersInhouse(hotelId: $hotelId, date: $date) {
    room checkin checkout
    traveller { firstName lastName age nationality nationalityName group }
  }
}"""


def pgo_fetch_roster(page, date_str):
    """Roster de in-house por GraphQL → filas en el formato de SEED_ROWS.

    Reemplaza al scraping del Reporte Geos. Verificado contra el HTML nombre por
    nombre y habitación por habitación: 70/70 idénticos (§4.2).
    """
    res = pgo_graphql(page, PGO_ROSTER_QUERY, {"hotelId": PGO_HOTEL_ID, "date": date_str})
    if res.get("errors"):
        print(f"[roster] errores: {str(res['errors'])[:300]}")
    filas = (res.get("data") or {}).get("travellersInhouse") or []
    out = []
    for f in filas:
        hab_raw = str(f.get("room") or "")
        digits = re.sub(r"\D", "", hab_raw)
        hab = digits.zfill(2) if digits else hab_raw.strip()
        ind  = _iso_dt(f.get("checkin"))[:10]
        outd = _iso_dt(f.get("checkout"))[:10]
        t = f.get("traveller")
        for tr in (t if isinstance(t, list) else [t]):
            if not isinstance(tr, dict):
                continue
            nombre = " ".join(str(tr.get(k) or "").strip()
                              for k in ("firstName", "lastName")).strip()
            if not nombre:
                continue
            out.append((hab, fix_mojibake(nombre), _to_int(tr.get("age")),
                        str(tr.get("nationality") or "").strip().upper(),
                        str(tr.get("group") or "").strip(), ind, outd, ""))
    print(f"[sync-viajeros] roster (API): {len(out)} viajeros en {len({r[0] for r in out})} habitaciones")
    return out


def pgo_compara_roster(api_rows, html_rows):
    """Compara las filas de las dos vías, campo por campo. Sólo diagnóstico."""
    def key(r): return norm_key(r[1])
    A = {key(r): r for r in api_rows}
    H = {key(r): r for r in html_rows}
    print(f"[cmp] API {len(api_rows)} filas · HTML {len(html_rows)} filas")
    print(f"[cmp] sólo API: {len(set(A)-set(H))} · sólo HTML: {len(set(H)-set(A))}")
    campos = ["hab", "nombre", "edad", "nac", "grupo", "in", "out"]
    difs = {c: 0 for c in campos}
    ejemplos = {}
    for k in set(A) & set(H):
        for i, c in enumerate(campos):
            a, h = A[k][i], H[k][i]
            if str(a).strip() != str(h).strip():
                difs[c] += 1
                ejemplos.setdefault(c, (str(a)[:24], str(h)[:24]))
    for c in campos:
        ej = f"  ej API={ejemplos[c][0]!r} HTML={ejemplos[c][1]!r}" if c in ejemplos else ""
        print(f"[cmp]   {c:8} difieren en {difs[c]:>3} de {len(set(A)&set(H))}{ej}")
    return difs


def pgo_probe_dietas(page, date_str, dietas_rows=None):
    """¿Los campos de dieta de TravellerType vienen poblados?

    Hoy las restricciones salen de parsear texto libre del reporte de Dietas con
    regex. Si estos campos traen el dato ESTRUCTURADO por persona, se deja de
    adivinar. Perfila cobertura y forma; el contenido va enmascarado salvo los
    booleanos y los códigos cortos, que es lo que define si sirven.
    """
    CAMPOS = ["hasFoodReq", "dietReq", "dietReqObs", "foodRestrictions",
              "hasMedicalReq", "healthCondition", "otherMedicalConditions",
              "medReqObs", "observation", "allConditionsHtml"]
    q = """query ($hotelId: Int!, $date: Date!) {
             travellersInhouse(hotelId: $hotelId, date: $date) {
               room traveller { firstName %s }
             }
           }""" % " ".join(CAMPOS)
    try:
        r = pgo_graphql(page, q, {"hotelId": PGO_HOTEL_ID, "date": date_str})
    except Exception as e:
        print(f"[dietas] la query falló: {e}"); return
    if r.get("errors"):
        print(f"[dietas] errores: {str(r['errors'])[:400]}")
    filas = (r.get("data") or {}).get("travellersInhouse") or []
    pers = []
    for f in filas:
        t = f.get("traveller")
        for tr in (t if isinstance(t, list) else [t]):
            if isinstance(tr, dict): pers.append(tr)
    print(f"[dietas] ══ {len(pers)} personas ══")
    for c in CAMPOS:
        vals = [tr.get(c) for tr in pers if tr.get(c) not in (None, "", "None", False, [], "[]")]
        if not vals:
            print(f"[dietas]   {c:24}   0 con dato"); continue
        # booleanos y códigos cortos se muestran tal cual; el texto libre se enmascara
        def _v(x):
            xs = str(x)
            return xs if (isinstance(x, bool) or len(xs) <= 14) else _mask_value(xs)[:44]
        largos = [len(str(x)) for x in vals]
        print(f"[dietas]   {c:24} {len(vals):>3} con dato · len max {max(largos):>4} · {[_v(x) for x in vals[:3]]}")
    # ¿coincide con lo que hoy leemos del reporte de Dietas?
    if dietas_rows is not None:
        print(f"[dietas] el reporte HTML de Dietas trae {len(dietas_rows)} filas hoy")
        con = sum(1 for tr in pers if tr.get("hasFoodReq") or tr.get("dietReq")
                  or tr.get("foodRestrictions") or tr.get("dietReqObs"))
        print(f"[dietas] la API marca con requerimiento alimentario: {con} personas")


def pgo_cruce_roster(page, date_str, geos_rows):
    """Cruza el roster de la API contra el del HTML, NOMBRE POR NOMBRE.

    El volumen coincidiendo no alcanza: si el desglose por persona difiere, los
    totales igual cuadran pero cada dieta se le asigna a otro. Por eso el
    criterio de migración es que las dos listas de nombres sean idénticas.
    """
    # 1) ¿qué campos tiene el traveller anidado?
    for tn in ("TravellerType",):
        q = '{ __type(name: "%s") { fields { name type { name kind ofType { name kind } } } } }' % tn
        try:
            r = pgo_graphql(page, q)
            campos = (((r.get("data") or {}).get("__type") or {}).get("fields") or [])
        except Exception as e:
            print(f"[cruce] no pude leer {tn}: {e}"); return
        esc = []
        for c in campos:
            t = c["type"]; nom = t.get("name") or (t.get("ofType") or {}).get("name") or ""
            k = (t.get("ofType") or {}).get("kind") or t.get("kind")
            if k not in ("OBJECT", "LIST") and not nom.endswith("Type"):
                esc.append(c["name"])
        print(f"[cruce] {tn}: {len(campos)} campos · escalares: {esc}")
    rx = re.compile(r"^(name|firstName|lastName|fullName|nombre|apellido|age|edad|birth|nationality|nacionalidad|country|gender|document)", re.I)
    sel = [c for c in esc if rx.search(c)] or esc[:12]
    print(f"[cruce] campos de persona elegidos: {sel}")

    # 2) roster por API, bajando al traveller
    q2 = """query ($hotelId: Int!, $date: Date!) {
              travellersInhouse(hotelId: $hotelId, date: $date) {
                room guestCount checkin checkout
                traveller { %s }
              }
            }""" % " ".join(sel)
    try:
        r2 = pgo_graphql(page, q2, {"hotelId": PGO_HOTEL_ID, "date": date_str})
    except Exception as e:
        print(f"[cruce] la query anidada falló: {e}"); return
    if r2.get("errors"):
        print(f"[cruce] errores: {str(r2['errors'])[:400]}")
    filas = (r2.get("data") or {}).get("travellersInhouse") or []
    if not filas:
        print("[cruce] sin filas: no se puede comparar."); return

    # 3) armar la lista de personas de la API
    def _nom(tr):
        if not isinstance(tr, dict): return ""
        for k in ("fullName", "name", "nombre"):
            if tr.get(k): return str(tr[k])
        a = " ".join(str(tr.get(k) or "") for k in ("firstName", "lastName") if tr.get(k))
        return a.strip()
    api = []
    for f in filas:
        t = f.get("traveller")
        for tr in (t if isinstance(t, list) else [t]):
            n = _nom(tr)
            if n:
                api.append((norm_key(fix_mojibake(n)), re.sub(r"\D", "", str(f.get("room") or "")).zfill(2)))
    html = []
    for r in (_remap(x, PGO_GEOS_COLS) for x in geos_rows):
        n = (r.get("nombre") or "").strip()
        if n:
            html.append((norm_key(n), re.sub(r"\D", "", str(r.get("hab") or "")).zfill(2)))

    sa, sh = {x[0] for x in api}, {x[0] for x in html}
    print(f"[cruce] ══ API {len(api)} personas · HTML {len(html)} personas ══")
    print(f"[cruce] sólo en API : {len(sa - sh)}")
    print(f"[cruce] sólo en HTML: {len(sh - sa)}")
    for n in sorted(sa - sh)[:6]: print(f"[cruce]    +API  {_mask_value(n)}")
    for n in sorted(sh - sa)[:6]: print(f"[cruce]    +HTML {_mask_value(n)}")
    da, dh = dict(api), dict(html)
    dif_hab = [n for n in (sa & sh) if da.get(n) != dh.get(n)]
    print(f"[cruce] misma persona, HABITACIÓN distinta: {len(dif_hab)}")
    for n in dif_hab[:5]: print(f"[cruce]    {_mask_value(n)}: API={da[n]} HTML={dh[n]}")
    print(f"[cruce] VEREDICTO: {'IDÉNTICOS — se puede migrar' if not (sa ^ sh) and not dif_hab else 'DIFIEREN — no migrar aún'}")


def pgo_explore(paths, date_str, dump=False, trace_net=False, introspect=False):
    """Abre sesión en PGO y perfila los reportes indicados. NO escribe nada."""
    _pgo_require()
    from playwright.sync_api import sync_playwright
    api_calls = []
    fecha = datetime.date.fromisoformat(date_str).strftime(PGO_DATE_FMT) if date_str else None
    launch_kw = {"headless": True}
    if os.environ.get("PGO_CHROMIUM"):
        launch_kw["executable_path"] = os.environ["PGO_CHROMIUM"]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(**launch_kw)
        page = browser.new_context(locale="es-CL").new_page()
        # La SPA pide sus datos por XHR. Si el reporte no renderiza tabla (el de
        # llegadas no la tiene), la API interna es la única vía razonable — y de
        # paso es más estable que pelear con un date-picker.
        if trace_net:
            pgo_api_probe(page, api_calls)
        base = PGO_BASE_URL
        try:
            page.goto(base + PGO_GEOS_PATH, wait_until="networkidle", timeout=60000)
        except Exception as e:
            if "ERR_NAME_NOT_RESOLVED" not in str(e):
                raise
            alt = (base.replace("://www.", "://", 1) if "://www." in base
                   else base.replace("://", "://www.", 1))
            print(f"[explore] {base} no resuelve; reintento con {alt}")
            page.goto(alt + PGO_GEOS_PATH, wait_until="networkidle", timeout=60000)
            base = alt
        globals()["PGO_BASE_URL"] = base
        if not _pgo_logged_in(page):
            _pgo_login(page)
            page.wait_for_load_state("networkidle", timeout=60000)
            for _ in range(40):
                page.wait_for_timeout(500)
                if _pgo_logged_in(page) or _pgo_error_msg(page):
                    break
            if not _pgo_logged_in(page):
                raise SystemExit("[explore] No pude iniciar sesión (ver §4.1: PGO_USER es el RUT).")
        # Sin esto todo reporte sale vacío: PGO abre en Torres del Paine.
        page.goto(PGO_BASE_URL + PGO_GEOS_PATH, wait_until="networkidle", timeout=60000)
        _pgo_set_destino(page, PGO_DESTINO)
        # La introspección va PRIMERO: si el esquema contesta, deja de tener
        # sentido adivinar selectores para los reportes que no renderizan.
        if introspect:
            pgo_resolve_hotel(page)
            pgo_introspect(page)
            pgo_introspect_types(page, PGO_TYPES_INTERES, max_depth=2)
            pgo_introspect_types(page, PGO_TYPES_GRANDES, max_depth=0,
                                 _filtro=_GQL_CAMPO_INTERES)
        # "inout" no es una página: es la query GraphQL de horas. Se prueba acá
        # antes de cablearla al sync productivo.
        if "inout" in paths:
            print(f"\n[explore] ===== inout (GraphQL reportInOut · hotelId={PGO_HOTEL_ID}) =====")
            horas, tot = pgo_fetch_inout(page, date_str or datetime.date.today().isoformat())
            print(f"[explore] totales: {tot}")
            con_in  = sum(1 for v in horas.values() if v.get("inAt"))
            con_out = sum(1 for v in horas.values() if v.get("outAt"))
            src = {}
            for v in horas.values():
                for k in ("inSrc", "outSrc"):
                    if v.get(k):
                        src[f"{k}={v[k]}"] = src.get(f"{k}={v[k]}", 0) + 1
            print(f"[explore] habs con hora de llegada: {con_in} · con hora de salida: {con_out}")
            print(f"[explore] origen del dato: {src or '(ninguno)'}")
            # Sólo el FORMATO de las horas, sin ligarlas a ninguna habitación.
            muestras = sorted({v[k] for v in horas.values() for k in ("inAt", "outAt") if v.get(k)})[:6]
            print(f"[explore] formato de las marcas: {muestras}")
            pgo_probe_arrival(page, date_str or datetime.date.today().isoformat())
            pgo_probe_roster(page, date_str or datetime.date.today().isoformat())
            try:
                _f = datetime.date.fromisoformat(date_str).strftime(PGO_DATE_FMT) if date_str else None
                _geos = _pgo_read_report(page, PGO_GEOS_PATH, _f)
                pgo_cruce_roster(page, date_str or datetime.date.today().isoformat(), _geos)
                _diet = _pgo_read_report(page, PGO_DIETAS_PATH, _f)
                pgo_probe_dietas(page, date_str or datetime.date.today().isoformat(), _diet)
                _iso = date_str or datetime.date.today().isoformat()
                pgo_compara_roster(pgo_fetch_roster(page, _iso),
                                   parse_pgo(_geos, _diet, _iso))
            except Exception as e:
                print(f"[cruce] no pude comparar contra el HTML: {type(e).__name__}: {e}")

        for nombre, path in paths.items():
            if nombre == "inout":
                continue
            print(f"\n[explore] ===== {nombre}  ({path}) =====")
            try:
                rows = _pgo_read_report(page, path, fecha,
                                        f"explore-{nombre}" if dump else None,
                                        kind=nombre, date_iso=date_str)
                _pgo_profile(nombre, rows)
            except SystemExit as e:
                # Un reporte que no se deja leer no debe abortar los demás: el
                # mapa de estructura ya quedó impreso por _pgo_read_report.
                print(f"[explore] {nombre}: no pude extraer la grilla. {e}")
            except Exception as e:
                print(f"[explore] {nombre}: error inesperado: {type(e).__name__}: {e}")
        browser.close()
    if trace_net and api_calls:
        print(f"\n[explore] === API de PGO: {len(api_calls)} llamadas ===")
        for i, c in enumerate(api_calls, 1):
            print(f"\n[explore] --- #{i} desde '{c['pagina']}' · {c['metodo']} {c['status']} {c['url']}")
            print(f"[explore] request: {c['req']}")
            print("[explore] respuesta (esqueleto, sin valores):")
            for ln in str(c["shape"]).splitlines()[:40]:
                print(f"[explore]   {ln}")


def pgo_fetch(date_str, dump=False, trace_net=False):
    """Login en PGO + lectura de Geos y Dietas del día → (geos_rows, dietas_rows)."""
    _pgo_require()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit(
            "[sync-viajeros] Falta Playwright. Instalá:\n"
            "  pip install playwright && python -m playwright install chromium\n"
            "  (en el workflow ya se instala automáticamente)."
        )
    # date_str None = respetar la fecha que PGO trae por defecto (el día
    # operativo, que es el siguiente). Sólo se fuerza si el owner pidió --date.
    fecha = datetime.date.fromisoformat(date_str).strftime(PGO_DATE_FMT) if date_str else None
    api_calls = []
    # PGO_CHROMIUM: ruta a un Chromium ya instalado. Útil en runners self-hosted
    # (o si PGO resulta accesible sólo desde la red corporativa) para no bajar
    # navegadores. Vacío = Playwright usa el suyo.
    launch_kw = {"headless": True}
    if os.environ.get("PGO_CHROMIUM"):
        launch_kw["executable_path"] = os.environ["PGO_CHROMIUM"]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(**launch_kw)
        ctx = browser.new_context(locale="es-CL")
        page = ctx.new_page()

        # Diagnóstico opcional: registra las llamadas XHR/fetch de la SPA. Sirve
        # para descubrir la API interna y, más adelante, pedir el JSON directo
        # (sin navegador) — mucho más rápido y estable que leer el HTML.
        if trace_net:
            def _on_resp(resp):
                try:
                    if resp.request.resource_type in ("xhr", "fetch"):
                        api_calls.append(f"{resp.request.method} {resp.status} {resp.url}")
                except Exception:
                    pass
            page.on("response", _on_resp)

        # 1) Sesión. Muchas apps redirigen al login al entrar a una ruta privada.
        #    Si el host no resuelve, probamos la variante con/sin "www." — los
        #    navegadores esconden el "www." en la barra, así que la URL que uno
        #    copia a mano suele venir sin él aunque el DNS sólo tenga el www.
        base = PGO_BASE_URL
        try:
            page.goto(base + PGO_GEOS_PATH, wait_until="networkidle", timeout=60000)
        except Exception as e:
            if "ERR_NAME_NOT_RESOLVED" not in str(e):
                raise
            alt = (base.replace("://www.", "://", 1) if "://www." in base
                   else base.replace("://", "://www.", 1))
            print(f"[sync-viajeros] {base} no resuelve; reintento con {alt}")
            page.goto(alt + PGO_GEOS_PATH, wait_until="networkidle", timeout=60000)
            base = alt
        globals()["PGO_BASE_URL"] = base   # las lecturas siguientes usan el host que sí funcionó
        if not _pgo_logged_in(page):
            if dump:
                _pgo_dump(page, "login")
            _pgo_form_report(page, "formulario de acceso (antes de completar)")
            _pgo_login(page)
            page.wait_for_load_state("networkidle", timeout=60000)
            # Esperar POR CONDICIÓN, no por tiempo fijo: PGO tarda distinto en
            # cada intento (con 1,5 s fijos el login entraba unas veces sí y
            # otras no). Se sondea hasta 20 s: corta apenas desaparece el
            # formulario o aparece un mensaje de error.
            for _ in range(40):
                page.wait_for_timeout(500)
                if _pgo_logged_in(page) or _pgo_error_msg(page):
                    break
            if not _pgo_logged_in(page):
                _pgo_form_report(page, "formulario tras intentar entrar")
                msg = _pgo_error_msg(page)
                raise SystemExit(
                    "[sync-viajeros] No pude iniciar sesión en PGO (sigue apareciendo el "
                    "formulario)."
                    + (f"\n  PGO dice: “{msg}”" if msg else "")
                    + "\n  Ojo: el campo de acceso de PGO es el RUT, no un nombre de usuario"
                      " — el secret PGO_USER debe llevar el RUT tal como se escribe al entrar"
                      " a mano.\n  Si el mensaje de arriba no aclara, corré con dump_html."
                )
            print("[sync-viajeros] Sesión iniciada en PGO.")
        else:
            print("[sync-viajeros] Sesión activa (sin formulario de login).")

        # 2) Destino: PGO abre en Torres del Paine. Se cambia ya parado en la
        # página del reporte — recién ahí está montada la cabecera con el menú
        # (justo después del login la SPA todavía no la dibujó).
        page.goto(PGO_BASE_URL + PGO_GEOS_PATH, wait_until="networkidle", timeout=60000)
        _pgo_set_destino(page, PGO_DESTINO)

        # 3) Reportes del día
        # El roster sale de la API desde el 2026-08-17: verificado contra el HTML
        # campo por campo, 0 diferencias en los 7 campos sobre 70 filas (§4.2).
        # El scraping de Geos queda como RESPALDO automático: si la query falla,
        # el sync no se cae — vuelve a leer la tabla. Es el corazón del módulo,
        # así que conserva las dos vías.
        fecha_iso = date_str or _pgo_fecha_visible(page)
        geos = []
        roster_api = None
        try:
            roster_api = pgo_fetch_roster(page, fecha_iso or datetime.date.today().isoformat())
            if not roster_api:
                raise ValueError("la API devolvió 0 viajeros")
        except Exception as e:
            print(f"[sync-viajeros] roster por API falló ({type(e).__name__}: {e}); "
                  "vuelvo al Reporte Geos por HTML.")
            roster_api = None
        if roster_api is None:
            geos = _pgo_read_report(page, PGO_GEOS_PATH, fecha, "geos" if dump else None)
        dietas = _pgo_read_report(page, PGO_DIETAS_PATH, fecha, "dietas" if dump else None)
        # Horas reales de movimiento por GraphQL (enfoque híbrido: el roster
        # sigue saliendo del HTML, que funciona; esto es lo nuevo). Si falla,
        # devuelve vacío y el sync continúa sin horas en vez de caerse.
        try:
            horas, totales = pgo_fetch_inout(page, fecha_iso or datetime.date.today().isoformat())
        except Exception as e:
            print(f"[sync-viajeros] Aviso: sin horas de movimiento ({type(e).__name__}: {e})")
            horas, totales = {}, {}
        # Comedor: cubiertos por servicio segun PGO. Es una SEGUNDA opinion
        # frente al conteo por presencia que hace la app; si divergen, algo se
        # perdio en el cruce. Que falle no debe tumbar el sync.
        try:
            filas_com = _pgo_read_report(page, PGO_COMEDOR_PATH, fecha,
                                         "comedor" if dump else None)
            if not getattr(_pgo_read_report, "ultima_fecha_ok", True):
                # Mejor sin comedor que con el comedor de MAÑANA: los cubiertos
                # del día equivocado se verían perfectamente normales.
                print("[sync-viajeros] comedor DESCARTADO: no se pudo confirmar la fecha.")
                comedor = None
            else:
                comedor = parse_comedor(filas_com)
                print(f"[sync-viajeros] comedor: {len(comedor['grupos'])} grupos · {comedor['totales']}")
        except Exception as e:
            print(f"[sync-viajeros] Aviso: sin reporte de comedor ({type(e).__name__}: {e})")
            comedor = None
        # Cumpleaños del mes. Que falle no debe tumbar el sync.
        try:
            cumples = parse_birthday(_pgo_read_report(
                page, PGO_BIRTHDAY_PATH, fecha, "cumples" if dump else None,
                kind="birthday", date_iso=fecha_iso))
            print(f"[sync-viajeros] cumpleaños del mes: {len(cumples)}")
        except Exception as e:
            print(f"[sync-viajeros] Aviso: sin reporte de cumpleaños ({type(e).__name__}: {e})")
            cumples = {}
        browser.close()

    if trace_net and api_calls:
        print("[sync-viajeros] Llamadas XHR/fetch detectadas (candidatas a API directa):")
        for c in dict.fromkeys(api_calls):
            print("   ", c)
    return geos, dietas, (fecha_iso or datetime.date.today().isoformat()), horas, totales, comedor, cumples, roster_api


# Mapeo encabezado de PGO (ya normalizado) → campo interno. Varios alias por si
# PGO nombra distinto que el PDF. Ajustar contra el HTML si algún nombre difiere.
PGO_GEOS_COLS = {
    "hab": "hab", "habitacion": "hab",
    "viajero": "nombre", "nombre": "nombre",
    "nac": "nac", "nacionalidad": "nac",
    "in/out": "inout", "inout": "inout", "in / out": "inout",
    "edad": "edad", "grupo": "grupo",
    # El Geos trae su propio comentario por viajero. Cubre a TODOS los in-house,
    # mientras que Dietas parece listar sólo el movimiento del día — por eso se
    # usa como segunda fuente de observaciones (ver parse_pgo).
    "comentario geos": "obs_geos", "comentario": "obs_geos",
}
PGO_DIET_COLS = {
    "hab": "hab", "nombre": "nombre", "viajero": "nombre",
    "edad": "edad", "nac": "nac", "grupo": "grupo",
    "observaciones": "obs", "observacion": "obs", "observaciones geos": "obs",
}


def _remap(row, colmap):
    return {colmap[k]: v for k, v in row.items() if k in colmap}


def _to_int(s, default=0):
    m = re.search(r"\d+", str(s or ""))
    return int(m.group()) if m else default


def _pgo_inout(val, year):
    """'20-07 22-07' (con saltos u otros separadores) -> ('YYYY-07-20','YYYY-07-22').

    El reporte no trae el año. Si el OUT cae antes que el IN, la estadía cruza
    el año nuevo (p.ej. 30-12 → 02-01) y el OUT se corre al año siguiente.
    """
    ds = re.findall(r"(\d{1,2})[-/](\d{1,2})", str(val or ""))
    def iso(dd, mm, y=year):
        return f"{y:04d}-{int(mm):02d}-{int(dd):02d}"
    if len(ds) >= 2:
        ind, outd = iso(*ds[0]), iso(*ds[1])
        if outd < ind:                       # cruce de año (dic → ene)
            outd = iso(ds[1][0], ds[1][1], year + 1)
        return ind, outd
    if len(ds) == 1:
        return iso(*ds[0]), ""
    return "", ""


# ── Observaciones por persona del reporte de comedor ─────────────────────────
# El comedor trae, por grupo, un texto con las restricciones de CADA integrante:
#   "(Elana) - Observaciones: NO CERDO (Ari Caleb) - ALERGIA a maní, no cerdo."
# Hasta el 2026-08-17 ese texto se guardaba entero en el grupo y NUNCA pasaba
# por obs_to_tags: la alergia al maní de Ari Caleb no generaba chip en ninguna
# parte. Es una tercera fuente de restricciones, además de Dietas y del
# comentario del Geos, y perderla es exactamente lo que no puede pasar.
_OBS_PERSONA = re.compile(r"\(([^)]{2,60})\)\s*[-–:]?\s*")


def parse_obs_comedor(texto):
    """'(A) - obs (B) - obs' → [(nombre, observación), …].

    Se parte por los paréntesis, que es lo único estable del formato: el resto
    del texto varía entre 'Observaciones:', 'Restricciones almientarias:' (sic,
    con la errata de PGO) y texto suelto.
    """
    t = fix_mojibake(texto or "").strip()
    if not t:
        return []
    partes = _OBS_PERSONA.split(t)
    # split con un grupo de captura deja [previo, nombre1, obs1, nombre2, obs2…]
    out = []
    for i in range(1, len(partes) - 1, 2):
        nombre = partes[i].strip()
        obs = (partes[i + 1] or "").strip(" -–:;.")
        if nombre and obs:
            out.append((nombre, obs))
    return out


def _nombre_calza(corto, completo):
    """¿'Ari Caleb' identifica a 'Ari Caleb Rosenberg'? Todas las palabras del
    nombre corto tienen que estar en el completo. Evita que 'Ana' matchee con
    cualquiera que tenga esa sílaba suelta."""
    a = set(norm_key(corto).split())
    b = set(norm_key(completo).split())
    return bool(a) and a.issubset(b)


def cruzar_obs_comedor(rows, comedor):
    """Suma al `obs` de cada viajero lo que el comedor dice de él.

    El cruce va POR HABITACIÓN primero y por nombre después: el comedor sólo da
    el nombre de pila, y buscarlo contra los 70 del roster invita a un falso
    positivo. Acotado a las habs del grupo, el riesgo desaparece.
    UNIÓN, nunca reemplazo: lo del comedor se agrega a lo que ya había.
    """
    if not comedor or not comedor.get("grupos"):
        return rows, 0
    sumadas = 0
    idx = {}
    for i, r in enumerate(rows):
        idx.setdefault(str(r[0]), []).append(i)
    rows = [list(r) for r in rows]
    for g in comedor["grupos"]:
        for nombre, obs in parse_obs_comedor(g.get("obs")):
            # candidatos: sólo los viajeros de las habitaciones de ESE grupo
            cand = [i for h in (g.get("habs") or []) for i in idx.get(str(h), [])]
            for i in cand:
                if not _nombre_calza(nombre, rows[i][1]):
                    continue
                actual = rows[i][7] or ""
                if norm_key(obs) and norm_key(obs) not in norm_key(actual):
                    rows[i][7] = f"{actual} · {obs}".strip(" ·")
                    sumadas += 1
                break
    return [tuple(r) for r in rows], sumadas


def parse_roster_con_dietas(roster_rows, dietas_rows):
    """Roster de la API + observaciones del reporte de Dietas, cruzadas por nombre.

    El roster ya viene en el formato final; lo único que falta es pegarle la
    observación, que sigue saliendo del HTML porque ahí hay más señal.
    """
    diet = {}
    for r in (_remap(x, PGO_DIET_COLS) for x in dietas_rows):
        if r.get("nombre"):
            diet[norm_key(r["nombre"])] = (r.get("obs") or "").strip()
    out, con_obs = [], 0
    for hab, nombre, edad, nac, grupo, ind, outd, _ in roster_rows:
        obs = diet.get(norm_key(nombre), "")
        if obs:
            con_obs += 1
        out.append((hab, nombre, edad, nac, grupo, ind, outd, obs))
    print(f"[sync-viajeros] cruce dietas→roster: {con_obs} de {len(dietas_rows)} observaciones pegadas")
    return out


def parse_pgo(geos_rows, dietas_rows, date_str):
    """
    Cruza Geos+Dietas (dicts leídos de PGO) -> filas en el MISMO formato que
    SEED_ROWS (hab, nombre, edad, nac, grupo, in, out, obs). De ahí en adelante
    build_doc() y obs_to_tags() hacen el resto sin cambios.

    Roster desde Geos (manda hab/edad/nac/grupo/IN-OUT); observación de dieta
    cruzada por norm_key(nombre) desde Dietas y pegada verbatim en obs.
    """
    year = datetime.date.fromisoformat(date_str).year
    diet = {}
    for r in (_remap(x, PGO_DIET_COLS) for x in dietas_rows):
        if r.get("nombre"):
            diet[norm_key(r["nombre"])] = (r.get("obs") or "").strip()
    rows = []
    for r in (_remap(x, PGO_GEOS_COLS) for x in geos_rows):
        nombre = (r.get("nombre") or "").strip()
        if not nombre:
            continue
        hab_digits = re.sub(r"\D", "", str(r.get("hab") or ""))
        hab = hab_digits.zfill(2) if hab_digits else str(r.get("hab") or "").strip()
        ind, outd = _pgo_inout(r.get("inout"), year)
        obs = diet.get(norm_key(nombre), "")
        # El comentario del Geos se suma SÓLO si normaliza a alguna dieta
        # conocida: así entran las dietas de quien no aparece en el reporte de
        # Dietas, sin arrastrar comentarios operativos (VIP, luna de miel, …)
        # al campo que se muestra en la app.
        cg = (r.get("obs_geos") or "").strip()
        if cg and obs_to_tags(cg) and norm_key(cg) not in norm_key(obs):
            obs = f"{obs} · {cg}".strip(" ·")
        rows.append((
            hab, nombre, _to_int(r.get("edad")),
            (r.get("nac") or "").strip().upper(),
            (r.get("grupo") or "").strip(),
            ind, outd, obs,
        ))
    return rows


# ── Firebase (mismo mecanismo que sync_rol.py) ───────────────────────────────

def get_token():
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request as GoogleAuthRequest
    key_data = json.loads(os.environ["FIREBASE_KEY"])
    creds = service_account.Credentials.from_service_account_info(
        key_data,
        scopes=[
            "https://www.googleapis.com/auth/firebase.database",
            "https://www.googleapis.com/auth/userinfo.email",
        ],
    )
    creds.refresh(GoogleAuthRequest())
    return creds.token


def fb_put(token, path, data):
    """El token va en la cabecera, no en la query.

    Con ?access_token=… el token entraba en la URL y, ante un error, requests lo
    imprimía completo en el traceback del log de Actions (pasó el 2026-08-07).
    """
    import requests
    r = requests.put(
        f"{DB_URL}/{path}.json",
        headers={"Authorization": f"Bearer {token}"},
        json=data,
        timeout=20,
    )
    if not r.ok:      # el cuerpo dice QUÉ rechazó Firebase; el status solo dice 400
        raise SystemExit(f"[sync-viajeros] Firebase rechazó el PUT ({r.status_code}): {r.text[:300]}")


# ── Main ──────────────────────────────────────────────────────────────────────

def print_summary(doc):
    habs = doc["habs"]
    travelers = [t for hab in habs.values() for t in hab]
    ninos = [t for t in travelers if t["edad"] <= 12]
    by_tag = {}
    for t in travelers:
        for tag in t["tags"]:
            by_tag.setdefault(tag, []).append(t["nombre"])
    print(f"[sync-viajeros] {doc['date']} · {len(habs)} habs · {len(travelers)} viajeros · {len(ninos)} niños (≤12)")
    for tag in sorted(by_tag):
        print(f"  {tag:28s} {len(by_tag[tag]):2d}  {', '.join(by_tag[tag])}")
    salen = [t["nombre"] for t in travelers if t["out"] == doc["date"]]
    print(f"  salen el {doc['date']:14s} {len(salen):2d}  {', '.join(salen)}")


def _arg_value(flag):
    """Valor que sigue a un flag en argv, o None (p.ej. --date 2026-07-26)."""
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return None


def main():
    # --explore corta antes que todo lo demás: sólo lee y perfila, nunca escribe
    # Firebase ni construye el doc. Es el modo de calibración de §4.1.
    if "--explore" in sys.argv:
        cual = _arg_value("--explore")
        paths = (PGO_EXPLORE_PATHS if not cual or cual.startswith("--")
                 else {k: v for k, v in PGO_EXPLORE_PATHS.items() if k in cual.split(",")})
        if not paths:
            raise SystemExit(f"[explore] Nada que explorar. Disponibles: {', '.join(PGO_EXPLORE_PATHS)}")
        print(f"[explore] Reportes a perfilar: {', '.join(paths)}")
        pgo_explore(paths, _arg_value("--date"), dump="--dump-html" in sys.argv,
                    trace_net="--trace-net" in sys.argv,
                    introspect="--introspect" in sys.argv)
        print("\n[explore] Listo — Firebase NO fue modificado.")
        return

    from_pgo = "--from-pgo" in sys.argv
    if from_pgo:
        date_str = _arg_value("--date")   # None = usar el día que PGO ya muestra
        print("[sync-viajeros] PGO — login y lectura de reportes "
              f"({date_str or 'fecha por defecto de PGO'})...")
        geos, dietas, date_str, horas, totales, comedor, cumples, roster_api = pgo_fetch(
            date_str,
            dump="--dump-html" in sys.argv,
            trace_net="--trace-net" in sys.argv)
        print(f"[sync-viajeros] Fecha efectiva del reporte: {date_str}")
        if roster_api is not None:
            # Las observaciones se siguen cruzando desde el reporte de Dietas:
            # los campos de dieta de la API traen menos casos (§4.2).
            rows = parse_roster_con_dietas(roster_api, dietas)
        else:
            rows = parse_pgo(geos, dietas, date_str)
        # TERCERA fuente de restricciones: el texto por persona del comedor.
        # Se suma a lo que ya haya, nunca lo reemplaza.
        rows, n_com = cruzar_obs_comedor(rows, comedor)
        if n_com:
            print(f"[sync-viajeros] comedor → obs: {n_com} observaciones por persona sumadas")
        print(f"[sync-viajeros] PGO: {len(geos)} filas Geos · {len(dietas)} filas Dietas → {len(rows)} viajeros")
        doc = build_doc(rows, date_str, "pgo", horas, totales, comedor, cumples)
    else:
        doc = build_doc(SEED_ROWS, REPORT_DATE, "seed")

    if "--emit-json" in sys.argv:
        out_path = sys.argv[sys.argv.index("--emit-json") + 1]
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
        print(f"[sync-viajeros] JSON escrito en {out_path}")
        return

    print_summary(doc)

    if "--debug" in sys.argv:
        print("[sync-viajeros] Modo debug — Firebase no modificado.")
        return

    if not from_pgo and "--seed" not in sys.argv:
        print("[sync-viajeros] Nada que hacer: usa --seed, --from-pgo, --debug o --emit-json.")
        return

    print("[sync-viajeros] Autenticando con Firebase...")
    token = get_token()
    fb_put(token, "viajeros/current", doc)
    print("[sync-viajeros] OK /viajeros/current")
    print("[sync-viajeros] Listo.")


if __name__ == "__main__":
    main()
