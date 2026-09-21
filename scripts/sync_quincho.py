#!/usr/bin/env python3
"""
sync_quincho.py — sube el plano de mesas del Quincho a Firebase.

MÓDULO TEMPORAL. Este script y el módulo Quincho del index.html se borran
juntos después del evento. Ver ARCHITECTURE.md §3.4.

POR QUÉ EXISTE ESTE SCRIPT en vez de un archivo de datos en el repo:
los datos del quincho son nombres completos de viajeros con su número de
habitación. El repo es PÚBLICO y Vercel sirve el index.html como archivo
estático — el gate de cuatro dígitos (§4.4) protege los datos de Firebase,
no los bytes del HTML. Un `curl` a la URL leería cualquier nombre que
estuviera escrito en el archivo, sin teclear un dígito, y el historial de
git no se borra con un commit. Por eso el plano viaja por Firebase, igual
que las dietas de PGO (§4.1), y el HTML sólo trae el código que lo lee.

FUENTE: el `buscador-mesas.html` que arma el jefe de A&B para el evento.
El script le extrae los arrays MESAS y ORDEN y los sube tal cual. Ese
archivo tampoco entra al repo — está en .gitignore junto a *.seed.json.

USO
  # Ver qué subiría, sin escribir nada en Firebase:
  python scripts/sync_quincho.py --from-html buscador-mesas.html --debug

  # Subir de verdad (necesita la service account):
  FIREBASE_KEY=$(cat firebase-key.json) \
    python scripts/sync_quincho.py --from-html buscador-mesas.html

  # Borrar el plano de Firebase después del evento:
  FIREBASE_KEY=$(cat firebase-key.json) python scripts/sync_quincho.py --borrar

REGLAS DE FIREBASE: el path `quincho` tiene que estar en las reglas o cae
en la denegación por defecto (§4.3 — la trampa de las reglas escritas de
memoria). La línea, sobre las reglas COPIADAS DE LA CONSOLA:

    "quincho": { ".read": "auth != null", ".write": false }

.write en false a propósito: el único que escribe es este script, con
service account, que pasa por encima de las reglas. La app sólo lee.
"""

import argparse, datetime, json, os, re, sys

DB_URL = "https://explora-cafe-orders-default-rtdb.firebaseio.com"
FB_PATH = "quincho/actual"


# ── Firebase ──────────────────────────────────────────────────────────────────
# Mismo patrón que sync_rol.py / sync_viajeros.py: service account → token →
# REST. Los imports pesados viven acá adentro para que --debug corra en
# cualquier máquina, sin google-auth instalado.

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


def fb_delete(token, path):
    import requests
    r = requests.delete(
        f"{DB_URL}/{path}.json",
        params={"access_token": token},
        timeout=20,
    )
    r.raise_for_status()


# ── Extracción desde el buscador-mesas.html ───────────────────────────────────

def _extraer_array(html, nombre):
    """Saca `const <nombre> = [...]` del HTML contando corchetes.

    Se cuentan corchetes en vez de usar un regex no-greedy porque los arrays
    traen arrays anidados (unidades → nombres) y un `.*?]` cortaría en el
    primer cierre interno.
    """
    m = re.search(r"const\s+%s\s*=\s*\[" % re.escape(nombre), html)
    if not m:
        raise ValueError(f"No encontré `const {nombre} = [` en el HTML.")
    ini = m.end() - 1
    prof, en_str, esc, comilla = 0, False, False, ""
    for i in range(ini, len(html)):
        c = html[i]
        if en_str:
            if esc:              esc = False
            elif c == "\\":      esc = True
            elif c == comilla:   en_str = False
            continue
        if c in "\"'":
            en_str, comilla = True, c
        elif c == "[":
            prof += 1
        elif c == "]":
            prof -= 1
            if prof == 0:
                return json.loads(html[ini:i + 1])
    raise ValueError(f"El array {nombre} no cierra.")


