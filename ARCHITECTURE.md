# The ATA Handbook — Arquitectura

> Un handbook digital de operaciones F&B para Explora Atacama.
> Single-page, vanilla, sincronizado en tiempo real vía Firebase.
> Sirve como referencia para extender el programa con menos fricción
> y como documento explicativo para terceros.

---

## 1. Resumen en una página

**Qué es.** Una herramienta interna del salón que vive en una sola URL
(`gastrocycles.company`). Trilingüe (ES/EN/PT). Cinco vistas operativas
sobre un mismo header común. Sin framework, sin build step, sin
servidor propio: HTML/CSS/JS plano servido por GitHub Pages, con
Firebase Realtime Database como capa de datos en vivo para todo lo
que es operacional (turnos, postres, pedidos, comandas).

**Para qué sirve hoy.**

- Consulta del menú rotativo D1-D4 con alérgenos y maridajes
- Fichas de vinos con guion de venta por categoría
- Manual de coctelería (con o sin alcohol)
- Manual de café + sistema mesero ↔ barista para pedidos al espresso
- Comandera de mesa (E-Check) PIN-gateada para registrar pedidos
- Panel operativo (roster del turno + clima de terraza para el montaje)
- Ventana viva de tips de vino, intercalada en el listado de platos
- Corcho digital de viajeros: dietas, alergias y restricciones por
  habitación, con filtros y contadores (módulo `viajeros`)

**Lo que la hace diferente de una "página web informativa".**

- Datos operativos vivos: turnos sincronizados desde Firebase, comandas
  sincronizables entre meseros en distintos dispositivos.
- Arquitectura extensible: agregar una familia nueva de productos
  (jugos, empanadas, sodas) son dos líneas en una sola tabla.
- Patrones de UI optimista + cola de escritura coalescente: los taps
  se sienten instantáneos aunque la red sea lenta.
- Trilingüe con un solo diccionario y un sistema de hooks que evita
  que módulos nuevos rompan los existentes.

---

## 2. Stack

| Capa | Tecnología | Justificación |
|---|---|---|
| Renderizado | HTML + CSS + JS vanilla | Cero build step. Editar = desplegar. Cualquier persona puede leer el código. |
| Datos en vivo | Firebase Realtime Database (compat SDK 10.12) | WebSocket para tiempo real + REST para fetches puntuales. Reglas abiertas en prototipo, fáciles de lockear con auth para producción. |
| Hosting | Vercel (auto-deploy por branch) | `main` → `gastrocycles.vercel.app` (producción). `staging` → URL fija para QA desde iPhone. `feature/*` y `fix/*` → preview por commit. Ver sección 12. |
| Tipografía | Cormorant Garamond (italic 500/700) + Courier Prime monospace | Cargadas vía Google Fonts. Family declarada en CSS desde el inicio; sólo recientemente se cargó la real. |
| Instalable | PWA: `manifest.webmanifest` + `sw.js` (service worker propio, ~50 líneas) | Se agrega al home screen y abre sin chrome del browser. Network-first: el cache es red de emergencia, no fuente de verdad. Ver §2.1. |
| Clima | Open-Meteo (REST, sin API key) | **Único tercero fuera de Firebase.** Gratis, CORS abierto y sin registro — en una app sin build step, una API key quedaría visible en el HTML. Si cae, el módulo se apaga solo. Ver §3.2. |
| Telemetría | Vercel Analytics (`/_vercel/insights/script.js`) | Pageviews ligeros, sin más. Da 404 en local — solo existe en el deploy de Vercel. |

**Por qué no hay framework.** El programa es lo bastante chico para que
el costo cognitivo de un framework supere su beneficio. Lo bastante
grande para que algunas convenciones internas hagan la diferencia.
La complejidad la maneja la disciplina de patrones, no la dependencia.

### 2.1 PWA — el handbook instalado en el home screen

**Está activa, no es potencial.** El garzón agrega el handbook a la
pantalla de inicio y se abre sin barra de URL ni pestañas, como una app.
Tres archivos en la raíz la sostienen, ninguno con build step:

| Archivo | Rol |
|---|---|
| `manifest.webmanifest` | Nombre, `display:standalone`, colores, y los íconos de Android/Chrome. |
| `sw.js` | Service worker. **Network-first**, cache solo como red de emergencia. |
| `index.html` `<head>` | Metas `apple-*` + `apple-touch-icon`. En iOS mandan estas, no el manifest. |

**Por qué network-first y no cache-first.** Es la decisión que define el
service worker y va contra el default de la mayoría de las PWA. Esto es
una herramienta de operación en vivo: mostrar un menú viejo a hora de
servicio es peor que no mostrar nada. Siempre se pide a la red primero;
el cache entra solo cuando se cae el wifi del lodge. Por lo mismo el SW
**no toca Firebase ni terceros** — los datos vivos nunca se cachean.

**Los íconos llevan versión en el nombre** (`icon-180-v2.png`, …). iOS y
el service worker guardan el ícono por URL: un archivo reescrito en sitio
NO se actualiza en un teléfono que ya tiene la app instalada. Al cambiar
el arte hay que subir el sufijo en los tres lugares —
`index.html`, `manifest.webmanifest` y el `CORE` de `sw.js` — y subir
también `CACHE` (`ata-handbook-vN`), sin lo cual el `activate` del SW no
descarta el bucket viejo. **Aun haciendo todo bien, un iPhone que ya tiene
la app en el home screen no relee el ícono: hay que borrarla y volver a
agregarla.** El contenido sí se actualiza solo.

El `maskable` es un archivo **propio**, con el lockup al 78 %: Android
recorta a un círculo del 80 %, así que reusar ahí el ícono `any` (como se
hacía hasta 2026-08-16) le comía los bordes a la marca.

**El arte es el telón de intro destilado** — ATA en sienna sobre una regla
dorada que mide justo el ancho de HANDBOOK. El favicon NO lo copia y sigue
siendo la "A.": a 16 px en una pestaña un lockup de tres partes es una
mancha. Cada contexto usa la marca que aguanta su tamaño.

---

## 3. Las cinco pantallas (topología)

Header común arriba (título + subtítulo + selector de idioma + logo).
Debajo, un wrapper "ops-strip" con el **clima de terraza** (módulo `wx`,
§3.2) y el panel de staffing (turno activo, viajeros). Después, la fila
de tabs:

```
┌─────────────────────────────────────────────────────────────┐
│ The ATA Handbook                              [ES][EN][PT]  │
│ El detalle, a mano.                                          │
├─────────────────────────────────────────────────────────────┤
│  22° · ráfagas 53 km/h 15:00                        2.450 m │  ← wx
├─────────────────────────────────────────────────────────────┤
│  AM            72 VIAJEROS                                   │
│  Senior  Percy                                               │
│  Comedor Nicolás · Sebastián · Diego · Viviana              │
│  Apoyo   Victor                                              │
├─────────────────────────────────────────────────────────────┤
│ [Menú] [Vinos] [PGO] [Comande] [Rol] [Café]                 │
└─────────────────────────────────────────────────────────────┘
                    (contenido de la tab activa)
```

