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
día (2026-07-24). El roster completo (hab, nombre, edad, nac, grupo, IN/OUT)
sale del "Reporte Geos" del 24-07; las observaciones de dieta/alergia se cruzan
por nombre desde el reporte "Dietas" del mismo día y se pegan verbatim sobre el
viajero que corresponde. Mientras no llegue el link del Excel (fase 2), este
bloque se reemplaza a mano con el reporte de cada día. 47 habs · 111 viajeros.

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
           cilantro,quinoa}
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

REPORT_DATE = "2026-07-24"   # fecha nominal del seed (día del Reporte Geos)


# ── Roster real del día ───────────────────────────────────────────────────────
# (hab, nombre, edad, nac, grupo, in, out, observación textual del reporte)
# Roster (hab/nombre/edad/nac/grupo/IN-OUT) desde el "Reporte Geos" 20-07-2026;
# las observaciones se cruzan por nombre desde el reporte "Dietas" del mismo día
# y se pegan verbatim (mayúsculas y mezcla ES/EN tal como llegan) para que la
# normalización obs_to_tags() trabaje sobre el texto original. Los viajeros sin
# fila en Dietas quedan con obs "" (sin restricción alimentaria informada).

SEED_ROWS = [
    ('01', 'Elaine Benisti', 51, 'BRAZ', 'BENISTI', '2026-07-22', '2026-07-27', ''),
    ('01', 'Roberto Benisti', 54, 'BRAZ', 'BENISTI', '2026-07-22', '2026-07-27', ''),
    ('02', 'Livia Farre Bloes', 7, 'BRAZ', 'BLOES', '2026-07-20', '2026-07-24', ''),
    ('02', 'Vinicius Farre Bloes', 11, 'BRAZ', 'BLOES', '2026-07-20', '2026-07-24', ''),
    ('03', 'Adriana Czerkes Farre', 44, 'BRAZ', 'BLOES', '2026-07-20', '2026-07-24', ''),
    ('03', 'Roberto Moreira Bloes', 43, 'BRAZ', 'BLOES', '2026-07-20', '2026-07-24', ''),
    ('04', 'Nititorn Sura-Bundith', 35, 'THAI', 'KHAMPALIKIT', '2026-07-21', '2026-07-25', ''),
    ('04', 'Por Khampalikit', 35, 'THAI', 'KHAMPALIKIT', '2026-07-21', '2026-07-25', 'ALERGIA A LA OSTRAS. Alergias: Oyster'),
    ('05', 'Nicolas Alfredo Tapia Quinteros', 38, 'CHIL', 'EXPLORA', '2026-07-23', '2026-07-24', ''),
    ('05', 'Matias Jesus Flores Caceres', 30, 'CHIL', 'EXPLORA', '2026-07-23', '2026-07-24', ''),
    ('06', 'Emilia Ignacia Alarcón García', 15, 'CHIL', 'ALARCON', '2026-07-20', '2026-07-25', ''),
    ('06', 'Josefa Isidora Alarcon Garcia', 7, 'CHIL', 'ALARCON', '2026-07-20', '2026-07-25', ''),
    ('07', 'Ademar Alejandro Alarcon', 47, 'CHIL', 'ALARCON', '2026-07-20', '2026-07-25', ''),
    ('07', 'Karen Fabiola Garcia Astudillo', 46, 'CHIL', 'ALARCON', '2026-07-20', '2026-07-25', ''),
    ('08', 'Prem Pavan Vuthandam', 51, 'INDI', 'VUTHANDAM', '2026-07-22', '2026-07-26', 'GLUTEN FREE LACTOSE FREE. Requerimientos alimentarios: Libre de Gluten - Libre de Lactosa - Baja en Carbohidratos - Libre de Azucar'),
    ('08', 'Purtini Vijaykumar Joshi', 48, 'USA', 'VUTHANDAM', '2026-07-22', '2026-07-26', 'VEGETARIANO. Requerimientos alimentarios: Vegetariana'),
    ('09', 'Meher Vuthandam', 7, 'INDI', 'VUTHANDAM', '2026-07-22', '2026-07-26', ''),
    ('09', 'Aahan Vuthandam', 17, 'INDI', 'VUTHANDAM', '2026-07-22', '2026-07-26', ''),
    ('10', 'Pamela Wheeler Maxwell', 84, 'USA', 'MAXWELL', '2026-07-21', '2026-07-24', ''),
    ('10', 'James Leslie Maxwell', 82, 'USA', 'MAXWELL', '2026-07-21', '2026-07-24', ''),
    ('13', 'Patrizia Galante', 78, 'ITAL', 'GALANTE', '2026-07-22', '2026-07-26', ''),
    ('13', 'Max Schwarz', 14, 'BRAZ', 'GALANTE', '2026-07-22', '2026-07-26', ''),
    ('13', 'Giulia Ellis Ramalho', 15, 'BRAZ', 'GALANTE', '2026-07-22', '2026-07-26', ''),
    ('14', 'Javiera Powditch Diez', 16, 'CHIL', 'DIEZ', '2026-07-22', '2026-07-26', ''),
    ('14', 'Catalina Powditch Diez', 18, 'CHIL', 'DIEZ', '2026-07-22', '2026-07-26', ''),
    ('15', 'Veronica Ivonne Diez Sabat', 50, 'CHIL', 'DIEZ', '2026-07-22', '2026-07-26', ''),
    ('15', 'Carlos Eduardo Kitridge Powditch Araya', 48, 'CHIL', 'DIEZ', '2026-07-22', '2026-07-26', ''),
    ('16', 'Davi Ribeiro Simao', 17, 'BRAZ', 'SIMAO', '2026-07-18', '2026-07-24', ''),
    ('16', 'Daniel Ribeiro Simao', 17, 'BRAZ', 'SIMAO', '2026-07-18', '2026-07-24', ''),
    ('16', 'Lais Ribeiro Simao', 7, 'BRAZ', 'SIMAO', '2026-07-18', '2026-07-24', ''),
    ('17', 'Lucas Pinto Simao', 41, 'BRAZ', 'SIMAO', '2026-07-18', '2026-07-24', ''),
    ('17', 'Luana De Carvalho Ribeiro Simão', 43, 'BRAZ', 'SIMAO', '2026-07-18', '2026-07-24', ''),
    ('18', 'Bernardita Maria Salas Negroni', 55, 'CHIL', 'UNDURRAGA', '2026-07-23', '2026-07-26', ''),
    ('18', 'Gonzalo Undurraga Pellegrini', 54, 'CHIL', 'UNDURRAGA', '2026-07-22', '2026-07-26', 'Requerimientos alimentarios: Libre de Azucar'),
    ('19', 'Blas Moreno', 16, 'ARGE', 'GUIDI', '2026-07-19', '2026-07-24', ''),
    ('19', 'Oriana Guidi', 57, 'ITAL', 'GUIDI', '2026-07-19', '2026-07-24', 'GLUTEN FREEE - LACTOSE FREE. Requerimientos alimentarios: Libre de Gluten - Libre de Lactosa - Baja en Carbohidratos. Alergias: I am not allergic to Gluten - I am intollerant to Gluten'),
    ('19', 'Patricio Esteban Maraboli Valenzuela', 44, 'CHIL', 'DAZA', '2026-07-24', '2026-07-29', ''),
    ('19', 'Adriana Sandra Milena Daza Gil', 50, 'CHIL', 'DAZA', '2026-07-24', '2026-07-29', ''),
    ('20', 'Salvador Moran Ramo', 14, 'MEXI', 'MORAN', '2026-07-24', '2026-07-28', ''),
    ('20', 'Salvador Moran Monroy', 59, 'MEXI', 'MORAN', '2026-07-24', '2026-07-28', ''),
    ('20', 'Giselle El Masou Luco', 47, 'CHIL', 'EL', '2026-07-22', '2026-07-24', 'Sin restricciones alimenticias - NO QUINOA'),
    ('21', 'Gabriela Muniz Barreto', 47, 'BRAZ', 'CAROSELLA', '2026-07-23', '2026-07-29', ''),
    ('22', 'Gabriela Barbosa Albuquerque', 6, 'BRAZ', 'BARBOSA', '2026-07-22', '2026-07-27', ''),
    ('22', 'Guilherme Barbosa Albuquerque', 9, 'BRAZ', 'BARBOSA', '2026-07-22', '2026-07-27', ''),
    ('23', 'Maria Juliana Salhani Do Prado Barbosa', 46, 'BRAZ', 'BARBOSA', '2026-07-22', '2026-07-27', ''),
    ('23', 'Andre Fernando Da Silva Vilarinho Simoes De Albuquerque', 43, 'BRAZ', 'BARBOSA', '2026-07-22', '2026-07-27', ''),
    ('24', 'Isabel Margarita Gonzalez Henriquez', 46, 'CHIL', 'ALBORNOZ', '2026-07-21', '2026-07-24', 'Requerimientos alimentarios: Libre de Lactosa. Alergias: No tengo dietas pero no como cosas con mucho aliño - Alergia a la azitromicina'),
    ('24', 'Susanne Vollbrecht', 63, 'GERM', 'VOLLBRECHT', '2026-07-24', '2026-07-27', 'prefieren una alimentación rica en vegetales y agradecerían mucho que siempre se les ofrecieran porciones abundantes de verduras y productos integrales en todas las comidas, incluido el desayuno.'),
    ('24', 'Daniela Albornoz', 32, 'CHIL', 'ALBORNOZ', '2026-07-21', '2026-07-24', 'NO COME NUECES. Alergias: nueces'),
    ('24', 'Vera Vollbrecht', 30, 'GERM', 'VOLLBRECHT', '2026-07-24', '2026-07-27', 'prefieren una alimentación rica en vegetales y agradecerían mucho que siempre se les ofrecieran porciones abundantes de verduras y productos integrales en todas las comidas, incluido el desayuno.'),
    ('25', 'Henrique Mc Darby Arouche De Toledo', 19, 'BRAZ', 'REZENDE', '2026-07-19', '2026-07-24', ''),
    ('25', 'Sophia Mc Darby Arouche De Toledo', 17, 'BRAZ', 'REZENDE', '2026-07-19', '2026-07-24', ''),
    ('26', 'Luis Henrique Rezende Arouche De Toledo', 55, 'BRAZ', 'REZENDE', '2026-07-19', '2026-07-24', ''),
    ('26', 'Grace Mc Darby Arouche De Toledo', 52, 'BRAZ', 'REZENDE', '2026-07-19', '2026-07-24', ''),
    ('27', 'Clara Lannes Ozmen Henrique', 14, 'BRAZ', 'LANNES', '2026-07-21', '2026-07-25', ''),
    ('27', 'Beatriz Lannes Ozmen Henrique', 11, 'BRAZ', 'LANNES', '2026-07-21', '2026-07-25', ''),
    ('28', 'Laercio Henrique Junior', 45, 'BRAZ', 'LANNES', '2026-07-21', '2026-07-25', ''),
    ('28', 'Aylin Lannes Ozmen Henrique', 45, 'BRAZ', 'LANNES', '2026-07-21', '2026-07-25', ''),
    ('29', 'Olivia De Albuquerque Schenardi', 12, 'BRAZ', 'SCHENARDI', '2026-07-22', '2026-07-27', ''),
    ('29', 'Maria Fernanda Vilarinho Simoes De Albuquerque', 45, 'BRAZ', 'SCHENARDI', '2026-07-22', '2026-07-27', ''),
    ('29', 'Cristiano Schenardi Paula', 48, 'BRAZ', 'SCHENARDI', '2026-07-22', '2026-07-27', ''),
    ('30', 'Lara Haddad Kairalla', 41, 'BRAZ', 'FUAD', '2026-07-24', '2026-07-30', ''),
    ('30', 'Tomas Leal Da Costa Marinho Rodrigues', 22, 'BRAZ', 'LEAL', '2026-07-17', '2026-07-24', ''),
    ('30', 'Ana Claudia Leal Da Costa Marinho Rodrigues', 52, 'BRAZ', 'LEAL', '2026-07-17', '2026-07-24', 'Alergia a la piña'),
    ('30', 'Luciano Fuad Kairalla', 40, 'BRAZ', 'FUAD', '2026-07-24', '2026-07-30', 'LIBRE DE LACTOSA - SOLO COME QUESO SIN LACTOSA. Requerimientos alimentarios: Libre de Lactosa'),
    ('31', 'Isabela Felgueiras Da Silva', 12, 'BRAZ', 'ZANIN', '2026-07-21', '2026-07-26', ''),
    ('31', 'Jan Kozak', 38, 'CZEC', 'KOZAK', '2026-07-22', '2026-07-25', ''),
    ('31', 'Xiaoxiao Shen', 36, 'CHIN', 'KOZAK', '2026-07-22', '2026-07-25', ''),
    ('31', 'Maria Eduarda Felgueiras Da Silva', 12, 'BRAZ', 'ZANIN', '2026-07-21', '2026-07-26', ''),
    ('32', 'Francesca Carosella Aldrovandi', 14, 'ITAL', 'CAROSELLA', '2026-07-23', '2026-07-29', 'VEGETARIANA COME PESCADO. Requerimientos alimentarios: Vegetariana'),
    ('32', 'Gabriel Pires Demarchi', 15, 'BRAZ', 'CAROSELLA', '2026-07-23', '2026-07-29', ''),
    ('33', 'Filippo Bom Angelo Vita', 12, 'BRAZ', 'VITA', '2026-07-22', '2026-07-27', ''),
    ('33', 'Lorenzo Bom Angelo Vita', 8, 'BRAZ', 'VITA', '2026-07-22', '2026-07-27', ''),
    ('34', 'Michele Maria Vita', 45, 'ITAL', 'VITA', '2026-07-22', '2026-07-27', ''),
    ('34', 'Mariana Arriel Bom Angelo Vita', 43, 'BRAZ', 'VITA', '2026-07-22', '2026-07-27', ''),
    ('35', 'Joaquin Emilio Undurraga Salas', 12, 'CHIL', 'UNDURRAGA', '2026-07-23', '2026-07-26', ''),
    ('35', 'Elisa Maria Undurraga Salas', 20, 'CHIL', 'UNDURRAGA', '2026-07-23', '2026-07-26', ''),
    ('36', 'Josefina Undurraga Salas', 23, 'CHIL', 'UNDURRAGA', '2026-07-23', '2026-07-26', ''),
    ('36', 'Bernardita Maria Undurraga Salas', 28, 'CHIL', 'UNDURRAGA', '2026-07-23', '2026-07-26', ''),
    ('37', 'Carlos Andres Olson Woodburn', 4, 'USA', 'WOODBURN', '2026-07-21', '2026-07-27', ''),
    ('37', 'Jennifer Elizabeth Woodburn', 38, 'USA', 'WOODBURN', '2026-07-21', '2026-07-27', 'ALERGIA SEVERA A LOS MARISCOS'),
    ('37', 'Siena Olson Woodburn', 1, 'USA', 'WOODBURN', '2026-07-21', '2026-07-27', ''),
    ('37', 'Carlos Eduardo Gonzalez Olson', 44, 'MEXI', 'WOODBURN', '2026-07-21', '2026-07-27', ''),
    ('39', 'Thelio Bonesio Gonçalves', 37, 'BRAZ', 'BONESIO', '2026-07-19', '2026-07-24', ''),
    ('39', 'David Salvador Mediavilla', 19, 'SPAI', 'SALVADOR', '2026-07-24', '2026-07-28', ''),
    ('39', 'Jose Benedito Ventura', 46, 'BRAZ', 'BONESIO', '2026-07-19', '2026-07-24', ''),
    ('39', 'Martin Salvador Mediavilla', 17, 'SPAI', 'SALVADOR', '2026-07-24', '2026-07-28', 'ALERGIA A TODOS LOS FRUTOS SECOS'),
    ('40', 'Miguel Bonesio Gonçalves Da Silva', 13, 'BRAZ', 'BONESIO', '2026-07-19', '2026-07-24', ''),
    ('40', 'Maria Luisa Mediavilla Sanz', 56, 'SPAI', 'SALVADOR', '2026-07-24', '2026-07-28', ''),
    ('40', 'Emilio Luis Salvador Prieto', 56, 'SPAI', 'SALVADOR', '2026-07-24', '2026-07-28', ''),
    ('40', 'Graziella Bonesio Gonçalves', 39, 'BRAZ', 'BONESIO', '2026-07-19', '2026-07-24', ''),
    ('41', 'Maria Clara Comparini Nogueira De Sa Santos Pereira', 41, 'BRAZ', 'NOGUEIRA', '2026-07-23', '2026-07-30', ''),
    ('41', 'Joao Pedro Nogueira De Sa Santos Pereira', 8, 'BRAZ', 'NOGUEIRA', '2026-07-23', '2026-07-30', ''),
    ('42', 'Rosa Maria Dos Santos', 55, 'BRAZ', 'NOGUEIRA', '2026-07-23', '2026-07-30', ''),
    ('42', 'Luiz Eduardo Nogueira De Sá Santos Pereira', 4, 'BRAZ', 'NOGUEIRA', '2026-07-23', '2026-07-30', ''),
    ('43', 'Marcel Tadeu Matos Alves Da Silva', 50, 'BRAZ', 'ZANIN', '2026-07-21', '2026-07-26', ''),
    ('43', 'Carla Zanin Dos Santos Felgueiras', 50, 'BRAZ', 'ZANIN', '2026-07-21', '2026-07-26', ''),
    ('44', 'Paola Florencia Carosella', 53, 'ARGE', 'CAROSELLA', '2026-07-23', '2026-07-29', ''),
    ('45', 'Leticia Guimaraes Albernaz Lyle', 45, 'BRAZ', 'SHAYER', '2026-07-24', '2026-07-28', ''),
    ('45', 'Catherine Hilary Rogers', 49, 'USA', 'TAN', '2026-07-21', '2026-07-24', ''),
    ('45', 'Miguel Tan', 56, 'USA', 'TAN', '2026-07-21', '2026-07-24', ''),
    ('45', 'Fernando Shayer', 52, 'BRAZ', 'SHAYER', '2026-07-24', '2026-07-28', ''),
    ('46', 'Renata De Luizi Correia', 49, 'BRAZ', 'DE LUIZI', '2026-07-19', '2026-07-24', 'PESCETARIANA. Requerimientos alimentarios: Pescetariana'),
    ('47', 'Claudine Parseghian De Luizi Correia', 53, 'BRAZ', 'DE LUIZI', '2026-07-19', '2026-07-24', ''),
    ('47', 'André De Luizi Correia', 53, 'BRAZ', 'DE LUIZI', '2026-07-19', '2026-07-24', ''),
    ('48', 'Marco Antonio Nogueira De Sá Santos Pereira', 6, 'BRAZ', 'NOGUEIRA', '2026-07-23', '2026-07-30', ''),
    ('48', 'Maria Teresa Nogueira De Sá Santos Pereira', 10, 'BRAZ', 'NOGUEIRA', '2026-07-23', '2026-07-30', ''),
    ('48', 'Renato Junqueira Santos Pereira', 49, 'BRAZ', 'NOGUEIRA', '2026-07-23', '2026-07-30', ''),
    ('49', 'Julia Parseghian De Luizi Correia', 17, 'BRAZ', 'DE LUIZI', '2026-07-19', '2026-07-24', ''),
    ('49', 'Sofia Parseghian De Luizi Correia', 24, 'BRAZ', 'DE LUIZI', '2026-07-19', '2026-07-24', ''),
    ('50', 'Ana Cecilia Lecona Galvez', 27, 'MEXI', 'WOODBURN', '2026-07-22', '2026-07-25', ''),
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
