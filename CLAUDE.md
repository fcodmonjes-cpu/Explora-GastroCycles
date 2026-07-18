# CLAUDE.md — Cómo trabajamos en este repo

> Guía operativa para cualquier asistente (Fable, Opus, Sonnet, o el que sea)
> que colabore en **The ATA Handbook**. No repite la arquitectura del código:
> para eso, **`ARCHITECTURE.md` es la fuente de verdad** — léela completa antes
> de tocar el área que vas a modificar. Este archivo cubre el *flujo de trabajo*
> y las convenciones que no se derivan del código.

## El proyecto en una línea

Handbook digital de operaciones F&B para Explora Atacama: single-page vanilla
HTML/CSS/JS (`index.html`, un solo archivo), Firebase Realtime Database para
datos vivos, deploy en Vercel por branch. Sin framework, sin build step.
Trilingüe ES/EN/PT. Ver `ARCHITECTURE.md` §1-§11.

## Idioma

- **Con el owner: español.** Comentarios de código en español (salvo términos
  técnicos universales). Toda string visible al usuario existe en los 3 idiomas
  del diccionario `UI` (ES/EN/PT). **No auto-traducir** — si falta un idioma
  para un módulo nuevo, proponer la traducción y marcarla para revisión.

## Reglas duras (romperlas rompe la operación o la confianza)

1. **Nunca commit ni push directo a `main`.** `main` es producción en vivo del
   lodge. Solo recibe merges desde `staging`, y **solo con aprobación explícita**
   del owner ("apruebo" / "súbelo a producción" / "mergea a main"). Ambigüedad →
   preguntar. Única excepción: hotfix urgente que el owner acelera a mano.
2. **Trabajo nuevo siempre en `feature/*` o `fix/*`** (ramas efímeras, una por
   unidad de trabajo; se borran tras merge). QA en `staging` (URL fija de Vercel
   que el owner revisa desde iPhone), preferentemente por fast-forward.
3. **Sin dependencias nuevas** (npm, build tools, frameworks) sin discutirlo.
4. **Sin cambios de paleta ni tipografías** sin avisar. Paleta: Cormorant
   Garamond + Courier Prime, dark amber. Cualquier **color o elemento visual
   nuevo** (p.ej. banderas emoji) se avisa antes — la estética es "destaca sin
   gritar" (disciplina de sutileza). Para decisiones de UX/estética que son del
   owner (default de un control, meter color nuevo), usar el flujo de pregunta
   con opciones/preview en vez de decidir solo.
5. **Firebase es una sola base de PRODUCCIÓN compartida** por todos los entornos
   (main/staging/previews/local). No gatillar escrituras desde local sin avisar;
   para QA local sin contaminar, monkey-patch de `fetch` sobre los paths que
   escriben. Ver `ARCHITECTURE.md` §4.

## Filosofía (guía de decisiones)

La **fricción de operación es el enemigo**: cada feature se mide en taps a hora
pico. Default permisivo, nunca muros; acceso rápido transversal (un buscador que
salta niveles vence a un laberinto de navegación). "El detalle, a mano": lo que
importa accesible, lo decorativo no se nota. Ver `ARCHITECTURE.md` §11.

## Validación antes de decir "listo"

Toolkit local (todo ya instalado, sin agregar deps) — detalle en
`ARCHITECTURE.md` §12:

- Paridad de backticks = 0 · cero bytes NUL.
- `node --check` sobre los `<script>` inline (Node v24 disponible).
- Screenshot de render real con **Chrome/Edge headless** vía un *harness* que
  reusa el `<style>` real. Caveat: los emoji de bandera **no renderizan en
  Windows** — ese detalle solo se valida en iPhone/staging.
- Scripts `sync_*.py`: correr con `PYTHONUTF8=1` en Windows; validar con
  `--debug` (no escribe Firebase).
- La prueba final: cargar la página (local o preview) y, para lo que solo se ve
  en iOS, el QA del owner desde iPhone.

## Datos vivos (scripts de sync)

`scripts/sync_rol.py` (staffing/roster) y `scripts/sync_viajeros.py` (dietas por
hab) bajan Excel de SharePoint → normalizan → escriben Firebase con service
account. Viajeros corre hoy sobre un **seed placeholder**; la **fase 2** (Excel
real) tiene el plumbing `--from-excel` listo — falta el link (secret
`VIAJEROS_SHAREPOINT_URL`) y mapear columnas en `parse_excel()`. Pasos en la
cabecera de `sync_viajeros.py`.

## Roles

- **Francisco** — desarrolla y conversa con el asistente.
- **Bruno** — revisa desde iPhone y aprueba los merges a producción.

## Hand-off entre sesiones

El estado del trabajo vive en **branches + commits**; las decisiones de diseño
en **`ARCHITECTURE.md`**; las preferencias del owner y convenciones operativas en
la memoria persistente del asistente. Al arrancar: `git status --short --branch`
para saber dónde estás; si estás en `main` por error, salí antes de tocar nada.
Al retomar "lo de X": `git log feature/X --oneline` + `git diff main feature/X`.