**Los tips de vino ya no viven acá.** Hasta el 2026-08-16 `winetips`
ocupaba la ops-strip; desde entonces se aloja **dentro del listado de
platos**, justo antes de Principales (ver §3.1). El tip le habla al plato
que viene, así que se lee donde se está eligiendo qué recomendar. El
mecanismo que lo hace posible —mover un nodo con estado vivo a través de
un `innerHTML`— es el patrón **park/place** de §5.

| Tab | Propósito | Datos | PIN |
|---|---|---|---|
| **Menú** | Servicio del día (Almuerzo · Cena · Bar) con matriz de restricciones por plato | Estático en el JS (`DISHES`, `BAR_DISHES`) | — |
| **Vinos** | Ficha por vino + sub-vista "Maridajes generales" | Estático (`WINES`, `GUIONES`) | — |
| **Café** | Manual de bebidas + modo servicio (mesero / barista) | Estático (`COFFEE_DATA`) + Firebase `/orders` | 555 (mesero) · 999 (barista) |
| **E-Check** | Comandera por mesa · **mapa espacial de asientos** | Firebase `/comandas/{date}/{id}` | 666 |
| **Viajeros** | Dietas/alergias/restricciones por hab + filtros y contadores | Firebase `/viajeros/current` (read-only; escribe `scripts/sync_viajeros.py`) | — |

Los datos del Café (módulo Service Mode) y los del E-Check tienen su
propia capa de Firebase. Del header, **staffing** escribe/lee Firebase; la
**ventana de tips de vino** es 100% estática (sin Firebase) y el **clima**
no toca Firebase tampoco: sale de Open-Meteo (§3.2). Los módulos
**Postres/86** quedaron latentes el 2026-06-22 (ver §4).

### 3.1 La vista Menú (rediseño del 2026-08-10)

Con el cambio de menú, el almuerzo pasó de 4 platos a **14** (buffet de 6
bandejas + sopa + 4 opciones principales + 3 postres). Un listado vertical
deja de servir a esa escala, así que la vista **corta primero por servicio**
y recién después se lee:

```
[ buscar plato, ingrediente o guion ]
 D1   D2   D3·hoy·   D4          ← en BAR se reemplaza por "Carta fija",
┌──────────────────────────────┐    del mismo alto: nada se mueve
│ ALMUERZO │  CENA  │   BAR    │  ← autodetecta por hora
└──────────────────────────────┘
    (sólo en BAR)  [COMIDA][TRAGOS]
BUFFET ──────────── 6 bandejas
  ┌ HOJAS ─┐ ┌ VEG.FIRMES ─┐   ← slots FIJOS: la bandeja no cambia,
  └────────┘ └─────────────┘      cambia el plato que la ocupa
SOPA DEL DÍA ─── (ancho completo)
─ TERROIR · tip de vino ────── ← hueco de winetips (park/place, §5)
PRINCIPALES ─ 4 · POSTRES ─ 3
```

El hueco de los tips cae **justo antes de Principales** en los dos
servicios: bajo la sopa en Almuerzo y bajo la entrada en Cena — misma
posición relativa. En **BAR no se muestra**, y es deliberado: esa carta no
tiene sopa ni principales donde anclarlo. En búsqueda tampoco.

**Dos ideas la sostienen.**

*La línea, no la lista.* El buffet es un objeto físico de seis bandejas en un
orden que no cambia nunca. Se dibuja como grilla de slots fijos (`BUFFET_SLOTS`)
en vez de como lista: el garzón aprende una vez dónde está cada bandeja y eso
queda cierto para siempre. Es el mismo movimiento que el mapa de asientos del
E-Check — espacializar en vez de listar.

*La matriz invertida — y por qué su control se retiró.* El PDF del asesor dice
"buscá tu plato y leé su fila de ✓/✗". La app respondía "decime la restricción
y la línea se apaga sola": el garzón prendía ejes en una lente —o tocaba
**"desde una hab"**, y `VJ_TAG_TO_AXIS` traducía los tags reales del viajero
a ejes— y los platos que no servían se atenuaban sin desaparecer.

**Esa lente se retiró de pantalla el 2026-08-17.** El owner reportó que en
servicio real prácticamente nadie la usaba, y ocupaba una fila entera de la
vista más cargada del programa. Quedó **latente** igual que Postres/86:
`menuLensHtml()` está intacta y reactivar son dos líneas descomentadas en
`menuRenderChrome`; `MENU_DIET_LENS` simplemente nunca se llena.

**Lo que NO se fue con ella, y es la mayor parte del valor:** la matriz sigue
leyéndose en cada plato. El `✓*` y el borde punteado de "sin dato" no dependían
de la lente — se pintan siempre. El `✓*` sigue siendo lo más útil de la
pantalla porque es una acción ejecutable ("sirve el pollo aparte"). Lo que se
perdió es el filtrado *interactivo*, no la información.

La lección vale más que el feature: la lente era una buena idea de diseño que
la operación no adoptó. Se mide en taps a hora pico (§11), no en elegancia.

**La regla de oro de la matriz** (vive entera en `dietVerdict` + `menuHasMatrix`):
`1` apto · `0` no apto · `'*'` apto con condición (obliga a tener su texto en
`dietNotes`) · **ausente = sin dato**. Un plato sin datos JAMÁS se pinta como
apto: se marca con borde punteado y "consultar cocina". Hoy aplica a los
principales del almuerzo y a toda la cena, que se mantienen hasta fin de mes, y
a los ejes que el Guion de Bar no declara. Silencio significa apto sólo donde
hay matriz completa — por eso no existe un chip verde de "apto".

**El bar absorbió Cocktails.** Toda la carta de bar (comida + tragos) vive en el
segmento BAR; la tab Cocktails desapareció de `.main-tabs` (de 7 a 6 tabs) y
`setTab('cocktails')` quedó como alias que entra a BAR › Tragos.
`renderCocktails()` no cambió: sólo cambió de casa.

**Mapa de mesa (E-Check).** La pantalla activa de la comandera es un
**diagrama espacial**: los comensales se eligen tocando su asiento en un
plano de la mesa, no una fila de números. `seatConfig = { shape, hasHead }`
en cada mesa define la forma (`rect` / `round` / `couple`) y si hay
cabecera; se ajusta en vivo desde el ⚙ del mapa. La geometría la calcula
`comandaSeatLayout(diners, shape, hasHead)` (coordenadas 0–100 %):
numeración horaria con asiento 1 = cabecera (si hay) o el de tu izquierda.
**El n° de asiento ES el `dinerN`** — el mapa solo cambia la presentación,
no la identidad del item, así que el motor de pedidos/batches/tally queda
intacto. La "comanda completa" es ahora una **vista única** (sin toggle):
tira de totales por producto para cocina + detalle por asiento con las
notas/pedidos especiales siempre visibles y sin hora de envío.

