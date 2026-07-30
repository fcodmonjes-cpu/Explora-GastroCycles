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

ALLERGY_MODE = re.compile(r"ALERG|ALLERG|CELIAC|INTOLERAN")
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

def build_doc(rows, date_str, source):
    habs = {}
    for i, (hab, nombre, edad, nac, grupo, in_d, out_d, obs) in enumerate(rows):
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
            # "foto": <url> — hook para la cédula futura; ausente = avatar iniciales
        }
        habs.setdefault(hab, []).append(traveler)
    return {
        "date":      date_str,
        "updatedAt": int(datetime.datetime.utcnow().timestamp() * 1000),
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
PGO_DATE_FMT    = os.environ.get("PGO_DATE_FMT")    or "%d-%m-%Y"   # como se ve en el input: 31-07-2026
# Selector del input de fecha y del botón refrescar (texto visible, robusto a
# cambios de clases). Sobrescribibles por env si el markup cambia.
PGO_SEL_DATE    = os.environ.get("PGO_SEL_DATE",    "input[value*='-20'], input[placeholder*='-'], .ant-picker-input input, input[type='text']")
PGO_SEL_REFRESH = os.environ.get("PGO_SEL_REFRESH") or "REFRESCAR"   # se busca por texto (case-insensitive)
PGO_TABLE_SEL   = os.environ.get("PGO_TABLE_SEL",   "")   # vacío = autodetecta la tabla con más filas
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

  // --- Estrategia A: <table> clásica ---
  const fromTable = tbl => {
    const trs = [...tbl.querySelectorAll('tr')];
    if (!trs.length) return null;
    let hi = trs.findIndex(tr => tr.querySelector('th'));
    if (hi < 0) hi = 0;
    const headers = [...trs[hi].querySelectorAll('th,td')].map(c => norm(c.innerText));
    const rows = [];
    for (let i = hi + 1; i < trs.length; i++) {
      const cells = [...trs[i].querySelectorAll('td,th')].map(c => norm(c.innerText));
      if (cells.some(x => x)) rows.push(cells);
    }
    return {headers, rows};
  };

  // --- Estrategia B: grilla ARIA (role=table/grid con role=row/columnheader) ---
  const fromAria = el => {
    const rowsEl = [...el.querySelectorAll('[role=row]')];
    if (!rowsEl.length) return null;
    const hdrRow = rowsEl.find(r => r.querySelector('[role=columnheader]')) || rowsEl[0];
    const headers = [...hdrRow.querySelectorAll('[role=columnheader],[role=cell],[role=gridcell]')]
                      .map(c => norm(c.innerText));
    const rows = [];
    for (const r of rowsEl) {
      if (r === hdrRow) continue;
      const cells = [...r.querySelectorAll('[role=gridcell],[role=cell],[role=columnheader]')]
                      .map(c => norm(c.innerText));
      if (cells.some(x => x)) rows.push(cells);
    }
    return {headers, rows};
  };

  const score = data => {
    if (!data || !data.headers.length) return -1;
    const h = data.headers.map(fold);
    if (h.every(x => DOW.includes(x))) return -1;              // calendario
    const hits = WANT.filter(w => h.some(x => x.includes(w))).length;
    return hits * 1000 + Math.min(data.rows.length, 999);
  };

  if (sel) {
    const el = document.querySelector(sel);
    if (!el) return null;
    return (el.tagName === 'TABLE' ? fromTable(el) : fromAria(el)) || fromTable(el);
  }
  let best = null, bestScore = 0;
  for (const el of document.querySelectorAll('table,[role=table],[role=grid]')) {
    const data = el.tagName === 'TABLE' ? fromTable(el) : fromAria(el);
    const sc = score(data);
    if (sc > bestScore) { bestScore = sc; best = data; }
  }
  return best;
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


def _pgo_set_date(page, fecha):
    """Setea la fecha en el datepicker de la SPA y refresca el reporte.

    PGO no acepta la fecha por URL: hay un input (DD-MM-YYYY) y un botón
    REFRESCAR. Se llena el input, se confirma con Enter y se refresca. Si el
    input ya muestra la fecha pedida, no toca nada.
    """
    try:
        inp = page.locator(PGO_SEL_DATE).first
        if inp.count() == 0:
            print("[sync-viajeros] Aviso: no encontré el input de fecha; leo lo que muestre el reporte.")
            return False
        actual = (inp.input_value() or "").strip()
        if actual != fecha:
            inp.click()
            inp.fill("")
            inp.type(fecha, delay=30)
            page.keyboard.press("Enter")
            page.wait_for_timeout(500)
        page.keyboard.press("Escape")   # cierra el calendario: si queda abierto tapa la tabla
        page.wait_for_timeout(200)
        # Botón REFRESCAR (por texto, case-insensitive)
        btn = page.get_by_text(re.compile(PGO_SEL_REFRESH, re.I)).first
        if btn.count() > 0:
            btn.click(timeout=8000)   # corto: si no se puede clickear, seguimos igual
        page.wait_for_load_state("networkidle", timeout=60000)
        page.wait_for_timeout(800)   # margen para que la tabla se repinte
        return True
    except Exception as e:
        print(f"[sync-viajeros] Aviso: no pude setear la fecha ({e}); leo lo que muestre el reporte.")
        return False


def _pgo_structure_report(page):
    """Mapa de la estructura de la página cuando no aparece la grilla esperada.

    Imprime QUÉ tipo de contenedores hay (tablas, grillas ARIA, contenedores con
    muchos hijos repetidos) y sus encabezados — nunca datos de huéspedes, sólo
    los títulos de columna y nombres de clase, que es lo que hace falta para
    apuntar el extractor.
    """
    try:
        info = page.evaluate("""
          () => {
            const norm = s => (s||'').replace(/\s+/g,' ').trim();
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
            // Contenedores con muchos hijos del mismo tipo: candidatos a grilla div
            for (const el of document.querySelectorAll('div,ul,tbody')) {
              const n = el.children.length;
              if (n < 8) continue;
              const tags = new Set([...el.children].map(c => c.tagName));
              if (tags.size !== 1) continue;
              out.repes.push({hijos: n, tag: [...tags][0],
                              cls: (el.className||'').slice(0,60),
                              muestra: norm(el.children[0].innerText).slice(0,90)});
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
    if not any(info.values()):
        print("[sync-viajeros]   (no encontré ni tablas ni contenedores repetidos)")


def _pgo_read_report(page, path, fecha, dump_name=None):
    """Abre un reporte, fija la fecha y devuelve [{encabezado_normalizado: valor}]."""
    url = PGO_BASE_URL + path
    page.goto(url, wait_until="networkidle", timeout=60000)
    _pgo_set_date(page, fecha)
    if dump_name:
        _pgo_dump(page, dump_name)
    data = page.evaluate(_PGO_TABLE_JS, PGO_TABLE_SEL or None)
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
        out.append({headers[i]: cells[i] for i in range(min(len(headers), len(cells)))})
    print(f"[sync-viajeros] {path}: {len(out)} filas · columnas: {', '.join(headers)}")
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
    fecha = datetime.date.fromisoformat(date_str).strftime(PGO_DATE_FMT)
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

        # 2) Reportes del día
        geos   = _pgo_read_report(page, PGO_GEOS_PATH,   fecha, "geos"   if dump else None)
        dietas = _pgo_read_report(page, PGO_DIETAS_PATH, fecha, "dietas" if dump else None)
        browser.close()

    if trace_net and api_calls:
        print("[sync-viajeros] Llamadas XHR/fetch detectadas (candidatas a API directa):")
        for c in dict.fromkeys(api_calls):
            print("   ", c)
    return geos, dietas


# Mapeo encabezado de PGO (ya normalizado) → campo interno. Varios alias por si
# PGO nombra distinto que el PDF. Ajustar contra el HTML si algún nombre difiere.
PGO_GEOS_COLS = {
    "hab": "hab", "habitacion": "hab",
    "viajero": "nombre", "nombre": "nombre",
    "nac": "nac", "nacionalidad": "nac",
    "in/out": "inout", "inout": "inout", "in / out": "inout",
    "edad": "edad", "grupo": "grupo",
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
        rows.append((
            hab, nombre, _to_int(r.get("edad")),
            (r.get("nac") or "").strip().upper(),
            (r.get("grupo") or "").strip(),
            ind, outd,
            diet.get(norm_key(nombre), ""),
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
    import requests
    r = requests.put(
        f"{DB_URL}/{path}.json",
        params={"access_token": token},
        json=data,
        timeout=20,
    )
    r.raise_for_status()


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
    from_pgo = "--from-pgo" in sys.argv
    if from_pgo:
        date_str = _arg_value("--date") or datetime.date.today().isoformat()
        print(f"[sync-viajeros] PGO — login y lectura de reportes ({date_str})...")
        geos, dietas = pgo_fetch(date_str,
                                 dump="--dump-html" in sys.argv,
                                 trace_net="--trace-net" in sys.argv)
        rows = parse_pgo(geos, dietas, date_str)
        print(f"[sync-viajeros] PGO: {len(geos)} filas Geos · {len(dietas)} filas Dietas → {len(rows)} viajeros")
        doc = build_doc(rows, date_str, "pgo")
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
