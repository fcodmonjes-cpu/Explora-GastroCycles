#!/usr/bin/env python3
"""
sync_rol.py — descarga el Excel de turnos desde SharePoint y actualiza Firebase.

Secrets requeridos (GitHub → Settings → Secrets → Actions):
  FIREBASE_KEY  →  contenido completo del JSON de la service account

Modo debug (no escribe en Firebase, imprime estructura):
  FIREBASE_KEY=$(cat firebase-key.json) python scripts/sync_rol.py --debug
"""

import json, os, io, sys, re, datetime, requests
import openpyxl
from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleAuthRequest

SHAREPOINT_URL = os.environ.get(
    "SHAREPOINT_URL",
    "https://exploracl-my.sharepoint.com/:x:/g/personal/bbossi_explora_com"
    "/IQBxeZ0oOIr8SYHBGrClVczaAc7hNdnV5UndiKHyOemr9ck?download=1",
)
DB_URL = "https://explora-cafe-orders-default-rtdb.firebaseio.com"
DEBUG  = "--debug" in sys.argv

# Alias: nombre en el Excel (tras limpiar sufijos) → nombre a mostrar en la app.
# El nombre del Excel es la clave; el alias es el valor.
ALIASES = {
    "Francisco Monjes": "Bruno",
    # "Otro Nombre": "Apodo",
}

# El Excel usa a veces nombre completo (JUNIO) y a veces abreviación (MAY, ABR).
# Se prueban todas las variantes posibles.
MES_VARIANTS = {
    1:  ["ENERO",      "ENE"],
    2:  ["FEBRERO",    "FEB"],
    3:  ["MARZO",      "MAR"],
    4:  ["ABRIL",      "ABR"],
    5:  ["MAYO",       "MAY"],
    6:  ["JUNIO",      "JUN"],
    7:  ["JULIO",      "JUL"],
    8:  ["AGOSTO",     "AGO"],
    9:  ["SEPTIEMBRE", "SEP", "SEPT"],
    10: ["OCTUBRE",    "OCT"],
    11: ["NOVIEMBRE",  "NOV"],
    12: ["DICIEMBRE",  "DIC"],
}

# Turnos de mañana → aparecen en geo_senior_am / geos_am
AM_CODES = {"CAM", "CAMC", "RAM", "RAMC", "BAM", "BAMC", "BPIS", "BDOB", "CDOB", "RDOB"}
# Turnos de tarde/noche → aparecen en geo_senior_pm / geos_pm
PM_CODES = {"CPM", "CPMC", "RPM", "RPMC", "RINT", "BPM", "BPMC", "RNOC", "RSAL"}
# L, LA, V, LIC, F, CU → no trabajando, se omiten


# ── Firebase ──────────────────────────────────────────────────────────────────

def get_token():
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
    r = requests.put(
        f"{DB_URL}/{path}.json",
        params={"access_token": token},
        json=data,
        timeout=20,
    )
    r.raise_for_status()


# ── Descarga ──────────────────────────────────────────────────────────────────

def download_excel():
    r = requests.get(
        SHAREPOINT_URL,
        headers={"User-Agent": "Mozilla/5.0"},
        allow_redirects=True,
        timeout=30,
    )
    r.raise_for_status()
    if r.content[:2] != b"PK":
        raise ValueError(
            f"La respuesta no es un xlsx ({len(r.content)} bytes). "
            "¿Expiró el link de SharePoint?"
        )
    return io.BytesIO(r.content)


# ── Parseo ────────────────────────────────────────────────────────────────────

def clean_name(raw):
    """Quita sufijos como (TDP), (VAL), (PNP), aplica aliases y normaliza espacios."""
    if not raw:
        return None
    name = re.sub(r"\s*\([^)]*\)", "", str(raw)).strip()
    if not name:
        return None
    return ALIASES.get(name, name)


def classify(code):
    if code is None:
        return None
    s = str(code).strip().upper()
    if s in AM_CODES:
        return "am"
    if s in PM_CODES:
        return "pm"
    return None


def find_sheet(wb, month: int):
    """Busca la hoja del mes actual, prefiriendo v2. Prueba nombre completo y abreviación."""
    for mes in MES_VARIANTS[month]:
        for candidate in (f"{mes} v2", mes):
            if candidate in wb.sheetnames:
                return wb[candidate], candidate
    raise ValueError(
        f"No se encontró hoja para mes {month}. "
        f"Hojas disponibles: {wb.sheetnames}"
    )