### 3.2 Clima de terraza (módulo `wx`)

Primer elemento bajo el header, **una sola línea**, visible desde
cualquier tab:

```
22° · ráfagas 53 km/h 15:00                          2.450 m
```

**No muestra "el clima": muestra el pico de ráfaga de la ventana de
almuerzo.** El almuerzo se sirve en la terraza y lo que arruina un montaje
no es el frío sino la ráfaga, que en San Pedro tiene una curva diaria muy
marcada — entra pasado el mediodía. El dato accionable es *cuánto va a
soplar entre las 12 y las 16, y a qué hora*, no la temperatura.

| Decisión | Por qué |
|---|---|
| **Open-Meteo**, sin API key | Único tercero fuera de Firebase. CORS abierto y sin registro: en una app sin build step, una key quedaría visible en el HTML o exigiría un proxy. |
| Umbrales **30** (gold) / **45** km/h (coral) | Bajo 30 la ráfaga ni se nombra: la línea dice temperatura y viento. Aparece algo que leer sólo cuando hay algo que decidir. |
| Los dos datos **se turnan**, no compiten | En calma manda el viento actual; con ráfaga sobre umbral ella toma el lugar. Además es lo que hace que la línea entre en el ancho de un iPhone. |
| Si el servicio de hoy ya pasó, muestra **mañana** | A las 18:00, saber que hubo viento a las 14:00 no sirve para montar nada. Corta en `nowHour >= WX_LUNCH_TO`. |
| Altitud **fija** (2.450 m), no del pronóstico | Es un dato del lodge: se muestra siempre, aun sin red. Open-Meteo reporta 2.444 m para la celda, lo que la confirma. |
| Cache en `localStorage`, 20 min | Evita pegarle a la API en cada carga y sobrevive cortes cortos. |

**Alto fijo, no negociable.** El bloque vive **arriba de `.main-tabs`** y
los datos llegan por red *después* del primer paint. Sin alto reservado,
las tabs saltan bajo el dedo del garzón justo al llegar el pronóstico —
pasó, medido en 23 px. Se verifica midiendo el Y de `.main-tabs` en los
estados *cargando · sin red · calmo · ojo · alerta*, más el peor caso de
largo (ráfaga de 3 dígitos + "mañana"): debe ser idéntico en todos.

Si Open-Meteo cae, el módulo se apaga solo (`WX_ERROR`) y el resto de la
ops-strip queda intacto. Estado en STATE TOP (`WX_LAT`, `WX_ALT_M`,
`WX_GUST_*`, `WX_LUNCH_*`, `WX_DATA`); sin Firebase.

---

## 4. Arquitectura de datos en Firebase

Cinco paths bajo el mismo proyecto Firebase. Cada uno con su propio
ciclo de vida y patrón de retención:

```
explora-cafe-orders-default-rtdb.firebaseio.com/
│
├── staffing/                      ← roster mensual del salón
│   └── {YYYY-MM}/
│       └── {dia} → { viajeros, geo_senior_am, geo_senior_pm,
│                     geos_am, geos_pm, apoyo_am, apoyo_pm }
│
├── desserts/                      ← postres rotativos por servicio (LATENTE 2026-06-22)
│   └── {YYYY-MM-DD} → { helado, sorbet, fruta[], ninos, enteredAt }
│       (auto-purge >4h · ya no se escribe/lee desde la UI: el módulo y su
│        strip se retiraron al poner los tips de vino; código intacto, igual
│        que /eightysix, reactivable según comentarios "LATENTE Postres/86")
│
├── viajeros/                      ← dietas y restricciones por habitación
│   └── current → { date, updatedAt, source,
│                   habs: { "01": [ { id, nombre, edad, nac, grupo,
│                                     in, out, tags[], obs, foto? } ] } }
│       (un solo doc sobrescrito por cada sync; lo escribe
│        scripts/sync_viajeros.py --from-pgo, automático cada día 10:00 UTC
│        (06:00 en Chile) vía .github/workflows/sync-viajeros.yml. El seed
│        manual (SEED_ROWS) y --from-excel quedan como respaldo. Read-only en
│        la app, sin PIN. Tags canónicos alergia-*/dieta-*/cond-* compartidos
│        script ↔ VJ_TAGS — ver §4.1)
│
├── orders/                        ← cola viva del café (mesero → barista)
│   └── {auto-id} → { items[], table, timestamp, status:'pending', lang }
│
├── orders_history/                ← historial de café completado
│   └── {YYYY-MM-DD}/
│       └── {auto-id} → { …, completedAt, prepMs }
│       (auto-purge >30 días)
│
└── comandas/                      ← E-Check: comandas por mesa
    └── {YYYY-MM-DD}/
        └── {auto-id} → { mesa, diners, openedAt, closedAt,
                          timerStartedAt, items[] }
        (auto-close >12h sin actividad, auto-purge >30 días)
```

**Reglas de Firebase actuales.** Abiertas (`{".read":true,".write":true}`).
Apropiado para un prototipo interno; el día que esto suba a producción
real con múltiples hoteles, se cierran con autenticación. La estructura
ya está particionada por fecha/mes para facilitar reglas granulares
después.

**Auto-purga.** Todo módulo que escribe datos temporales tiene su propia
auto-purga client-side: cuando un cliente entra a la vista, revisa
qué buckets/entradas están fuera de la ventana de retención y los borra.
Eventually consistent, no necesita Cloud Functions ni cron. El barista
de cualquier turno mantiene la base limpia por el simple hecho de
abrir la app.

### 4.1 Sync de viajeros desde PGO (automático desde 2026-07-30)

`/viajeros/current` ya no se llena a mano. `scripts/sync_viajeros.py
--from-pgo` entra al portal PGO con Playwright + Chromium headless, lee el
**Reporte Geos** (roster completo: hab, nombre, nac, edad, grupo, IN/OUT) y
**Dietas** (observaciones), los cruza por nombre normalizado y escribe el doc.
Corre solo cada día a las **10:00 UTC** (06:00 en Chile, antes del desayuno)
y también a mano desde Actions con `date` / `dry_run`.

**Secrets** (Settings → Secrets → Actions): `PGO_BASE_URL`, `PGO_USER` (es el
**RUT**, no un nombre de usuario), `PGO_PASS`, `FIREBASE_KEY`.

**Las trampas de PGO — cada una costó una corrida, no re-descubrirlas:**

