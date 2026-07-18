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

Fase 1 (actual): SEED_ROWS — dataset placeholder coherente construido a mano
desde fotos de ambos reportes (13/17-07-2026) y del corcho físico. Nombres y
habs que aparecen en más de una fuente se mantienen consistentes; el resto es
relleno verosímil. Sirve para probar la UI con volumen real (~50 habs).

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
  alergia-{mariscos,gluten,lactosa,sesamo,pescado,ajo,frutos-secos,frutillas}
  dieta-{vegetariana,vegana,sin-gluten,sin-lactosa,sin-cerdo,sin-carnes-rojas,
         sin-cordero,sin-mariscos,sin-pescado,sin-fritura}
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

REPORT_DATE = "2026-07-17"   # fecha nominal del seed (día del Reporte Geos)


# ── Seed placeholder ──────────────────────────────────────────────────────────
# (hab, nombre, edad, nac, grupo, in, out, observación textual del reporte)
# Observaciones en el formato crudo en que llegan (mayúsculas irregulares,
# mezcla ES/EN) para ejercitar la normalización igual que con el Excel real.

SEED_ROWS = [
    ("01", "Patricio Moreno Undurraga", 41, "CHIL", "MORENO", "2026-07-16", "2026-07-19", ""),
    ("01", "Patricia Moreno Achondo", 38, "CHIL", "MORENO", "2026-07-16", "2026-07-19", "EMBARAZADA"),
    ("02", "Diogo Freitas Carneiro", 48, "BRAZ", "FREITAS", "2026-07-14", "2026-07-20", "NO FRUTOS DEL MAR - ALERGIA A LOS CAMARONES"),
    ("02", "Marina Carneiro Freitas", 45, "BRAZ", "FREITAS", "2026-07-14", "2026-07-20", ""),
    ("03", "Peter Koranyi", 61, "USA", "KORANYI", "2026-07-15", "2026-07-18", ""),
    ("03", "Suzanne Koranyi", 58, "USA", "KORANYI", "2026-07-15", "2026-07-18", "Sin restricciones alimenticias"),
    ("04", "Deepankar Panigrahi", 47, "INDI", "PANIGRAHI", "2026-07-16", "2026-07-21", "NO COME CARNES ROJAS, PRE DIABETICO; Alergias: Don't eat beef"),
    ("04", "Anjali Panigrahi", 44, "INDI", "PANIGRAHI", "2026-07-16", "2026-07-21", "VEGETARIANA"),
    ("04", "Rohan Panigrahi", 12, "INDI", "PANIGRAHI", "2026-07-16", "2026-07-21", "VEGETARIANO"),
    ("05", "Leticia Costa", 34, "BRAZ", "COSTA", "2026-07-16", "2026-07-20", "NO COME FRUTILLAS"),
    ("05", "Bruno Costa", 36, "BRAZ", "COSTA", "2026-07-16", "2026-07-20", ""),
    ("06", "Marcos Silva Prado", 51, "BRAZ", "SILVA", "2026-07-13", "2026-07-17", ""),
    ("06", "Fernanda Silva", 49, "BRAZ", "SILVA", "2026-07-13", "2026-07-17", "Libre de Lactosa"),
    ("07", "Ignacio Vicente Rios", 39, "CHIL", "VICENTE", "2026-07-15", "2026-07-18", ""),
    ("07", "Josefa Vicente Larrain", 37, "CHIL", "VICENTE", "2026-07-15", "2026-07-18", ""),
    ("08", "Cristobal Rojas Vial", 42, "CHIL", "ROJAS", "2026-07-16", "2026-07-22", ""),
    ("08", "Magdalena Rojas Court", 40, "CHIL", "ROJAS", "2026-07-16", "2026-07-22", ""),
    ("08", "Emilia Rojas Court", 8, "CHIL", "ROJAS", "2026-07-16", "2026-07-22", "no come picante; sin alergias"),
    ("09", "Michael Harris", 55, "USA", "HARRIS", "2026-07-12", "2026-07-17", ""),
    ("09", "Karen Harris", 53, "USA", "HARRIS", "2026-07-12", "2026-07-17", "GLUTEN FREE"),
    ("11", "Helena Costa", 22, "BRAZ", "COSTA", "2026-07-13", "2026-07-18", "CELIACA - Libre de Gluten"),
    ("11", "Laura Fernandes Kalaigian", 22, "BRAZ", "COSTA", "2026-07-13", "2026-07-18", "Libre de Lactosa; Alergias: no informada"),
    ("12", "Gabriela Linhares", 19, "BRAZ", "LINHARES", "2026-07-13", "2026-07-18", "ALERGIA A LOS CAMARONES"),
    ("12", "Pedro Linhares", 21, "BRAZ", "LINHARES", "2026-07-13", "2026-07-18", ""),
    ("13", "Antonio Pedro Linhares", 48, "BRAZ", "LINHARES", "2026-07-13", "2026-07-18", "No tiene dietas - no informa"),
    ("13", "Carolina Cavalcanti Landau Linhares", 47, "BRAZ", "LINHARES", "2026-07-13", "2026-07-18", "Libre de Gluten - Libre de Lactosa; intolerancia al gluten y lactosa"),
    ("14", "Ricardo Baumgart", 54, "BRAZ", "BAUMGART", "2026-07-15", "2026-07-19", ""),
    ("15", "Ana Clara Nascimento", 41, "BRAZ", "NASCIMENTO", "2026-07-14", "2026-07-18", ""),
    ("15", "Sofia Nascimento", 9, "BRAZ", "NASCIMENTO", "2026-07-14", "2026-07-18", ""),
    ("16", "Vinicius Nascimento", 44, "BRAZ", "NASCIMENTO", "2026-07-14", "2026-07-18", "VEGANO"),
    ("17", "Andrea Antunes Veras", 57, "BRAZ", "ANTUNES", "2026-07-14", "2026-07-17", "no indica"),
    ("17", "Leonardo Veras Mccormick", 20, "BRAZ", "ANTUNES", "2026-07-14", "2026-07-17", "NO PESCADO"),
    ("18", "Raimundo Solis Bacigalupo", 22, "CHIL", "SOLIS", "2026-07-16", "2026-07-22", ""),
    ("18", "Benjamin Solis Bacigalupo", 23, "CHIL", "SOLIS", "2026-07-16", "2026-07-22", ""),
    ("19", "Rodrigo Leite Silva Ribeiro", 30, "BRAZ", "RIBEIRO", "2026-07-11", "2026-07-17", ""),
    ("19", "Amanda Sousa De Andrade", 25, "BRAZ", "RIBEIRO", "2026-07-11", "2026-07-17", "NO COME FRITURA; no alergias"),
    ("20", "Andre Ribeiro De Andrada Buck", 30, "BRAZ", "RIBEIRO", "2026-07-11", "2026-07-17", ""),
    ("20", "Rafaela De Andrada Ribeiro", 23, "BRAZ", "RIBEIRO", "2026-07-11", "2026-07-17", ""),
    ("21", "Marcelo Costa Reis Ribeiro", 67, "BRAZ", "RIBEIRO", "2026-07-11", "2026-07-17", ""),
    ("21", "Gabriela Ribeiro De Andrada", 57, "BRAZ", "RIBEIRO", "2026-07-11", "2026-07-17", ""),
    ("22", "Isadora Chaves Arrais", 16, "BRAZ", "ARRAIS", "2026-07-16", "2026-07-20", ""),
    ("22", "Felipe Chaves Arrais", 9, "BRAZ", "ARRAIS", "2026-07-16", "2026-07-20", ""),
    ("23", "Michelle Lai Velez", 51, "USA", "VELEZ", "2026-07-12", "2026-07-17", ""),
    ("23", "Juan Velez", 50, "USA", "VELEZ", "2026-07-12", "2026-07-17", ""),
    ("24", "Celso Arrais Rodrigues Da Silva", 50, "BRAZ", "ARRAIS", "2026-07-16", "2026-07-20", ""),
    ("24", "Christiano Leonardo Gonzaga Gomes", 46, "BRAZ", "ARRAIS", "2026-07-16", "2026-07-20", ""),
    ("25", "Pablo Matias Parodi Orquera", 32, "CHIL", "PARODI", "2026-07-16", "2026-07-19", ""),
    ("25", "Constanza Alejandra Gutierrez Diaz", 34, "CHIL", "PARODI", "2026-07-16", "2026-07-19", ""),
    ("26", "Jordan Zuleta Toro", 40, "CHIL", "TORO", "2026-07-16", "2026-07-19", ""),
    ("26", "Viana Lucia Toro Vargas", 38, "CHIL", "TORO", "2026-07-16", "2026-07-19", "NO COME CORDERO - ALERGIA A LAS OSTRAS"),
    ("27", "Lucas Toro Mckenzie", 17, "CHIL", "MCKENZIE", "2026-07-16", "2026-07-21", "ALERGIA A LOS FRUTOS SECOS EN GENERAL"),
    ("27", "Matilda Toro Mckenzie", 15, "CHIL", "MCKENZIE", "2026-07-16", "2026-07-21", ""),
    ("27", "Amalia Toro Mckenzie", 13, "CHIL", "MCKENZIE", "2026-07-16", "2026-07-21", "ALERGIA A LOS CAMARONES"),
    ("28", "Carolyn Mckenzie", 44, "CHIL", "MCKENZIE", "2026-07-16", "2026-07-21", ""),
    ("28", "Juan Carlos Toro Ruiz-Tagle", 48, "CHIL", "MCKENZIE", "2026-07-16", "2026-07-21", ""),
    ("29", "Robinson Paz Grez", 44, "CHIL", "BUENO", "2026-07-16", "2026-07-19", ""),
    ("29", "Yerko Bueno Salomon", 45, "CHIL", "BUENO", "2026-07-16", "2026-07-19", ""),
    ("30", "Paula Noschese", 58, "BRAZ", "NOSCHESE", "2026-07-17", "2026-07-22", ""),
    ("30", "Antonio Noschese", 10, "BRAZ", "NOSCHESE", "2026-07-17", "2026-07-22", "no come verduras crudas"),
    ("31", "David Bivins", 48, "USA", "BIVINS", "2026-07-17", "2026-07-20", ""),
    ("31", "Leila Teel Bivins", 15, "USA", "BIVINS", "2026-07-17", "2026-07-20", ""),
    ("32", "Marco Parrella", 47, "USA", "PARRELLA", "2026-07-17", "2026-07-20", ""),
    ("32", "Eliana Cefia Kundrat Parrella", 15, "USA", "PARRELLA", "2026-07-17", "2026-07-20", ""),
    ("33", "Henrique Gomes Barreto", 43, "BRAZ", "GOMES", "2026-07-15", "2026-07-18", ""),
    ("33", "Juliana Barreto", 41, "BRAZ", "GOMES", "2026-07-15", "2026-07-18", ""),
    ("34", "Rafael Duarte", 38, "BRAZ", "DUARTE", "2026-07-16", "2026-07-20", ""),
    ("34", "Camila Duarte", 36, "BRAZ", "DUARTE", "2026-07-16", "2026-07-20", ""),
    ("34", "Theo Duarte", 6, "BRAZ", "DUARTE", "2026-07-16", "2026-07-20", "sin frutos secos por precaucion; ALERGIA AL MANI"),
    ("35", "Laura Gutierrez", 69, "USA", "SUTHERLAND", "2026-07-13", "2026-07-18", "VEGETARIANA; GLUTEN FREE Y LACTO FREE"),
    ("35", "James Sutherland", 41, "USA", "SUTHERLAND", "2026-07-13", "2026-07-18", "VEGETARIANO"),
    ("36", "Juan Carlos Pattillo Silva", 52, "CHIL", "PATTILLO", "2026-07-15", "2026-07-19", "DIABETICO"),
    ("36", "Cecilia Silva Prado", 50, "CHIL", "PATTILLO", "2026-07-15", "2026-07-19", ""),
    ("37", "Robert Wagner", 63, "USA", "WAGNER", "2026-07-14", "2026-07-17", ""),
    ("37", "Ellen Wagner", 60, "USA", "WAGNER", "2026-07-14", "2026-07-17", "Requerimientos alimentarios: Vegetariana"),
    ("38", "Oliver Thompson", 46, "ENGL", "THOMPSON", "2026-07-16", "2026-07-21", ""),
    ("38", "Charlotte Thompson", 44, "ENGL", "THOMPSON", "2026-07-16", "2026-07-21", ""),
    ("39", "Gabriela Baumgart", 52, "BRAZ", "BAUMGART", "2026-07-15", "2026-07-19", "Requerimientos alimentarios: Vegetariana"),
    ("40", "Monica Rangel", 49, "BRAZ", "RANGEL", "2026-07-15", "2026-07-18", "NO COMEN CERDO, NI CARNES ROJAS"),
    ("40", "Eduardo Rangel", 51, "BRAZ", "RANGEL", "2026-07-15", "2026-07-18", "NO COMEN CERDO, NI CARNES ROJAS"),
    ("41", "Gabriela Mendes", 39, "BRAZ", "MENDES", "2026-07-16", "2026-07-22", "Alergia al ajo"),
    ("41", "Sergio Mendes", 42, "BRAZ", "MENDES", "2026-07-16", "2026-07-22", "Alergia a los erizos"),
    ("42", "Cristina Farjallat", 55, "BRAZ", "SZARF", "2026-07-14", "2026-07-18", "NO COMEN CERDO"),
    ("42", "Gilberto Szarf", 55, "BRAZ", "SZARF", "2026-07-14", "2026-07-18", "NO COMEN CERDO"),
    ("43", "Andres Oyarzun Perez", 47, "CHIL", "OYARZUN", "2026-07-17", "2026-07-20", ""),
    ("43", "Paulina Oyarzun Bravo", 45, "CHIL", "OYARZUN", "2026-07-17", "2026-07-20", ""),
    ("44", "Daniel Lopez", 44, "USA", "LOPEZ", "2026-07-16", "2026-07-20", ""),
    ("44", "Maria Lopez", 42, "USA", "LOPEZ", "2026-07-16", "2026-07-20", ""),
    ("44", "Valentina Lopez", 10, "USA", "LOPEZ", "2026-07-16", "2026-07-20", "Libre de Gluten"),
    ("45", "Felipe Szarf", 16, "BRAZ", "SZARF", "2026-07-14", "2026-07-18", "NO COMEN CERDO"),
    ("45", "Luisa Szarf", 14, "BRAZ", "SZARF", "2026-07-14", "2026-07-18", "NO COMEN CERDO"),
    ("46", "Ewelina Sealy", 45, "ENGL", "SEALY", "2026-07-15", "2026-07-19", "Sin restricciones alimenticias - ALERGIA AL SESAMO; Alergias: Sesame seeds"),
    ("46", "Laura Sealy", 16, "ENGL", "SEALY", "2026-07-15", "2026-07-19", "ALERGIA A LAS SEMILLAS DE SESAMO"),
    ("47", "Eduardo Vasconcelos", 47, "BRAZ", "VASCONCELOS", "2026-07-16", "2026-07-21", ""),
    ("47", "Renata Palhares Vasconcelos", 45, "BRAZ", "VASCONCELOS", "2026-07-16", "2026-07-21", ""),
    ("47", "Maria Victoria Palhares Vasconcelos", 13, "BRAZ", "VASCONCELOS", "2026-07-16", "2026-07-21", "CELIACA"),
    ("48", "Joao Martins", 57, "BRAZ", "MARTINS", "2026-07-13", "2026-07-17", ""),
    ("48", "Beatriz Martins", 55, "BRAZ", "MARTINS", "2026-07-13", "2026-07-17", ""),
    ("49", "Ivana Kovac", 36, "USA", "KOVAC", "2026-07-15", "2026-07-19", "lactose free"),
    ("49", "Milan Kovac", 38, "USA", "KOVAC", "2026-07-15", "2026-07-19", ""),
    ("50", "Alexandre Freitas De Paiva", 56, "BRAZ", "FREITAS", "2026-07-14", "2026-07-20", "PREFIERE NO COMER MARISCOS / FRUTOS DEL MAR"),
    ("50", "Beatriz De Paiva", 53, "BRAZ", "FREITAS", "2026-07-14", "2026-07-20", ""),
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
    (r"MARISC|CAMARON|OSTRA|ERIZO|FRUTOS? DEL MAR|F\. ?DEL MAR|SEAFOOD|SHELLFISH", "mariscos"),
    (r"GLUTEN|CELIAC",                       "gluten"),
    (r"LACTOS|LACTO\b|LACTEOS?|DAIRY",       "lactosa"),
    (r"SESAM",                               "sesamo"),
    (r"PESCADO|\bFISH\b",                    "pescado"),
    (r"\bAJO\b|GARLIC",                      "ajo"),
    (r"FRUTOS SECOS|NUEZ|NUECES|\bMANI\b|ALMENDRA|NUTS?\b", "frutos-secos"),
    (r"FRUTILLA|FRESA|STRAWBERR",            "frutillas"),
]

# Temas que siempre son dieta (preferencia) o condición, sin importar el modo.
DIET_TOPICS = [
    (r"VEGETARIAN",                          "vegetariana"),
    (r"VEGAN[OA]?\b",                        "vegana"),
    (r"CERDO|CHANCHO|\bPORK\b",              "sin-cerdo"),
    (r"CARNES? ROJAS?|RED MEAT|\bBEEF\b",    "sin-carnes-rojas"),
    (r"CORDERO|\bLAMB\b",                    "sin-cordero"),
    (r"FRITURA|FRITOS?\b|FRIED",             "sin-fritura"),
]
COND_TOPICS = [
    (r"DIABET",                              "diabetico"),
    (r"EMBARAZ|PREGNAN",                     "embarazada"),
]

ALLERGY_MODE = re.compile(r"ALERG|ALLERG|CELIAC|INTOLERAN")
SPLIT_FRAGS  = re.compile(r"[;,·/]|\s[-–]\s|\sY\s|\sAND\s|\sE\s")


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
        allergy = bool(ALLERGY_MODE.search(frag))
        for rx, slug in FOOD_TOPICS:
            if re.search(rx, frag):
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