def parse_excel(xlsx_bytes, month: int):
    """
    Retorna (staffing_dict, roster_dict) listos para Firebase.
    staffing: { "1": {viajeros, geo_senior_am, geo_senior_pm, geos_am, geos_pm, ...}, ... }
    roster:   { "Nombre": {role, days}, ... }
    """
    wb = openpyxl.load_workbook(xlsx_bytes, read_only=True, data_only=True)
    ws, sheet_name = find_sheet(wb, month)
    print(f"[sync-rol] Usando hoja: {sheet_name}")

    rows = list(ws.iter_rows(values_only=True))

    # Fila con 'DIA' en col 9
    dia_idx = next(
        (i for i, r in enumerate(rows) if len(r) > 9 and r[9] == "DIA"),
        None,
    )
    if dia_idx is None:
        raise ValueError("No se encontró fila 'DIA' en la hoja")

    # Mapeo día → índice de columna
    dia_row = rows[dia_idx]
    day_cols = {
        int(v): ci
        for ci, v in enumerate(dia_row)
        if isinstance(v, (int, float)) and 1 <= v <= 31
    }

    # Viajeros (fila DIA + 2)
    occ_row = rows[dia_idx + 2]
    viajeros = {
        day: int(occ_row[col])
        for day, col in day_cols.items()
        if isinstance(occ_row[col], (int, float))
    }

    # Personas: solo filas donde col8 = 'GEO SENIOR' o 'GEO'
    people = []
    for row in rows[dia_idx + 3:]:
        role = row[8] if len(row) > 8 else None
        if role not in ("GEO SENIOR", "GEO"):
            continue
        name = clean_name(row[9] if len(row) > 9 else None)
        if not name:
            continue
        shifts = {
            day: classify(row[col] if col < len(row) else None)
            for day, col in day_cols.items()
        }
        people.append({"name": name, "role": role, "shifts": shifts})
        if DEBUG:
            sample = [f"{d}:{shifts[d] or '-'}" for d in sorted(shifts)[:7]]
            print(f"  {role:12s} {name}: {' '.join(sample)}…")

    print(f"[sync-rol] {len(people)} personas encontradas")

    # ── Staffing ──
    staffing = {}
    for day in sorted(day_cols):
        entry = {
            "viajeros":      viajeros.get(day, 0),
            "geo_senior_am": [],
            "geo_senior_pm": [],
            "geos_am":       [],
            "geos_pm":       [],
            "apoyo_am":      [],  # no cubierto por este Excel
            "apoyo_pm":      [],
        }
        for p in people:
            s = p["shifts"].get(day)
            if s == "am":
                key = "geo_senior_am" if p["role"] == "GEO SENIOR" else "geos_am"
            elif s == "pm":
                key = "geo_senior_pm" if p["role"] == "GEO SENIOR" else "geos_pm"
            else:
                continue
            entry[key].append(p["name"])
        staffing[str(day)] = entry

    # ── Roster ──
    roster = {}
    for p in people:
        working_days = sorted(
            day for day, s in p["shifts"].items() if s in ("am", "pm")
        )
        roster[p["name"]] = {
            "role": "geo_senior" if p["role"] == "GEO SENIOR" else "geo",
            "days": working_days,
        }

    return staffing, roster


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    today     = datetime.date.today()
    month_str = today.strftime("%Y-%m")

    print(f"[sync-rol] {today} — descargando Excel…")
    xlsx = download_excel()
    print(f"[sync-rol] {xlsx.getbuffer().nbytes:,} bytes recibidos")

    staffing, roster = parse_excel(xlsx, today.month)
    print(f"[sync-rol] {len(staffing)} días · {len(roster)} personas en roster")

    if DEBUG:
        import pprint
        print("\n--- staffing (primeros 2 dias) ---")
        pprint.pprint({k: staffing[k] for k in list(staffing)[:2]})
        print("\n--- roster (primeras 5 personas) ---")
        pprint.pprint(dict(list(roster.items())[:5]))
        print("\n[sync-rol] Modo debug — Firebase no modificado.")
        return

    print("[sync-rol] Autenticando con Firebase…")
    token = get_token()

    fb_put(token, f"staffing/{month_str}", staffing)
    print(f"[sync-rol] ✓ /staffing/{month_str}")

    fb_put(token, f"roster/{month_str}", roster)
    print(f"[sync-rol] ✓ /roster/{month_str}")

    ts = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    fb_put(token, "meta/last_update", ts)
    print(f"[sync-rol] ✓ /meta/last_update → {ts}")
    print("[sync-rol] Listo.")


if __name__ == "__main__":
    main()