| Síntoma | Causa real |
|---|---|
| `ERR_NAME_NOT_RESOLVED` | El apex `pgo-explora.com` no tiene DNS; sólo existe `www.`. El navegador oculta el "www." al mostrarlo. El script hace fallback automático. |
| Login falla con credenciales correctas | El campo de RUT está **enmascarado**: `fill()` setea el valor de una sola vez y el componente lo descarta. Hay que tipear tecla por tecla (`type(delay=45)`). |
| La grilla dibuja el encabezado pero sin filas | PGO abre en **Torres del Paine**. Sin cambiar el destino a Atacama, todo reporte sale vacío. |
| No se encuentra el menú de destinos | Está oculto hasta abrirlo, y **`innerText` devuelve `''` para elementos sin layout**. Todo el matcheo de menús cerrados va por `textContent`. |
| El menú "no existe" justo después del login | La SPA monta la cabecera unos segundos tarde. Se navega primero al reporte y se reintenta hasta 20s. |
| La fecha se escribe en el buscador | PGO es **Element UI (Vue)**. El campo de fecha se ubica por su *valor* (regex `DD-MM-YYYY`), no por clase ni por `input[type=text]`. |
| El calendario se lee como tabla de datos | Element UI usa `<table>` para el date-picker. El extractor puntúa por encabezados esperados y excluye clases `date-table|picker|calendar`. |
| El encabezado aparece sin filas | Element UI parte la grilla en **dos tablas** (header y body); se unen por cantidad de columnas. |
| Un secret vacío pisa el valor por defecto | `os.environ.get(k, default)` devuelve `""` si la variable existe vacía — GitHub siempre la inyecta. Usar `os.environ.get(k) or default`. |
| El botón "Run workflow" no aparece en Actions | `workflow_dispatch` sólo se muestra cuando el archivo está en la rama **default** (`main`). Por eso estos workflows se iteran en `main`. |

**Dos comportamientos del negocio, no bugs:** PGO abre por defecto en el **día
siguiente** (por eso el cron pasa `--date` con la fecha de hoy), y el reporte
de **Dietas lista el movimiento del día**, no a todos los in-house — el
`comentario geos` quedó cableado como segunda fuente (sólo se usa si normaliza
a una dieta conocida, para no ensuciar el campo visible), pero al 2026-07-30
venía vacío. **Pendiente de QA:** contrastar a mano si faltan dietas de
huéspedes que llegaron días antes.

**Para depurar sin adivinar:** el script imprime un *mapa de estructura* de la
página (tablas, encabezados, contenedores repetidos, clases) cuando no
encuentra la grilla — sólo metadatos, nunca datos de huéspedes. Los inputs
`dump_html` / `trace_net` del workflow guardan HTML y llamadas XHR; **el HTML
tiene datos personales**, por eso `retention-days: 1`.

**Próximo paso (diferido a pedido del owner):** extraer más campos del viajero
(preferencia de agua, vinos, special requests) para una ficha rica. Lo difícil
declarado no es guardarlos, sino **cómo esa información interactúa con el
resto de la app**.

---

## 5. El patrón "módulo"

Cada feature operativo del programa (staffing, desserts, café orders,
comandera) sigue **el mismo patrón estructural**. Esto es lo que hace
el código predecible:

```
┌─ STATE TOP ─────────────────────────────────────────┐
│ const MODULE_PATH = 'firebase/path'                  │
│ const MODULE_RETENTION_MS = ...                      │
│ let   MODULE_DATA = null                             │
│ let   MODULE_VIEW = 'default'                        │
└──────────────────────────────────────────────────────┘
              │
              ↓
┌─ MÓDULO (más abajo en el script) ───────────────────┐
│ // Comentario de contrato: path, shape, lifecycle    │
│                                                       │
│ function moduleFetch()    { /* REST GET */ }         │
│ function moduleRender()   { /* DOM write */ }        │
│ function modulePersist()  { /* REST PATCH/PUT */ }   │
│ function modulePurge()    { /* eventual cleanup */ } │
│                                                       │
│ setInterval(...)          // polling / tick          │
│ onI18nChange(moduleRender) // hook registry          │
└──────────────────────────────────────────────────────┘
              │
              ↓
┌─ BOOT (al final del script) ────────────────────────┐
│ moduleFetch()                                         │
└──────────────────────────────────────────────────────┘
```

Lo importante: el **STATE TOP** está en la parte superior del script,
con un comentario muy explícito de "hard rule, not a suggestion". Las
funciones pueden vivir donde quieras (se hoistean). El estado, no.

> **Esta regla nació de un bug real.** Una vez declaré un `let` del
> staffing module en medio del script y la función `staffingRender()`
> se llamó desde `setLang()` ANTES de que esa línea se ejecutara. JS
> tira `ReferenceError`, haltea TODO el script, y todos los `let`/`const`
> declarados DESPUÉS quedan en Temporal Dead Zone para siempre. La
> consecuencia: tabs vacías al hacer click, módulos enteros no funcionan.
> La regla salió de esa cascada.

### Sub-patrones recurrentes

**i18n hook registry** (`__i18nHooks` + `onI18nChange`). En lugar de que
`setLang()` conozca a cada módulo por nombre, los módulos se registran
solos. `setLang` itera el array con try/catch — un módulo roto no
arrastra a los otros.

```js
// Cada módulo, al final de su bloque:
onI18nChange(comandaRender);

// En setLang:
__i18nHooks.forEach(fn => { try { fn(); } catch(e){ console.warn(...); } });
```

**Optimistic UI + write queue coalescente.** El usuario tapea, el render
se actualiza al frame siguiente; la escritura a Firebase corre en
background. Si tapeas 5 productos rápido, no se disparan 5 PATCHes en
paralelo: la cola coalese y manda uno solo con el estado final.

```js
let _CMD_WRITE_PENDING  = null;
let _CMD_WRITE_INFLIGHT = false;

function comandaPersist(patch){
  _CMD_WRITE_PENDING = Object.assign(_CMD_WRITE_PENDING || {}, patch);
  if (_CMD_WRITE_INFLIGHT) return;            // active loop will pick it up
  return _comandaPersistDrain();
}
```

**Polling con skip-on-interaction.** El polling de sincronización entre
dispositivos NO re-renderea si el usuario está interactuando (input
con focus, gesto reciente). 2.5 segundos de calma y la sincronización
resume.

**Source Resolvers** (E-Check). El catálogo del comandera no está
hardcodeado: es un array de "fuentes" cada una con un resolver. Para
agregar jugos al programa son DOS líneas, una para los datos y otra
para registrar el resolver.

```js
const COMANDA_SOURCES = [
  { key:'dishes',    labelKey:'cmdSourceDishes',    icon:'🍽',
    items: () => DISHES.filter(...).map(...) },
  { key:'wines',     labelKey:'cmdSourceWines',     icon:'🍷',
    items: () => WINES.map(...) },
  // ↓ agregar familia nueva aquí:
  // { key:'juices', labelKey:'cmdSourceJuices', icon:'🥤',
  //   items: () => JUICES.map(...) }
];
```

**Park / place** (alojar un nodo con estado vivo dentro de un render que
usa `innerHTML`). El módulo `winetips` tiene estado que no vive en
variables sino **en el propio nodo**: un timer de 15 s, la animación del
hilo dorado y el cross-fade. Cuando pasó a mostrarse dentro del listado de
platos (§3.1), apareció el conflicto: `renderDishes()` reescribe
`grid.innerHTML`, y todo nodo que esté adentro se destruye.

