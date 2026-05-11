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
- Panel operativo (roster del turno + postres del servicio del día)

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
| Hosting | GitHub Pages (`master:main`) | Free, automático, ramas master ↔ main sincronizadas. |
| Tipografía | Cormorant Garamond (italic 500/700) + Courier Prime monospace | Cargadas vía Google Fonts. Family declarada en CSS desde el inicio; sólo recientemente se cargó la real. |
| Telemetría | Vercel Analytics (`/_vercel/insights/script.js`) | Pageviews ligeros, sin más. |

**Por qué no hay framework.** El programa es lo bastante chico para que
el costo cognitivo de un framework supere su beneficio. Lo bastante
grande para que algunas convenciones internas hagan la diferencia.
La complejidad la maneja la disciplina de patrones, no la dependencia.

---

## 3. Las cinco pantallas (topología)

Header común arriba (título + subtítulo + selector de idioma + logo).
Debajo, un wrapper "ops-strip" con el panel de staffing (turno activo,
viajeros) y el strip de postres del día. Después, la fila de tabs:

```
┌─────────────────────────────────────────────────────────────┐
│ The ATA Handbook                              [ES][EN][PT]  │
│ El detalle, a mano.                                          │
├─────────────────────────────────────────────────────────────┤
│  AM            72 VIAJEROS                                   │
│  Senior  Percy                                               │
│  Comedor Nicolás · Sebastián · Diego · Viviana              │
│  Apoyo   Victor                                              │
│                                                              │
│  H · durazno   S · frutilla   F · tuna, melón   N · choco   │
├─────────────────────────────────────────────────────────────┤
│ [Menú] [Vinos] [Cocktails] [Café] [E-Check]                 │
└─────────────────────────────────────────────────────────────┘
                    (contenido de la tab activa)
```

| Tab | Propósito | Datos | PIN |
|---|---|---|---|
| **Menú** | Plato del día (D1-D4) + alérgenos + maridajes | Estático en el JS (`DISHES`) | — |
| **Vinos** | Ficha por vino + sub-vista "Maridajes generales" | Estático (`WINES`, `GUIONES`) | — |
| **Cocktails** | Mocktails (halo verde) + Cocktails + sub-banner Momentos | Estático (`COCKTAILS`, `MOCKTAILS`) | — |
| **Café** | Manual de bebidas + modo servicio (mesero / barista) | Estático (`COFFEE_DATA`) + Firebase `/orders` | 555 (mesero) · 999 (barista) |
| **E-Check** | Comandera por mesa | Firebase `/comandas/{date}/{id}` | 666 |

Los datos del Café (módulo Service Mode) y los del E-Check tienen su
propia capa de Firebase. Los módulos del header (staffing, desserts)
también escriben/leen Firebase.

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
├── desserts/                      ← postres rotativos por servicio
│   └── {YYYY-MM-DD} → { helado, sorbet, fruta[], ninos, enteredAt }
│       (auto-purge >4h)
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

**PWA (instalable como app).** Un `manifest.json` + meta tags Apple +
service worker mínimo lo convierten en una app instalable en el home
screen. Sin barra de URL, sin pestañas, mejor experiencia para el
mesero.

**Modo offline.** Firebase compat SDK ya cachea. Con una capa pequeña
encima (queue de writes pendientes en localStorage) se podría ingresar
pedidos sin red y sincronizar al recuperar conexión.

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
- **Sin pipeline de CI.** GitHub Pages despliega automáticamente
  desde `main`. Cualquier push se ve en producción ~30s después.
  Decisión: máxima velocidad de iteración.

---

## 10. Anatomía del archivo

`explora_atacama_app.V2.html` (también copiado como `index.html`) tiene
~3900 líneas. Mapa de regiones aproximadas:

| Región | Aprox. líneas | Contenido |
|---|---|---|
| `<head>` | 1-15 | Title, fonts, Vercel analytics, Firebase SDK |
| CSS | 15-700 | Variables, layout, tipografía, animaciones, todos los módulos |
| HTML (body) | 700-1000 | Header, tabs, containers de cada vista |
| `<script>` STATE TOP | 1000-1100 | Todas las let/const accesibles desde boot |
| Diccionario `UI` | 1100-1300 | ES/EN/PT strings |
| Data estática | 1300-1900 | DISHES, WINES, COCKTAILS, MOCKTAILS, MOMENTOS, GUIONES |
| Navegación | 1900-2200 | setTab, setLang, openWineFromGuion |
| Render principal | 2200-2400 | renderDishes, renderWines, renderCocktails, etc. |
| Módulo Café | 2400-3400 | COFFEE_DATA + manual + modo servicio (waiter+barista+history) |
| Módulo Staffing | 3400-3500 | Fetch + render del roster |
| Módulo Desserts | 3500-3600 | Strip + form de postres |
| Módulo Comandera | 3600-3900 | Gate + home + new + active + drag + history |
| Boot | 3900+ | setLang(currentLang) + fetches iniciales |

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

*Documento mantenido junto al código. Actualizar al agregar un
módulo nuevo o cambiar un patrón estructural.*
