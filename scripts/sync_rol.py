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

# Códigos de turno de COMEDOR — los únicos que aparecen en el staffing panel.
# Bar (BAM/BPM) y recepción (RAM/RPM) se excluyen de las listas am/pm.
COMEDOR_AM  = {"CAM", "CAMC"}
COMEDOR_PM  = {"CPM", "CPMC"}
COMEDOR_DOB = {"CDOB"}   # doble turno → aparece en AM y PM

# Códigos que significan "no trabajando" — se omiten del roster.
NOT_WORKING = {"L", "LA", "LIC", "V", "CU", "F", "x", ""}

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


def comedor_franjas(code):
    """
    Retorna las franjas de comedor del código: [], ['am'], ['pm'], o ['am','pm'].
    Solo códigos CAM/CAMC/CPM/CPMC/CDOB — bar y recepción devuelven [].
    """
    if not code:
        return []
    s = str(code).strip().upper()
    if s in COMEDOR_AM:  return ["am"]
    if s in COMEDOR_PM:  return ["pm"]
    if s in COMEDOR_DOB: return ["am", "pm"]
    return []


def apoyo_franjas(code):
    """
    Clasifica los códigos informales de la sección de Apoyos.
    Ignora bar/recepción. Retorna [], ['am'], ['pm'] o ['am','pm'].
    """
    if not code:
        return []
    s = str(code).strip().lower().replace(" ", "").replace("/", "")
    if s in {"bpm", "bam", "bpis", "rpm", "rsal", "rnoc", "bpmc", "bamc", "bpmapoyo", "bpisbpm"}:
        return []
    if s.startswith("cam") or s == "almbpm":
        return ["am"]
    if s in {"cpm", "cpmc", "cen", "cena"}:
        return ["pm"]
    if s == "dob":
        return ["am", "pm"]
    return []


def is_working(code):
    """True si el código representa un turno real (no libre/vacaciones/etc.)."""
    if not code:
        return False
    return str(code).strip().upper() not in NOT_WORKING


def find_sheets(wb, month: int):
    """
    Devuelve (ws_principal, ws_apoyos).
    Principal: v2 preferida para GEO/GEO SENIOR (datos más actualizados).
    Apoyos:    hoja base preferida (la sección de apoyos solo existe ahí).
    """
    mes_names = MES_VARIANTS[month]
    ws_principal = ws_apoyos = None

    for mes in mes_names:
        for candidate in (f"{mes} v2", mes):
            if candidate in wb.sheetnames:
                ws_principal = wb[candidate]
                break
        if ws_principal:
            break

    for mes in mes_names:
        if mes in wb.sheetnames:
            ws_apoyos = wb[mes]
            break
    if ws_apoyos is None:
        ws_apoyos = ws_principal

    if ws_principal is None:
        raise ValueError(
            f"No se encontró hoja para mes {month}. "
            f"Hojas disponibles: {wb.sheetnames}"
        )
    return ws_principal, ws_apoyos