La solución no es re-crearlo (perdería el estado) sino **moverlo**:

```js
// El HTML del menú sólo deja un HUECO vacío…
function winetipsSlot(){ return '<div id="winetips-slot"></div>'; }

// …y el nodo real entra y sale de él. appendChild MUEVE, no clona:
// conserva listeners, timers y animaciones en curso.
function winetipsPark(){    // ANTES de cada innerHTML → a la casa oculta
  const n = document.getElementById('winetips');
  const home = document.getElementById('winetips-home');
  if (n && home && n.parentNode !== home) home.appendChild(n);
}
function winetipsPlace(){   // DESPUÉS del render → al hueco, si lo hay
  const n = document.getElementById('winetips');
  const slot = document.getElementById('winetips-slot');
  if (n && slot && n.parentNode !== slot) slot.appendChild(n);
}
```

> **El park es la mitad que se olvida.** Sin él, el primer render se ve
> perfecto —el nodo entra al hueco— y **el segundo lo mata**: el
> `innerHTML` lo borra con el resto y a partir de ahí `getElementById`
> devuelve `null` para siempre. El bug no se ve en pantalla al primer
> vistazo; se detecta consultando el DOM tras varios renders seguidos.
> Regla: **park antes de tocar `innerHTML`, place después.** Ambas
> idempotentes, así llamarlas de más no cuesta nada.

Cuando no hay hueco (Bar, búsqueda, otra tab) el nodo se queda en su
contenedor "casa" oculto, que existe justo para eso.

**DOM diff** (no innerHTML completo). En la cola del barista, en lugar
de reescribir todo el listado en cada update, el render diff-ea: solo
agrega tarjetas nuevas, anima la salida de las que se completaron, y
deja intactas las que ya están en pantalla. Conserva el scroll, el
estado abierto/cerrado, y evita el "flash" que destruye gestos.

---

## 6. Convenciones que valen la pena

| Convención | Por qué importa |
|---|---|
| Toda string de UI vive en el diccionario `UI` con 3 idiomas | Cambiar un texto no requiere tocar HTML. `setLang()` corre en boot y refresca todos los labels desde el diccionario. |
| `setLang()` se llama en boot con el idioma activo | Garantiza que el primer paint use el diccionario, no el texto hardcoded del HTML. Si en el futuro cambias una string sin tocar el HTML, igual aparece bien. |
| Cualquier `let`/`const` accesible desde `setLang()` o el boot va en STATE TOP | Evita el bug TDZ que halta el script entero. |
| Cada módulo abre con un comentario de contrato | Path en Firebase, shape del documento, ciclo de vida. Cuando vuelvas en 6 meses, no tienes que grep para entender. |
| Reuso de componentes entre módulos | El numpad del PIN del Café se reusa en E-Check. Los modales (note edit, full view) comparten estilos. Los timers de "elapsed time" del barista y del E-Check usan la misma lógica de color (gold → naranja → rojo). |
| Acentos de color como lenguaje visual | Gold = bebida principal · Azul = modifier seleccionado (leche, comensal activo) · Verde = sin alcohol (mocktails) · Rojo claro = "coming soon" (Momentos) · Sienna (`#c75c2a`) = brand mark (ATA) |
| `overflow-x: clip` (no `hidden`) en html+body para matar el side-scroll en iOS | Bug real (2026-06-22): `hidden` no impide el paneo lateral en iOS Safari cuando un descendiente desborda por pocos px. `clip` no crea contenedor scrolleable ni admite pan táctil. Se deja `hidden` antes como fallback. El scroll-x propio de `.main-tabs` (su `overflow-x:auto`) no se ve afectado. |

---

## 7. Cómo extender el programa (recetas concretas)

### Receta 1: Agregar un plato al menú

```js
// Buscar el array DISHES y agregar:
{
  id: 'd61',                              // único
  day: '3',                               // D1 / D2 / D3 / D4
  service: 'Cena',                        // 'Almuerzo' / 'Cena' / 'Almuerzo y Cena'
  course: 'Plato principal',              // 'Entrada' / 'Plato principal' / 'Postre'
  name: 'Pulpo a la parrilla',
  desc: 'Descripción del plato. Alérgenos: Mariscos.',
  allergens: ['Mariscos'],
  wines: ['talinay', 'aquitania'],        // ids de WINES que maridan
  why: {
    talinay: 'Salinidad cítrica para el pulpo.',
    aquitania: 'Volumen del Chardonnay con la grasa del marinado.'
  }
}
```

Listo. Aparece en el menú del Día 3, cena, plato principal, con los
maridajes wireados a la ficha de cada vino.

### Receta 1b: Agregar un plato con matriz de restricciones

Los platos del cambio de menú 2026 viven en tres arrays propios
(`MENU_BUFFET`, `MENU_SOPAS`, `MENU_POSTRES`) que se empujan a `DISHES` al
final del bloque de datos, más `BAR_DISHES` para la carta fija del bar.

```js
{
  id:'bf1-hojas',            // id estable y legible (no correlativo)
  day:'1',                   // DÍA DEL DOCUMENTO — se traduce al día de la
                             // app con MENU_CYCLE_OFFSET al entrar a DISHES
  slot:'hojas',              // slot fijo: ver BUFFET_SLOTS / POSTRE_SLOTS
  recipeDay:'1',             // ficha técnica de cocina (≠ día de servicio)
  name:'César de Lechuga Costina, Pollo Ahumado y Pan Gratato',
  short:'César',             // nombre corto para la ficha y la comanda
  diet:{veg:0, vgt:'*', pesc:1, mar:1, fs:1, lac:0, ge:0, gs:'*', halal:1},
  dietNotes:{ vgt:'Sin el pollo ni el pan gratato...' },   // obligatorio si hay '*'
  brief:'…',                 // explicación breve — se dice en voz alta
  extended:'…',              // explicación extendida — se lee si preguntan
  barTwin:'bar-cesar'        // 💡 hermana en la otra carta (o lunchTwin)
}
```

Reglas duras al cargar la matriz:

1. **Se transcribe, no se infiere.** El eje que el documento del asesor no
   declara se **omite** — se verá como "sin dato · consultar cocina". Escribir
   un `1` que nadie verificó es el único error de esta feature que puede
   terminar en un plato servido a quien no debía.
2. **Todo `'*'` exige su entrada en `dietNotes`.** Un asterisco sin la acción
   que lo resuelve no le sirve a nadie en hora de servicio.
3. **`COURSE_ORDER` tiene una copia** en `COMANDA_SERVICE_ORDER`. Si agregás un
   curso, tocá las dos. `'Buffet'` está excluido del catálogo del Comande a
   propósito: es autoservicio, nunca entra en una comanda.