def parse_html(ruta):
    with open(ruta, encoding="utf-8") as f:
        html = f.read()
    mesas = _extraer_array(html, "MESAS")
    orden = _extraer_array(html, "ORDEN")
    validar(mesas, orden)
    return mesas, orden


def validar(mesas, orden):
    """Chequeos que atrapan un plano mal armado antes de subirlo.

    El plano se arma a mano contra el rooming del día, así que los errores
    posibles son de dedo: una mesa que quedó fuera del orden físico, dos
    mesas en la misma posición, un total que no cuadra con la gente listada.
    Todos son baratos de detectar acá y caros de descubrir a hora de servicio.
    """
    errores = []
    ns = [m["n"] for m in mesas]
    if len(set(ns)) != len(ns):
        errores.append(f"Números de mesa repetidos: {sorted(ns)}")
    if sorted(orden) != sorted(ns):
        errores.append(f"ORDEN {sorted(orden)} no cubre las mesas {sorted(ns)}")
    poss = [m["pos"] for m in mesas]
    if sorted(poss) != list(range(1, len(mesas) + 1)):
        errores.append(f"Las posiciones no son 1..{len(mesas)}: {sorted(poss)}")
    for m in mesas:
        # pos y ORDEN dicen lo mismo de dos formas; si no coinciden, la tira
        # del salón y la línea "Nª de izquierda a derecha" se contradicen.
        if orden.index(m["n"]) + 1 != m["pos"]:
            errores.append(
                f"Mesa {m['n']}: pos={m['pos']} pero en ORDEN va "
                f"{orden.index(m['n']) + 1}ª"
            )
        cuenta = sum(len(u["nombres"]) for u in m["unidades"])
        if cuenta != m["total"]:
            errores.append(f"Mesa {m['n']}: total={m['total']} pero hay {cuenta} nombres")
    if errores:
        raise SystemExit("[quincho] Plano inconsistente:\n  - " + "\n  - ".join(errores))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Sube el plano del Quincho a Firebase.")
    ap.add_argument("--from-html", metavar="RUTA",
                    help="buscador-mesas.html del que extraer MESAS y ORDEN")
    ap.add_argument("--fecha", help="Fecha del evento (YYYY-MM-DD). Default: hoy.")
    ap.add_argument("--titulo", default="Quincho", help="Rótulo del evento.")
    ap.add_argument("--debug", action="store_true",
                    help="No escribe en Firebase: imprime lo que subiría.")
    ap.add_argument("--borrar", action="store_true",
                    help="Borra el plano de Firebase (después del evento).")
    args = ap.parse_args()

    if args.borrar:
        if args.debug:
            print(f"[quincho] --debug: borraría {DB_URL}/{FB_PATH}")
            return
        fb_delete(get_token(), FB_PATH)
        print(f"[quincho] {FB_PATH} borrado de Firebase.")
        return

    if not args.from_html:
        raise SystemExit("[quincho] Falta --from-html (o usá --borrar).")

    mesas, orden = parse_html(args.from_html)
    doc = {
        "fecha": args.fecha or datetime.date.today().isoformat(),
        "titulo": args.titulo,
        "orden": orden,
        "mesas": mesas,
        "actualizado": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
    }

    total = sum(m["total"] for m in mesas)
    print(f"[quincho] {doc['fecha']} — {len(mesas)} mesas · {total} viajeros")
    for n in orden:
        m = next(x for x in mesas if x["n"] == n)
        marca = " (grupo)" if m.get("grupo") else ""
        print(f"  {m['pos']:>2}ª  mesa {m['n']:<2} {m['titulo']}{marca} — {m['total']}p")

    if args.debug:
        print("\n[quincho] --debug: no se escribió nada en Firebase.")
        print(json.dumps(doc, ensure_ascii=False, indent=2)[:600] + "\n  …")
        return

    fb_put(get_token(), FB_PATH, doc)
    print(f"[quincho] subido a {DB_URL}/{FB_PATH}")


if __name__ == "__main__":
    main()