def get_day_cols(rows):
    """Detecta la fila DIA y retorna (dia_idx, day_cols {day_int: col_idx})."""
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

    staffing: { "1": { viajeros, geo_senior_am, geo_senior_pm,
                        geos_am, geos_pm, apoyo_am, apoyo_pm }, ... }

    roster:   { "Nombre": { "1": "CAM", "5": "CPM", ... } }
              (solo días trabajados, valor = código de turno del Excel)
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

    # Personas GEO: filas con SENIOR_ROLES o 'GEO'
    people = []
    for row in rows_main[dia_idx + 3:]:
        role_cell = row[8] if len(row) > 8 else None
        if role_cell not in (*SENIOR_ROLES, "GEO"):
            continue
        name = clean_name(row[9] if len(row) > 9 else None)
        if not name:
            continue

        comedor = {}   # day → ['am'/'pm'...]  para staffing arrays
        codes   = {}   # day → código raw      para roster

        for day, col in day_cols.items():
            code = row[col] if col < len(row) else None
            franjas = comedor_franjas(code)
            if franjas:
                comedor[day] = franjas
            if is_working(code):
                codes[str(day)] = str(code).strip().upper()

        people.append({
            "name":      name,
            "is_senior": role_cell in SENIOR_ROLES,
            "comedor":   comedor,
            "codes":     codes,
        })

        if DEBUG:
            sample = [f"{d}:{','.join(comedor.get(d,[])) or codes.get(str(d),'-')}"
                      for d in sorted(day_cols)[:7]]
            print(f"  {'SENIOR' if role_cell in SENIOR_ROLES else 'GEO':6s} {name}: {' '.join(sample)}...")

    print(f"[sync-rol] {len(people)} personas en sección GEO")
    geo_names = {p["name"] for p in people}

    # ── Sección Apoyos ────────────────────────────────────────────────────────
    rows_apoyo = (list(ws_apoyo.iter_rows(values_only=True))
                  if ws_apoyo is not ws_main else rows_main)
    _, day_cols_ap = get_day_cols(rows_apoyo)

    apoyos = []
    for row in rows_apoyo:
        if (row[8] if len(row) > 8 else None) is not None:
            continue
        name = clean_name(row[9] if len(row) > 9 else None)
        if not name or name in geo_names:
            continue
        # Solo filas de persona: algún día tiene valor de texto (no número)
        day_vals = [row[col] if col < len(row) else None for col in day_cols_ap.values()]
        if not any(isinstance(v, str) and v.strip() for v in day_vals):
            continue

        franjas_ap = {}  # day → ['am'/'pm'...]
        codes_ap   = {}  # day → código raw
        for day, col in day_cols_ap.items():
            code = row[col] if col < len(row) else None
            fr = apoyo_franjas(code)
            if fr:
                franjas_ap[day] = fr
            if code and str(code).strip() and str(code).strip().lower() not in NOT_WORKING:
                codes_ap[str(day)] = str(code).strip().upper()

        if any(franjas_ap.values()):
            apoyos.append({"name": name, "franjas": franjas_ap, "codes": codes_ap})
            if DEBUG:
                sample = [f"{d}:{''.join(franjas_ap.get(d,[])) or '-'}"
                          for d in sorted(day_cols_ap)[:7]]
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
            for franja in p["comedor"].get(day, []):
                key = f"geo_senior_{franja}" if p["is_senior"] else f"geos_{franja}"
                entry[key].append(p["name"])
        for ap in apoyos:
            for franja in ap["franjas"].get(day, []):
                entry[f"apoyo_{franja}"].append(ap["name"])
        staffing[str(day)] = entry

    # ── Construir roster  ─────────────────────────────────────────────────────
    # Formato que la app espera: { "NombrePersona": { "1": "CAM", "5": "CPM" } }
    roster = {}
    for p in people:
        if p["codes"]:
            roster[p["name"]] = p["codes"]
    for ap in apoyos:
        if ap["codes"]:
            roster[ap["name"]] = ap["codes"]

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
        print(f"\n--- staffing dia {today.day} ---")
        pprint.pprint(staffing.get(str(today.day)))
        print("\n--- roster Bruno ---")
        pprint.pprint(roster.get("Bruno"))
        print(f"\n--- roster Francisco Urrutia ---")
        pprint.pprint(roster.get("Francisco Urrutia"))
        print("\n[sync-rol] Modo debug — Firebase no modificado.")
        return

    print("[sync-rol] Autenticando con Firebase...")
    token = get_token()

    fb_put(token, f"staffing/{month_str}", staffing)
    print(f"[sync-rol] OK /staffing/{month_str}")

    fb_put(token, f"roster/{month_str}", roster)
    print(f"[sync-rol] OK /roster/{month_str}")

    # meta/last_update como objeto con timestamp_iso (formato que espera la app)
    now_utc = datetime.datetime.utcnow()
    fb_put(token, "meta/last_update", {
        "timestamp_iso":   now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timestamp_local": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "timestamp_ms":    int(now_utc.timestamp() * 1000),
        "mes":             month_str,
        "tipo":            "sync automatico",
    })
    print(f"[sync-rol] OK /meta/last_update")
    print("[sync-rol] Listo.")


if __name__ == "__main__":
    main()