4. **El cruce se valida a máquina, no a ojo.** Ver §12.

### Receta 2: Agregar una familia de productos al E-Check

Por ejemplo, jugos del bar.

```js
// 1. Definir los datos (cerca de COCKTAILS o donde quieras):
const JUICES = [
  { id:'j1', name:'Jugo de naranja', group:'Frío' },
  { id:'j2', name:'Jugo verde',      group:'Frío' },
  { id:'j3', name:'Limonada de menta', group:'Frío' }
];

// 2. Registrar la fuente en COMANDA_SOURCES:
{ key:'juices', labelKey:'cmdSourceJuices', icon:'🥤',
  items: () => JUICES.map(j => ({
    sourceId: j.id, name: j.name, group: j.group, allergens: []
  })) }

// 3. Agregar la string en los 3 idiomas:
//    cmdSourceJuices: 'Jugos' / 'Juices' / 'Sucos'
```

Listo. Aparece un nuevo botón de categoría en el E-Check con los
jugos, mismo manejo de comensales, mismo agrupamiento por curso,
mismo drag-to-reorder.

### Receta 3: Agregar un módulo operativo nuevo en el header

Por ejemplo, un strip de "Eventos del día" arriba o abajo del staffing.

```js
// 1. STATE TOP — agregar:
const EVENTS_PATH = 'events';
let   EVENTS_DATA = null;

// 2. HTML — un nuevo container dentro de .ops-strip:
<div class="events-strip" id="events-strip"></div>

// 3. CSS — estilos del strip

// 4. JS — el módulo (en cualquier lugar abajo en el script):
async function eventsFetch() { /* REST GET */ }
function eventsRender()      { /* DOM write */ }
onI18nChange(eventsRender);

// 5. Boot — al final del script:
eventsFetch();
```

El módulo nuevo no toca ningún módulo existente. La regla i18n hook
y la regla STATE TOP garantizan que no se rompa nada.

---

## 8. Potencial latente (lo que el código ya soporta)

Sembré architecturalmente algunos features que NO están activos hoy
pero requieren poco trabajo para activarse:

**Integración con cocina/barra.** Cada item del E-Check carga un campo
`status` ('open' por ahora) que ya acepta 'sent' / 'served' /
'cancelled'. Y un campo `source` que dice si el item es de plato,
vino, coctel o custom — base para rooteo por estación de impresión.
Cuando llegue una impresora térmica al pase, los hooks ya están.

**Multi-mesero colaborativo.** El polling del E-Check sincroniza cada
8 segundos. Hoy es "uno mismo entre dispositivos"; con un campo
`waiter` agregado al schema y un PIN identitario, se vuelve "varios
meseros viendo las mismas mesas con sus propias responsabilidades".

**Cross-device del modo barista.** Hoy un solo barista por turno.
Estructura permite varios — el WebSocket listener de Firebase ya
distribuye eventos.

**Métricas operacionales.** El historial del café (`/orders_history`)
ya tiene `prepMs` por orden. El historial de mesas (`/comandas/{date}`
después de `closedAt`) tiene `openedAt`, `closedAt`, `timerStartedAt`,
duración por mesa. Tener un dashboard con: tiempo promedio de
preparación de café, mesas con duración anormal, postres más
solicitados, items más vendidos por servicio — todo eso es "leer los
buckets existentes y agregar".

**Voice notes / dictado en E-Check.** El campo `notes` del item es
string libre. Reemplazar el textarea por un botón de dictado del
navegador es una línea de Web Speech API.

**Modo offline.** La PWA (§2.1) ya sirve el shell desde cache cuando se
cae la red, pero solo para *leer*: un pedido que se tapea sin conexión se
pierde. Con una capa pequeña encima (queue de writes pendientes en
localStorage, drenada al volver online) se podría ingresar pedidos sin
red. El patrón de cola coalescente de §5 es la mitad del trabajo ya
hecha: falta que sobreviva a un reload.

---

## 9. Deuda intencional (qué NO está en producción real)

Hay decisiones conscientes de prototipo. Listarlas explícitas:

- **Reglas Firebase abiertas.** Cualquiera con la URL puede escribir.
  Bien para un prototipo de un solo hotel; mal para producción
  multi-tenant. Sustituir por auth (anónima o por email) cuando se
  abra al equipo completo.
- **No hay sistema de usuarios.** PINs son strings hardcoded
  (555/666/999). Sin trazabilidad de quién hizo qué. La data tiene
  espacio para `waiter` pero no se llena.
- **Sin backups automáticos.** El export de Firebase es manual desde
  consola.
- **Catálogos hardcoded en JS.** Platos, vinos y cocktails viven en
  el script. Update mensual → commit + push. No hay panel admin para
  no-desarrolladores. (Excepción: postres del servicio y staffing
  ya están en Firebase con upload via JSON paste / form.)
- **No hay tests.** El programa se valida con uso real y commits
  reversibles. Para un solo desarrollador iterando rápido, el costo
  de tests automatizados todavía supera el beneficio.
- **CI implícito vía Vercel.** No hay GitHub Actions de build/test (las que
  existen son de datos: `sync-viajeros.yml`, `seed-viajeros.yml`, `sync-rol`).
  Vercel despliega cada push automáticamente — `main` a producción,
  `staging` a una URL fija para QA por iPhone, `feature/*` a previews
  efímeras. La separación de branches (sección 12) cubre la mayor parte
  de lo que harían tests automatizados en otro proyecto: el owner valida
  visualmente antes de aprobar el merge a `main`.

---

## 10. Anatomía del archivo

`index.html` es **el único archivo de programa** de la app (~7400 líneas
tras los módulos Checklist y Viajeros): todo el CSS, el markup y el JS
viven ahí. Lo acompañan, en la raíz, los tres archivos de la PWA
(`manifest.webmanifest`, `sw.js`, `favicon.svg` — ver §2.1) y `assets/`
con los íconos; ninguno tiene lógica de la app.
Antes existía un duplicado `explora_atacama_app.V2.html`
como fuente de verdad mientras `index.html` quedaba como copia desplegada
— esa convención fue retirada el 2026-05-22 cuando la arquitectura de
branches (sección 12) reemplazó la necesidad de mantener dos versiones
locales en paralelo. Las "versiones paralelas" ahora viven en branches
de Git, no en archivos.

Mapa de regiones aproximadas (los rangos cambian a medida que crece;
úsalos como pista de búsqueda, no como verdad):

