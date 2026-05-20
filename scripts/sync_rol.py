#!/usr/bin/env python3
"""
sync_rol.py — descarga el Excel de turnos desde SharePoint y actualiza Firebase.

Secrets requeridos (GitHub → Settings → Secrets → Actions):
  FIREBASE_KEY   →  contenido completo del JSON de la service account
  SHAREPOINT_URL →  link directo de descarga del Excel

Modo debug (no escribe en Firebase, imprime estructura):
  FIREBASE_KEY=$(cat firebase-key.json) SHAREPOINT_URL=<url> python scripts/sync_rol.py --debug
"""

import json, os, io, sys, re, datetime, requests
import openpyxl
from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleAuthRequest

SHAREPOINT_URL = os.environ["SHAREPOINT_URL"]
DB_URL = "https://explora-cafe-orders-default-rtdb.firebaseio.com"
DEBUG  = "--debug" in sys.argv

# Alias: nombre en el Excel (tras limpiar sufijos) → nombre a mostrar en la app.
ALIASES = {
    "Francisco Monjes": "Bruno",
    # "Otro Nombre": "Apodo",
}

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

# Solo turnos de COMEDOR — bar y recepción se excluyen de la vista principal.
COMEDOR_AM  = {"CAM", "CAMC"}
COMEDOR_PM  = {"CPM", "CPMC"}
COMEDOR_DOB = {"CDOB"}   # doble: aparece en AM y PM

# Roles que cuentan como "senior" en el comedor.
SENIOR_ROLES = {"GEO SENIOR", "SUP COMEDOR", "JEFE HOSP"}


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
    """Quita sufijos (TDP)/(VAL)/etc., aplica aliases y normaliza espacios."""
    if not raw:
        return None
    name = re.sub(r"\s*\([^)]*\)", "", str(raw)).strip()
    if not name:
        return None
    return ALIASES.get(name, name)


def comedor_shifts(code):
    """
    Devuelve lista de franjas ['am'], ['pm'], ['am','pm'] o [] según el código.
    Solo códigos de COMEDOR — bar/recepción devuelven [].
    """
    if code is None:
        return []
    s = str(code).strip().upper()
    if s in COMEDOR_AM:
        return ["am"]
    if s in COMEDOR_PM:
        return ["pm"]
    if s in COMEDOR_DOB:
        return ["am", "pm"]
    return []


def apoyo_shifts(code):
    """
    Clasifica los códigos informales de la sección de Apoyos.
    Ignora bar/recepción; solo devuelve ['am'], ['pm'] o ['am','pm'].
    """
    if not code:
        return []
    s = str(code).strip().lower().replace(" ", "").replace("/", "")
    if s in {"bpm", "bam", "bpis", "rpm", "bpmc", "bamc", "bpmapoyo", "bpisbpm", "rnoc", "rsal"}:
        return []
    if s.startswith("cam") or s == "almbpm":
        return ["am"]
    if s in {"cpm", "cpmc", "cen", "cena"}:
        return ["pm"]
    if s == "dob":
        return ["am", "pm"]
    return []


def find_sheets(wb, month: int):
    """
    Devuelve (ws_principal, ws_apoyos).
    ws_principal: hoja con datos GEO/GEO SENIOR (prefiere v2).
    ws_apoyos:    hoja con sección de apoyos (prefiere base sin v2, ya que v2 no la tiene).
    Ambas pueden ser la misma si solo hay una hoja del mes.
    """
    mes_names = MES_VARIANTS[month]
    ws_principal = ws_apoyos = None

    # Principal: v2 preferida
    for mes in mes_names:
        for candidate in (f"{mes} v2", mes):
            if candidate in wb.sheetnames:
                ws_principal = wb[candidate]
                break
        if ws_principal:
            break

    # Apoyos: hoja base preferida (sin v2) porque la sección de apoyos solo está ahí
    for mes in mes_names:
        if mes in wb.sheetnames:
            ws_apoyos = wb[mes]
            break
    if ws_apoyos is None:
        ws_apoyos = ws_principal  # fallback: misma hoja

    if ws_principal is None:
        raise ValueError(
            f"No se encontró hoja para mes {month}. "
            f"Hojas disponibles: {wb.sheetnames}"
        )

    return ws_principal, ws_apoyos


def get_day_cols(rows):
    """Detecta la fila DIA y retorna (dia_idx, day_cols dict)."""
    dia_idx = next(
        (i for i, r in enumerate(rows) if len(r) > 9 and r[9] == "DIA"),
        None,
    )
    if dia_idx is None:
        raise ValueError("No se encontró fila 'DIA' en la hoja")
    dia_row = rows[dia_idx]
    day_cols = {
        int(v): ci
        for ci, v in enumerate(dia_row)
        if isinstance(v, (int, float)) and 1 <= v <= 31
    }
    return dia_idx, day_cols


