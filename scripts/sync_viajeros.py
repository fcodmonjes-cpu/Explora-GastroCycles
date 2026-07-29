#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_viajeros.py — publica en Firebase los viajeros en casa con sus dietas,
alergias y restricciones, agrupados por habitación. Alimenta el módulo
"Viajeros" del ATA Handbook (el reemplazo digital del corcho de tarjetas).

Fuentes reales (fase 2, cuando el Excel esté disponible):
  · Reporte "Dietas"      → hab, nombre, edad, nac, grupo, observaciones
  · "Reporte Geos" diario → hab, viajero, nac, IN/OUT, edad, excursión, grupo
  parse_excel() queda como stub documentado; el resto del pipeline
  (normalización → doc Firebase) ya es el definitivo.

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
  python scripts/sync_viajeros.py --seed               → escribe el seed en Firebase
  python scripts/sync_viajeros.py --from-excel         → baja el Excel real y escribe (fase 2)
  python scripts/sync_viajeros.py --debug              → imprime resumen, no escribe
  python scripts/sync_viajeros.py --emit-json out.json → dump del doc (dev local)
  (combinables: --from-excel --debug valida el Excel sin tocar Firebase)
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


# ── Fase 2 — parseo del Excel real (Dietas + Reporte Geos) ───────────────────
# El PLUMBING ya está listo: download_excel() baja el xlsx desde SharePoint,
# main() --from-excel lo carga con openpyxl y llama a parse_excel(wb), y el
# resultado pasa por build_doc(source="excel") igual que el seed. Lo único que
# falta cuando llegue el link es MAPEAR LAS COLUMNAS dentro de parse_excel().
#
# Activar la fase 2 (cuando el owner consiga el link de descarga):
#   1. Agregar el secret VIAJEROS_SHAREPOINT_URL en GitHub → Settings → Secrets
#      → Actions (link directo de descarga del Excel Dietas/Geos). Es un secret
#      DISTINTO al SHAREPOINT_URL del rol.
#   2. Llenar parse_excel() con el mapeo de columnas real (ver spec abajo).
#   3. Validar sin escribir:  VIAJEROS_SHAREPOINT_URL=<url> \
#        python scripts/sync_viajeros.py --from-excel --debug
#   4. Cuando el resumen se vea bien: --from-excel (escribe /viajeros/current).
#   5. En seed-viajeros.yml: agregar un cron horario que corra --from-excel con
#      el nuevo secret (hoy el workflow solo corre --seed on-dispatch/on-push).

VIAJEROS_XLSX_ENV = "VIAJEROS_SHAREPOINT_URL"   # secret propio del Excel de dietas


def norm_key(s):
    """Texto sin tildes en minúscula — para cruzar Dietas ↔ Geos por nombre."""
    return unicodedata.normalize("NFD", str(s)).encode("ascii", "ignore").decode().lower().strip()


def download_excel():
    """Baja el xlsx desde SharePoint. Espejo de download_excel() de sync_rol.py."""
    import io, requests
    url = os.environ.get(VIAJEROS_XLSX_ENV)
    if not url:
        raise SystemExit(
            f"Falta el secret/variable {VIAJEROS_XLSX_ENV} (link de descarga del "
            "Excel Dietas/Geos). Agrégalo en GitHub Actions o expórtalo local."
        )
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"},
                     allow_redirects=True, timeout=30)
    r.raise_for_status()
    if r.content[:2] != b"PK":
        raise ValueError(
            f"La respuesta no es un xlsx ({len(r.content)} bytes). "
            "¿Expiró el link de SharePoint?"
        )
    return io.BytesIO(r.content)


def parse_excel(wb):
    """
    Cruza las dos fuentes y devuelve filas en el MISMO formato que SEED_ROWS
    (hab, nombre, edad, nac, grupo, in, out, obs) para pasar por build_doc().
    obs_to_tags() y build_doc() ya hacen el resto sin cambios.

    Flujo previsto (llenar contra el Excel real; detectar columnas leyendo la
    fila de encabezado, no hardcodear índices — ver find_sheet/get_day_cols en
    sync_rol.py como referencia de la técnica):

      1. Hoja "Dietas": una fila por viajero → hab, nombre, edad, nac, grupo,
         observación libre. Indexar por norm_key(nombre) (o hab+nombre si hay
         homónimos entre grupos).
      2. Hoja "Reporte Geos" (diaria): una fila por viajero → IN/OUT (y hab, que
         manda si difiere de Dietas). Cruzar por el mismo norm_key para pegar
         las fechas IN/OUT sobre cada viajero de Dietas.
      3. Emitir la lista de tuplas en el orden de columnas de SEED_ROWS.

    Los `nac` nuevos que aparezcan hay que sumarlos al mapa VJ_NAC de index.html
    (nacionalidad → bandera) o caen a texto sin bandera.
    """
    raise NotImplementedError(
        "Fase 2 — falta mapear columnas del Excel Dietas/Geos. El plumbing "
        "(download_excel, --from-excel, build_doc) ya está listo; ver el "
        "comentario de arriba para los pasos de activación."
    )


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


def main():
    from_excel = "--from-excel" in sys.argv
    if from_excel:
        import openpyxl
        print("[sync-viajeros] Descargando Excel Dietas/Geos...")
        wb = openpyxl.load_workbook(download_excel(), read_only=True, data_only=True)
        doc = build_doc(parse_excel(wb), datetime.date.today().isoformat(), "excel")
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

    if not from_excel and "--seed" not in sys.argv:
        print("[sync-viajeros] Nada que hacer: usa --seed, --from-excel, --debug o --emit-json.")
        return

    print("[sync-viajeros] Autenticando con Firebase...")
    token = get_token()
    fb_put(token, "viajeros/current", doc)
    print("[sync-viajeros] OK /viajeros/current")
    print("[sync-viajeros] Listo.")


if __name__ == "__main__":
    main()