| Región | Aprox. líneas | Contenido |
|---|---|---|
| `<head>` | 1-15 | Title, fonts, Vercel analytics, Firebase SDK |
| CSS | 15-820 | Variables, layout, tipografía, animaciones, todos los módulos |
| HTML (body) | 820-985 | Header, tabs, containers de cada vista |
| `<script>` STATE TOP | 985-1170 | Todas las let/const accesibles desde boot |
| Diccionario `UI` | 1170-1610 | ES/EN/PT strings |
| Data estática | 1610-2400 | DISHES, WINES, COCKTAILS, MOCKTAILS, MOMENTOS, GUIONES |
| Cambio de menú 2026 | tras `DISHES` | `DIET_AXES`, `VJ_TAG_TO_AXIS`, `BUFFET_SLOTS`, `POSTRE_SLOTS`, `MENU_CYCLE_OFFSET`, `MENU_BUFFET`, `MENU_SOPAS`, `MENU_POSTRES`, `BAR_DISHES`, `DISHES_LEGACY_POSTRES` (los 12 postres anteriores, retirados pero reversibles con `DISHES.push(...)`) y el `DISHES.push` que unifica todo |
| Vista Menú | tras `setTab` | `renderDishes` + `menuRender*` (almuerzo/cena/bar/búsqueda), `dietVerdict`, `menuHasMatrix`, `menuExclStrip`, `menuVerdicts`, `menuTile`, la lente (`menuToggleAxis`, `menuApplyRoom`) y `menuJumpTwin` |
| Navegación | 2200-2400 | setTab, setLang, openWineFromGuion |
| Render principal | 2400-2700 | renderDishes, renderWines, renderCocktails, etc. |
| Módulo Café | 2700-3700 | COFFEE_DATA + manual + modo servicio (waiter+barista+history) |
| Módulo Staffing | 3700-3800 | Fetch + render del roster |
| Módulo Desserts / 86 | 3800-3900 | Strip + form de postres/86 — **latente** desde 2026-06-22 (markup en `<template id="latent-postres-86">`, activadores JS comentados) |
| Módulo Wine tips | — | `winetips`: rota `WINE_TIPS` (68, trilingüe, estático) cada 15s en orden barajado; reemplazó a Postres/86. **Ya no vive en la ops-strip**: desde 2026-08-16 se aloja en el listado de platos vía park/place (`winetipsSlot`/`Park`/`Place`, §5), con casa oculta en `#winetips-home` |
| Módulo Clima (`wx`) | tras `winetips` | Ráfagas de la ventana de almuerzo + altitud, en una línea sobre las tabs. `wxUrl`/`wxPeakGust`/`wxFetch`/`wxRender` + cache `localStorage`. Open-Meteo, sin Firebase — ver §3.2 |
| Módulo Comandera | 3900-4200 | Gate + home + new + active + drag + history |
| Módulo Viajeros | ~5260-5525 (+ CSS ~1377, STATE TOP ~2500, UI ~2682) | Corcho de dietas por hab: stats/chips filtrantes, búsqueda con teclado numérico plegable, grilla con roster (primer nombre + bandera `VJ_NAC` en vez de esferas de iniciales), modal por hab. Read-only `/viajeros/current` |
| Módulo Rol | 5500-6260 | PIN gate + lectura semanal del roster |
| Módulo Checklist | 6260-6940 | Sub-secciones + fases + carry-over + edit mode supervisor |
| Boot | dispersos | setLang(currentLang) + fetches iniciales |

Los módulos están agrupados, no entrelazados. Si vas a tocar el café,
todo lo del café está junto. Si vas a tocar la comandera, todo lo de
la comandera está junto.

---

## 11. Filosofía

Tres principios que guían las decisiones, escritos como reglas para
quienes contribuyan después:

**1 · La fricción de operación es enemiga.** Cada feature se mide por
cuántos taps cuesta usarla en plena hora pico. La velocidad importa
más que la elegancia del flujo. Un confirm() popup que cuesta un tap
extra es deuda — la app debe ser más rápida que una hoja de papel,
no más prolija.

**2 · El detalle, a mano.** El subtítulo del header es también la
norma de diseño: lo que importa está accesible, lo decorativo no se
nota. Ningún huésped debería ver la app — pero si la viera, leería
como un cuaderno cuidado, no como software corporativo.

**3 · Robustez por convención, no por framework.** Las reglas STATE
TOP, i18n hooks, optimistic UI y polling skip-on-interaction nacieron
de bugs reales. Cada una previene una clase de problema. Documentarlas
cuesta menos que el bug que viene después.

---

## 12. Workflow del repo

El programa se itera sobre un repo público en GitHub
(`fcodmonjes-cpu/Explora-GastroCycles`). La arquitectura de branches
separa **lo que está en uso**, **lo que está en revisión** y **lo que
está en exploración** — y cada una tiene su URL de Vercel distinta.

### Branches

| Branch | Rol | URL de Vercel |
|---|---|---|
| `main` | Producción. Lo que el staff del lodge usa en turno. | `gastrocycles.vercel.app` |
| `staging` | Cola de revisión. Lo que el owner mira desde iPhone antes de aprobar. | `gastrocycles-git-staging-<scope>.vercel.app` — **URL fija**, no cambia con cada commit |
| `feature/<nombre>` | Trabajo en curso de un feature nuevo. Iteraciones hasta que está listo para revisión. | Preview por commit, URL específica generada por Vercel |
| `fix/<nombre>` | Igual que feature, pero para correcciones puntuales. | Igual. |
| `master` | Legacy en sync con `main`. **No se usa** para trabajo nuevo. | — |

### Reglas

1. **Nunca commit ni push directo a `main`.** Solo recibe merges desde `staging`, y solo cuando el owner aprueba explícitamente. Un commit equivocado a main rompe la operación de un servicio en vivo.
2. **Trabajo nuevo siempre arranca en `feature/*` o `fix/*`.** Si voy a tocar cualquier cosa que no sea trivial, creo un branch.
3. **`staging` es el escenario de QA.** Cuando un feature está listo para que el owner lo vea desde iPhone, se mergea ahí — preferentemente fast-forward para mantener el historial lineal.
4. **El merge a `main` lo gatilla el owner.** Señales claras: "apruebo", "súbelo a producción", "mergea a main". Ambigüedad → preguntar.

### Flujo de una sesión de trabajo

**Al arrancar:**

1. `git status --short --branch` — confirmar dónde estoy. Si quedó algo a medias del día anterior, está acá.
2. Si estoy en `main` por error: salir antes de tocar nada. Crear/cambiar al branch correcto.
3. Releer las secciones de este archivo que toquen el área que voy a modificar.

**Trabajando:**

- Editar `index.html` directamente (no hay archivo paralelo desde 2026-05-22).
- Probar localmente con `py -m http.server 3000` y `http://localhost:3000/index.html`.
- Para módulos que tocan Firebase, considerar monkey-patch del `fetch` durante el desarrollo para no contaminar la base de producción con datos de prueba.

**Toolkit de validación local** (sin instalar dependencias — todo ya disponible en el entorno; sirve igual con cualquier modelo):