def parse_excel(xlsx_bytes, month: int):
    """
    Retorna (staffing_dict, roster_dict) listos para Firebase.
    staffing: { "1": {viajeros, geo_senior_am, geo_senior_pm, geos_am, geos_pm, apoyo_am, apoyo_pm}, ... }
    roster:   { "Nombre": {role, days}, ... }
    """
    wb = openpyxl.load_workbook(xlsx_bytes, read_only=True, data_only=True)
    ws_main, ws_apoyo = find_sheets(wb, month)
    print(f"[sync-rol] GEOs: {ws_main.title} | Apoyos: {ws_apoyo.title}")

    # ── Sección GEO / GEO SENIOR ──────────────────────────────────────────────
    rows_main = list(ws_main.iter_rows(values_only=True))
    dia_idx, day_cols = get_day_cols(rows_main)

    # Viajeros (fila DIA + 2)
    occ_row = rows_main[dia_idx + 2]
    viajeros = {
        day: int(occ_row[col])
        for day, col in day_cols.items()
        if isinstance(occ_row[col], (int, float))
    }

    # Personas GEO: solo filas con SENIOR_ROLES o 'GEO', filtradas a COMEDOR
    people = []
    for row in rows_main[dia_idx + 3:]:
        role_cell = row[8] if len(row) > 8 else None
        if role_cell not in (*SENIOR_ROLES, "GEO"):
            continue
        name = clean_name(row[9] if len(row) > 9 else None)
        if not name:
            continue
        shifts = {}
        for day, col in day_cols.items():
            code = row[col] if col < len(row) else None
            shifts[day] = comedor_shifts(code)  # [] si no es comedor
        people.append({"name": name, "is_senior": role_cell in SENIOR_ROLES, "shifts": shifts})
        if DEBUG:
            sample = [f"{d}:{''.join(shifts[d]) or '-'}" for d in sorted(shifts)[:7]]
            print(f"  {'SENIOR' if role_cell in SENIOR_ROLES else 'GEO':6s} {name}: {' '.join(sample)}...")

    print(f"[sync-rol] {len(people)} personas en sección GEO")

    # Nombres ya cubiertos como GEO — no deben aparecer también como apoyo
    geo_names = {p["name"] for p in people}

    # ── Sección Apoyos ────────────────────────────────────────────────────────
    rows_apoyo = list(ws_apoyo.iter_rows(values_only=True)) if ws_apoyo is not ws_main else rows_main
    _, day_cols_ap = get_day_cols(rows_apoyo)

    apoyos = []   # {name, shifts: {day: ['am'/'pm'/...]}}
    for row in rows_apoyo:
        # Apoyos tienen col8=None y col9=nombre con códigos de texto en días
        if (row[8] if len(row) > 8 else None) is not None:
            continue
        name = clean_name(row[9] if len(row) > 9 else None)
        if not name or name in geo_names:
            continue
        # Distinguir filas de persona (códigos texto) vs filas de estadísticas (números)
        day_vals = [row[col] if col < len(row) else None for col in day_cols_ap.values()]
        if not any(isinstance(v, str) and v.strip() for v in day_vals):
            continue
        shifts_ap = {day: apoyo_shifts(row[col] if col < len(row) else None)
                     for day, col in day_cols_ap.items()}
        if any(shifts_ap.values()):
            apoyos.append({"name": name, "shifts": shifts_ap})
            if DEBUG:
                sample = [f"{d}:{''.join(shifts_ap[d]) or '-'}" for d in sorted(shifts_ap)[:7]]
                print(f"  APOYO  {name}: {' '.join(sample)}...")

    print(f"[sync-rol] {len(apoyos)} personas en sección Apoyos")

    # ── Construir staffing ────────────────────────────────────────────────────
    staffing = {}
    for day in sorted(day_cols):
        entry = {
            "viajeros":      viajeros.get(day, 0),
            "geo_senior_am": [],
            "geo_senior_pm": [],
            "geos_am":       [],
            "geos_pm":       [],
            "apoyo_am":      [],
            "apoyo_pm":      [],
        }
        for p in people:
            for franja in p["shifts"].get(day, []):
                if p["is_senior"]:
                    entry[f"geo_senior_{franja}"].append(p["name"])
                else:
                    entry[f"geos_{franja}"].append(p["name"])
        for ap in apoyos:
            for franja in ap["shifts"].get(day, []):
                entry[f"apoyo_{franja}"].append(ap["name"])
        staffing[str(day)] = entry

    # ── Construir roster ──────────────────────────────────────────────────────
    roster = {}
    for p in people:
        working_days = sorted(day for day, s in p["shifts"].items() if s)
        roster[p["name"]] = {
            "role": "geo_senior" if p["is_senior"] else "geo",
            "days": working_days,
        }
    for ap in apoyos:
        working_days = sorted(day for day, s in ap["shifts"].items() if s)
        if working_days:
            roster[ap["name"]] = {"role": "apoyo", "days": working_days}

    return staffing, roster


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    today     = datetime.date.today()
    month_str = today.strftime("%Y-%m")

    print(f"[sync-rol] {today} — descargando Excel...")
    xlsx = download_excel()
    print(f"[sync-rol] {xlsx.getbuffer().nbytes:,} bytes recibidos")

    staffing, roster = parse_excel(xlsx, today.month)
    print(f"[sync-rol] {len(staffing)} dias · {len(roster)} personas en roster")

    if DEBUG:
        import pprint
        print("\n--- staffing dia 19 ---")
        pprint.pprint(staffing.get("19"))
        print("\n--- roster (primeras 5) ---")
        pprint.pprint(dict(list(roster.items())[:5]))
        print("\n[sync-rol] Modo debug — Firebase no modificado.")
        return

    print("[sync-rol] Autenticando con Firebase...")
    token = get_token()

    fb_put(token, f"staffing/{month_str}", staffing)
    print(f"[sync-rol] OK /staffing/{month_str}")

    fb_put(token, f"roster/{month_str}", roster)
    print(f"[sync-rol] OK /roster/{month_str}")

    ts = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    fb_put(token, "meta/last_update", ts)
    print(f"[sync-rol] OK /meta/last_update -> {ts}")
    print("[sync-rol] Listo.")


if __name__ == "__main__":
    main()