1. **Paridad de backticks:** `py -c "print(open('index.html',encoding='utf-8').read().count(chr(96))%2)"` → debe dar `0`. Un impar = template-literal sin cerrar = script halteado por TDZ (§5).
2. **Bytes NUL:** contar `b'\x00'` sobre el archivo en binario → debe dar `0` (la herramienta de edición a veces mete un NUL literal; ensucia el repo y rompe ripgrep).
3. **Syntax-check real con Node** (`node v24` está instalado): extraer los `<script>` inline (regex `/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi`) y `node --check` sobre el resultado. Atrapa errores de sintaxis sin ejecutar el DOM.
4. **Screenshot de render real con Chrome/Edge headless** (ambos instalados en `Program Files`): como los módulos viven detrás de una tab + Firebase, armar un *harness* que reuse el `<style>` real del `index.html` + markup estático que replique lo que emiten las funciones de render, y capturarlo: `chrome.exe --headless=new --disable-gpu --window-size=390,H --screenshot=out.png harness.html`. Atrapa errores de CSS/layout/overflow que el syntax-check no ve. **Caveat:** los emoji de bandera (indicadores regionales) **no renderizan en Windows** (salen como letras `BR`/`CL`); ese detalle solo se valida en iPhone.
5. **Scripts Python (`sync_*.py`):** correr con `PYTHONUTF8=1` en consola Windows — sin eso, los `print` con `≤`/`·`/`ñ` tiran `UnicodeEncodeError` (cp1252). En CI ubuntu corren sin el flag. Validar el pipeline con `--debug` (no escribe Firebase). Además, un **chequeo estático con `ast`** (funciones llamadas pero no definidas + constantes en mayúscula sin asignar) antes de gastar una corrida de CI: al editar bloques grandes es fácil borrar una función vecina y el `NameError` recién aparece a los 3 minutos, en el runner.
6. **Cruce de datos contra la fuente, a máquina.** Cuando entra contenido desde
   un documento del asesor (la matriz de restricciones son 9 ejes × 40 platos =
   360 celdas), no se revisa a ojo: un script lee la tabla del `.docx` con
   `zipfile` + regex sobre `word/document.xml`, extrae los arrays del
   `index.html` corriéndolos con `node -e`, cruza por nombre normalizado y
   reporta discrepancias. Debe dar **0**. El mismo script verifica que todo
   `'*'` tenga su `dietNotes`. Vive en el scratchpad de la sesión, no en el repo.
7. **Delta de Y bajo el dedo.** Para cualquier control que despliegue contenido
   variable, medir en el navegador que los elementos vecinos NO se mueven:
   `getBoundingClientRect().top + scrollY` antes y después de cada toggle. En la
   lente de restricciones (hoy latente, §3.1) se verificó en su momento que
   prender/apagar ejes dejaba los chips, la fila de acciones y la grilla
   exactamente donde estaban, y que el riel del selector de día mide 33 px
   tanto en almuerzo como en bar.
   **El caso más traicionero no es un toggle sino un dato que llega por red**,
   porque nadie lo está mirando cuando ocurre: el clima (§3.2) pinta después del
   primer paint y, sin alto reservado, empujaba `.main-tabs` 23 px hacia abajo —
   justo cuando el garzón va a tocarlas. Para esos módulos hay que recorrer
   *todos* los estados, no sólo el feliz: cargando · sin red · cada umbral · y
   el peor caso de largo del texto. El Y del vecino debe ser idéntico en todos.
8. **Screenshots headless con viewport real.** `chrome --headless=new` ignora
   `--window-size` para el layout y renderiza más ancho de lo pedido, lo que
   simula desbordes que no existen. La vuelta: un wrapper con un `<iframe>` de
   ancho fijo (375 px) apuntando a la página, y screenshot del wrapper.
9. La **prueba real** sigue siendo cargar la página (server local o preview de Vercel) y, para lo que solo se ve en iOS, el QA del owner desde iPhone en la URL fija de staging.

**Al cerrar:**

| Estado | Acción |
|---|---|
| Listo para revisión | Commit en `feature/*` → push → merge a `staging` (fast-forward) → push staging. Reportar URL fija de staging al owner. |
| Incompleto pero quiero guardar | Commit en `feature/*` → push. Queda como WIP visible en el preview de Vercel, no toca staging. |
| Experimental o destructivo | Puede quedar uncommitted en working tree, o en un commit local sin push. |

### Hand-off entre sesiones

El estado del trabajo vive en **branches + commits**. Las decisiones de
diseño viven en **este archivo**. Las memorias persistentes del
asistente (`~/.claude/projects/.../memory/`) cubren preferencias del
owner y convenciones operacionales que no encajan en docs del repo.

Cuando el owner pida "retomemos lo de X":

1. `git log feature/X --oneline` — entender el camino recorrido.
2. `git diff main feature/X -- index.html` — ver el delta acumulado.
3. Abrir la URL del preview de Vercel para validar visualmente sin levantar local.

### Convenciones de código y contenido

- **Idioma de trabajo con el owner:** español.
- **Trilingüe (ES/EN/PT):** cualquier string visible al usuario debe existir en los 3 idiomas del diccionario `UI`. Si falta un idioma para un módulo nuevo, consultar al owner antes de traducir automáticamente.
- **Comentarios:** en español, salvo cuando se refieran a APIs/términos técnicos universales.
- **Paleta y tipografías:** Cormorant Garamond + Courier Prime, dark amber. No introducir colores nuevos sin avisar.
- **Convención de PINs:** 555 (mesero), 999 (barista), 9876 (supervisor Checklist). Gates desactivados el 2026-06-09 para reducir fricción: **Rol** (tenía 2098 — ahora entra directo; quedó "oculto" al final del strip scrollable y esa obscuridad reemplaza la clave) y **E-Check/comandera** (tenía 666 waiter / 777 recibidor — ahora entra directo como waiter; reimaginada como herramienta personal + intercom entre meseros). El código de ambos gates queda latente para reactivar en una línea (`ROL_PIN_CODE`/`rolRenderGate`/… y `COMANDA_PIN_CODE`/`COMANDA_RECIBIDOR_PIN`/`comandaRenderGate`/…). El módulo **Viajeros** (2026-07-17) nació sin gate por la misma lógica. Nuevos PINs deben ir aquí cuando se agreguen.

### Lo que NO se hace

- No commitear a `main` sin aprobación.
- No introducir dependencias (npm, build tools, frameworks) sin discutirlo.
- No cambiar paleta o tipografías sin aviso.
- No traducir automáticamente — preguntar si falta un idioma.
- No borrar contenido del ATA Handbook sin confirmar.
- No commitear secretos (tokens, credenciales) ni dejarlos en plain text en `.git/config`. Si se necesita autenticar, usar Windows Credential Manager.

### Excepciones válidas

Hotfix urgente (algo roto en plena hora de servicio): el flujo ideal
sigue siendo `fix/<nombre>` → staging → main, pero el owner puede
acelerar y pedir push directo a `main` si la urgencia lo amerita.
**Es la única excepción válida**, y siempre por solicitud explícita
del owner.

---

*Documento mantenido junto al código. Actualizar al agregar un
módulo nuevo o cambiar un patrón estructural.*
