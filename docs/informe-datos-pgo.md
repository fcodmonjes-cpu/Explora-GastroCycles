# Informe · Qué datos de PGO entran al Handbook y dónde se ven

> Fecha: 2026-09-16 · Rama `claude/jolly-einstein-66r33y`
> Alcance: `scripts/sync_viajeros.py` (pipeline PGO → Firebase) + `index.html`
> (superficies que dibujan ese dato). Complementa `ARCHITECTURE.md` §4, §4.1 y §4.2.

## 0. Cómo se hizo, y qué NO pude verificar

El inventario sale de leer **el código completo de punta a punta**: la query
GraphQL que se le manda a PGO, el mapeo de columnas de cada reporte HTML, el
doc exacto que arma `build_doc()`, y cada función de render de la app que toca
`VIAJEROS_DATA`. Eso lo hace exacto para las dos preguntas del encargo: *qué se
pide* y *qué se dibuja*.

**Lo que no pude hacer en esta sesión, y conviene saberlo antes de leer:**

- **No corrí el sync contra PGO en vivo.** Los secrets (`PGO_USER`, `PGO_PASS`,
  `PGO_BASE_URL`) viven en GitHub Actions, no acá. Así que no hay tasas de
  llenado reales del día ("de 70 viajeros, cuántos traen hora de vuelo",
  "cuántas obs quedaron en `revisar`").
- **No pude leer `/viajeros/current` de producción**: el entorno bloqueó la
  lectura de datos productivos. Tampoco corrí el seed local — el sandbox
  bloquea ejecutar ese script.
- **Cómo cerrar esa brecha en 5 minutos, sin tocar nada:** Actions →
  *Sync Viajeros (PGO)* → Run workflow con `dry_run: true`. Lee PGO, imprime
  `print_summary` + `print_comedor` y **no escribe Firebase**. Para los campos
  que hoy no se piden: mismo workflow con `explore: all` + `introspect: true`.

---

## 1. El pipeline en una imagen

Cada corrida (cada 2 h, 9 al día, `0 9-23/2` + `0 1` UTC) toca **cinco** fuentes
de PGO y escribe **un solo doc** que se sobrescribe entero:

```
PGO
├─ GraphQL travellersInhouse(hotelId:2, date)   → ROSTER   (la columna vertebral)
├─ GraphQL reportInOut(hotelId:2, date)         → HORAS reales + vuelos + contadores
├─ HTML /dietas                                 → OBSERVACIONES (texto libre)
├─ HTML /comedor                                → CUBIERTOS por grupo + tabla Hoy/Mañana
├─ HTML /birthday-report                        → CUMPLEAÑOS del mes
│
├─ HTML /report-geos       ← SOLO si la API de roster falla (respaldo automático)
└─ HTML /arrival-report    ← NO se lee en el sync; sólo con --explore
                                     │
                                     ▼
                        Firebase  /viajeros/current   (un doc, pisado cada vez)
                                     │
        ┌────────────────────────────┼────────────────────────────┐
        ▼                            ▼                            ▼
   Banner home                  Tab PGO                     Tab Comande
   (3 contadores +          (vista Viajeros +            (panel de habs +
    línea de cumpleaños)      vista Comedor)              comanda completa)
                                     │
                                     └─ Tab Menú "desde una hab" → LATENTE (comentado)
```

Aparte, y en otro path: **`/viajeros_notas/{pid}`** — el dato flexible que
escribe el equipo desde la app. No lo pisa el sync; se purga 2 días después del
check-out. Es, hoy, el único canal para todo lo que PGO no entrega.

---

## 2. Lo que SÍ estamos mostrando

### 2.1 Campos por viajero

Doc: `viajeros/current.habs["01"][i]`. Origen y superficie de cada campo:

| Campo | Origen en PGO | Dónde se ve | Nota |
|---|---|---|---|
| `nombre` | API `traveller.firstName + lastName` | Grilla de habs (**sólo nombre de pila**), tarjeta de persona y ficha (completo), panel del Comande. Es campo de búsqueda. | Por API llega sin mojibake; por HTML había que repararlo |
| `edad` | API `traveller.age` | Ficha (`48 años`), tarjeta de persona (número suelto). Deriva **"menor"** (≤17) → badge, flag por hab y contador del banner | El log del script usa ≤12 para "niños"; la app usa ≤17. Dos umbrales distintos conviviendo |
| `nac` | API `traveller.nationality` (código de 4 letras) | **Bandera emoji** en grilla, tarjeta de persona y ficha; texto crudo en la ficha | `VJ_NAC` mapea 18 códigos. Uno nuevo cae a texto crudo — ver §4.8 |
| `grupo` | API `traveller.group` | Encabezado de la tarjeta de hab y de la ficha; **color del avatar** de iniciales; campo de búsqueda | |
| `in` / `out` | API `reserva.checkin/checkout` (fecha) | Ficha: `IN 26-07 → OUT 01-08`; chips *sale hoy / sale mañana / llega hoy*; **oculta a los salientes** de las vistas por hab | |
| `tags[]` | **Derivado** de `obs` por `obs_to_tags()` | Chips en ficha y tarjeta de persona · chips-filtro con contadores · flags `● N` por hab · contadores del banner · panel del Comande | 37 tags canónicos en `VJ_TAGS` |
| `obs` | HTML `/dietas` col. Observaciones (+ comedor, + comentario Geos si mapea) | Texto crudo bajo los chips — **sólo en la ficha completa** | No aparece en la grilla ni en la tarjeta de persona |
| `revisar` | Derivado: la obs dice algo y ningún tag la cubrió | Chip ámbar *"revisar observación"* | La red de seguridad del sistema. **Sin filtro accesible** — §4.5 |
| `cumple` | HTML `/birthday-report` (`DD-MM`) | Línea de cumpleaños del banner + chip en la tarjeta de persona | **No aparece en la ficha ni en la grilla** — §4.3 |
| `pid` | Derivado del nombre (slug estable) | Invisible: es el ancla de las **notas del equipo** | |
| `inAt` / `outAt` | API `reportInOut.checkin/checkout` (**hora real**) | **Nunca se muestran.** Sólo alimentan el cálculo de presencia por servicio | El dato más valioso hoy desaprovechado — §4.1 |
| `foto` | — (hook, PGO no lo entrega) | Si existiera, reemplaza el avatar de iniciales | |

### 2.2 Campos del doc (nivel raíz)

| Campo | Dónde se ve |
|---|---|
| `date` | Chip de la cabecera de la tab: fecha del reporte + aviso si es de otro día |
| `updatedAt` | Mismo chip: punto de frescura (verde <2,5 h · ámbar <5 h · rojo) + "hace N min" |
| `comedor.grupos[]` | Vista **Comedor**: grupo, cubiertos del servicio, habs, y `mov` (`IN 09:45`) |
| `comedor.totales` (HOY) | Chip *"N comen"* en las celdas de servicio, **sólo si difiere en más de 2** del conteo por presencia. Usa `desayunos`, `almuerzos`, `cena` |

### 2.3 Las cuatro superficies, y qué responde cada una

| Superficie | Qué pregunta responde | Dato que usa |
|---|---|---|
| **Banner de la home** | "¿Cuántos son ahora y cuántos condicionan la cocina?" | presencia por servicio, menores, restricciones, cumpleaños de hoy |
| **Tab PGO · vista Viajeros** | "¿Quién está en la 14 y qué no puede comer?" | todo lo de §2.1 |
| **Tab PGO · vista Comedor** | "¿Entran todos? ¿Hay que remontar?" | `comedor.grupos` + capacidad 80 + rotación 60′ |
| **Tab Comande · panel de habs** | "Estoy tomando esta mesa: ¿qué restricciones tiene?" | la **misma ficha** (`vjTravelerRow`) que el modal de hab |

> La ficha de viajero es **una sola función** usada en tres lugares (modal de
> hab, panel del Comande, comanda completa). Rediseñarla los arregla a los tres
> de una — y también los rompe a los tres de una.

---

## 3. Lo que el script escanea y NO se ve

Tres niveles distintos, de más barato a más caro de recuperar.

### Nivel A · Ya está en Firebase, sólo falta dibujarlo (costo: UI)

| Campo | Qué es | Por qué importa |
|---|---|---|
| `inAt` / `outAt` | **Hora real** de check-in/out (`2026-09-16T15:40`). Verificada contra el vuelo: el HTML redondea a `:15`/`:45`, la API no | Hoy sólo se usan para contar. "Sale hoy" esconde a alguien que almuerza a las 13:00 y se va 16:30 |
| `inFlight` / `inFlightAt` | Vuelo de llegada: `LA 144` + hora en Calama | Explica el desayuno temprano y el "llega tarde y con hambre" |
| `outFlight` / `outFlightAt` | Vuelo de salida | Un vuelo 11:11 = desayuno temprano obligado |
| `inSrc` / `outSrc` | De qué campo salió la hora (`checkin`/`checkout`) | Diagnóstico, no pantalla |
| `comedor.totales.full` | Cubiertos "Full" (comen fuera del salón) | **Responde "¿dónde están los otros 20?"** — hoy sólo vive en el log |
| `comedor.totales.terreno` | Almuerzos en terreno (box lunch) | Idem |
| `comedor.totalesManana` | La misma tabla para mañana | Permite anticipar el montaje del día siguiente |
| `comedor.diaGrupos` | `"hoy"` o `"?"` — si el detalle por grupo cuadró con la columna Hoy | **La vista Comedor no lo lee**: cuando el detalle es de otro día, se dibuja igual y sin aviso |
| `pgoCounts` | `cantTravellerIn`, `cantTravellerOut`, `cantTravellerTodayNight` de PGO | Segunda opinión contra nuestro conteo por presencia |
| `source` | `"pgo"` o `"seed"` | Si un día el seed pisa producción (ya pasó el 31-07), la app no lo dice |
| `id` | `h{hab}-{i}` | Vestigial: el ancla real es `pid`. No lo usa nadie |

### Nivel B · Se le pide a PGO y se tira antes de llegar al doc (costo: 1-5 líneas de script)

| Campo | Se pide en | Se descarta en |
|---|---|---|
| `traveller.nationalityName` | `PGO_ROSTER_QUERY` | `pgo_fetch_roster()` sólo lee `nationality`. **Es el fallback gratis para los códigos sin bandera** |
| `guestCount` | `_INOUT_FIELDS` | `pgo_fetch_inout()` no lo lee |
| `confirmationNumber` | `_INOUT_FIELDS` | idem. Sería la llave para cruzar con cualquier otro reporte |
| `arrivalStatus` / `departureStatus` | `_INOUT_FIELDS` | idem. "¿Ya llegó de verdad, o está en la ruta?" |
| Dietas: `hab`, `edad`, `nac`, `grupo` | `PGO_DIET_COLS` | `parse_roster_con_dietas()` sólo toma `nombre` → `obs`. Correcto (manda el roster), pero servirían para **auditar el cruce** |
| Cumpleaños: `hab`, `n° confirmación` | `PGO_CUMPLE_COLS` | `parse_birthday()` sólo devuelve `{nombre: 'DD-MM'}` |
| Comedor por grupo: columnas no mapeadas | tabla completa leída | `PGO_COMEDOR_COLS` no mapea `full` ni `terreno` a nivel grupo (sí en el pie) |
| **Toda columna no mapeada de cualquier tabla HTML** | `_pgo_extraer_tabla()` lee la grilla **entera** | `_remap()` se queda sólo con las columnas del diccionario. Todo lo demás se descarta en memoria |

### Nivel C · Está en la fuente y no se pide (costo: una query o un mapeo nuevo)

| Dato | Dónde está | Estado real hoy |
|---|---|---|
| **Exploración del día** | Columna `excursión` del **Reporte Geos** (HTML) | Se lee la columna y `PGO_GEOS_COLS` la descarta. Y desde el 17-08 **Geos ni se abre**: el roster sale de la API y el HTML quedó de respaldo. O sea: **hoy no se escanea** |
| **Exploración con hora AM/PM** | No confirmada en ninguna fuente que el script toque | El único rastro operativo es `dt` (desayuno temprano = excursión o vuelo antes de que abra el comedor) |
| **Últimas exploraciones** (histórico) | No existe extracción por rango de fechas | Requeriría una query nueva por viajero/reserva |
| **Tipo de cama** | Presumiblemente en `ReservationType` (135 campos) o en `/arrival-report` | **No se pide ni se lee.** No hay rastro en el repo. Se confirma con un `--explore --introspect` |
| `dietReq`, `foodRestrictions`, `dietReqObs` | API `TravellerType` | Medido el 17-08: 4 y 5 casos contra **9** del HTML. Migrar perdería restricciones; **sumar** en unión sí conviene (§4.2) |
| `hasFoodReq` | API | **Trampa**: viene `True` en 60 de 70. Significa "llenó el formulario", no "tiene restricción" |
| Preferencia de agua, vinos, special requests | API (declarado en §4.1) | Diferido a pedido del owner. Hoy lo cubre a mano el módulo de **notas** |
| `/arrival-report` completo | HTML | Sólo se perfila con `--explore`; nunca entra al doc |

---

## 4. Hallazgos — cosas que hoy no cierran

Ordenados por lo que cuesta arreglarlos contra lo que devuelven.

### 4.1 La grilla esconde por FECHA a alguien que el contador cuenta por HORA

`vjVisibles()` oculta a todo el que tenga `out === hoy`, sin mirar la hora.
`pgoBannerCounts()` y las celdas de servicio, en cambio, usan `outAt` real. Un
huésped con checkout 16:30 **está contado en el almuerzo y escondido en la
grilla al mismo tiempo**. El toggle "ver salientes" lo recupera, pero hay que
saber que está. Arreglo: ocultar por `vjPresenteAhora()`/ventana del servicio en
vez de por fecha.

### 4.2 La vista Comedor puede estar mostrando MAÑANA sin decirlo

El script ya sabe la respuesta y la escribe (`comedor.diaGrupos`: `"hoy"` o
`"?"`). La app no la lee. Cuando el detalle por grupo no cuadra con la columna
Hoy de PGO, la vista dibuja los cubiertos igual, con el mismo aspecto de siempre.
Un rótulo de una línea cierra el agujero.

### 4.3 El cumpleaños no está donde se lo busca

`vjCumpleChip()` se dibuja **sólo** en la tarjeta de persona filtrada. Si abrís
la habitación 14 —el camino natural— no aparece. Tampoco en la grilla. El banner
lo anuncia y después el dato se esconde justo en la pantalla desde la que se
actúa.

### 4.4 `full` y `terreno` sólo existen en el log

`print_comedor()` ya imprime `almuerzo salón=54 full=9 terreno=11`, y hasta lista
quién se queda sin cubierto por grupo. Nada de eso llega a pantalla. Es
exactamente la pregunta que las dos cifras distintas del header provocan.

### 4.5 Tres filtros existen y no tienen botón

`vjMatchesFilter()` soporta `alergias`, `revisar` y `salenhoy`. Ningún control
de la UI los dispara: la fila de stats se volvió las tres celdas de servicio, y
el banner sólo manda `ninos`, `dietas` y `cumplehoy`. **"Revisar" es el más
grave**: es la red de seguridad para la obs que el script no supo mapear, y no
hay forma de listar a esa gente.

### 4.6 Dos umbrales de "niño" conviviendo

El script informa "niños (≤12)" en el log; la app marca "menor" con ≤17
(`VIAJEROS_NINO_MAX`). Los dos números son defendibles, pero son distintos y
nadie lo dice. Si el contador del banner se contrasta contra el log, no cuadran.

### 4.7 La hora real se calcula y no se lee

Es el caso más caro de todos: `reportInOut` existe, se resolvió el cruce por
habitación (con el bug de la hab reocupada ya corregido), se guarda la hora al
minuto… y en pantalla sigue diciendo `OUT 01-08`. Todo el valor está en el doc
esperando tres líneas de render.

### 4.8 Una nacionalidad nueva pierde la bandera, teniendo el nombre a mano

`VJ_NAC` tiene 18 códigos cableados. Un `POLA` o un `JAPA` cae a texto crudo. La
query **ya pide `nationalityName`** y el script lo tira. Guardarlo cuesta una
línea y da el nombre legible del país como respaldo.

---

## 5. Oportunidades, por retorno sobre esfuerzo

### Tier 1 · Sólo UI — el dato ya está en Firebase

1. **Horas reales en la ficha** (`inAt`/`outAt`): `sale hoy 16:30` en vez de
   `OUT 01-08`. Cambia la decisión del salón, no la decora.
2. **Rótulo de día en la vista Comedor** (`diaGrupos`). Una línea, cierra un
   riesgo real de leer el día equivocado.
3. **`full` + `terreno` en las celdas de servicio**: "62 en casa · 54 almuerzan
   acá · 20 fuera". Responde la pregunta antes de que se haga.
4. **Cumpleaños en la ficha y en la tarjeta de hab**.
5. **Devolver los filtros huérfanos**, en particular `revisar`.
6. **Ocultar salientes por hora, no por fecha** (§4.1).
7. **Vuelos** (`inFlight`/`outFlight`) en la ficha, discretos: `LA 402 · 11:11`.

### Tier 2 · Una línea de script + UI

8. **`nationalityName` como respaldo de bandera** (ya se pide, se descarta).
9. **`dietReq` / `foodRestrictions` en UNIÓN** con el texto libre — nunca en
   reemplazo (§4.2). Sube la cobertura sin perder los 9 casos del HTML.
10. **`arrivalStatus` / `departureStatus`**: distinguir "llegó" de "viene en
    camino". Hoy alguien que aterrizó a las 07:07 figura igual que el que ya
    hizo check-in.

### Tier 3 · Pedirle algo nuevo a PGO

11. **Exploración del día (con AM/PM)** — lo que más le falta al salón y lo que
    explica la mitad de los huecos de cubiertos. La vía conocida es la columna
    `excursión` del Reporte Geos, hoy ni fetcheada. **Antes de escribir código:
    un `--explore --introspect` para ver si la API la entrega estructurada**, que
    sería mucho más estable que volver al HTML.
12. **Tipo de cama / tipo de habitación**: mismo `--explore`. Valor F&B moderado
    (composición de la hab: matrimonio vs twin vs familia); valor alto para
    housekeeping, que no es este handbook.
13. **Últimas exploraciones (histórico)**: caro y de valor incierto para el
    salón. Recomiendo diferirlo hasta que 11 esté andando.

**Costo que no se ve:** cada campo nuevo del GraphQL es gratis en tiempo (viaja
en la misma llamada), pero **un campo inválido tumba la respuesta entera** y se
ve idéntico a "hoy no hay datos" (§4.2). Todo campo nuevo se valida primero con
`--explore`, nunca directo en el sync productivo.

---

## 6. La tarjeta del viajero — diagnóstico y propuesta

### Cómo es hoy (`vjTravelerRow`, tres pantallas a la vez)

```
┌────────────────────────────────────────────────┐
│ (MN)  María Nusynkier                          │
│       10 años · 🇦🇷 ARGE · IN 26-07 → OUT 01-08 │
│       [sin lactosa] [alergia maní]             │
│       ALERGIA AL MANI. Alergias: MANI          │  ← obs cruda
│       + agregar nota                           │
└────────────────────────────────────────────────┘
```

**Lo que funciona y no hay que tocar:** la precedencia de los chips (revisar en
ámbar → sin restricciones en verde → los tags), que garantiza que ninguna rama
termine en silencio. Es lo mejor del módulo.

**Lo que no:**

- **La línea meta mezcla tres registros** — demografía (edad, nacionalidad) y
  logística de estadía (fechas) — en un renglón mono de igual peso. Se lee
  entera o no se lee.
- **Las fechas `IN 26-07 → OUT 01-08` son lenguaje de recepción.** Al salón le
  importa "¿está ahora?", "¿a qué hora se va?", "¿cuántos servicios le quedan?".
  Y la hora real ya está en el doc (§4.7).
- **La obs cruda repite a los chips** en la mayoría de los casos. Aporta cuando
  hay matiz ("vegetariana pero come pescado") o cuando `revisar` está prendido;
  el resto del tiempo es ruido que empuja las notas fuera de pantalla.
- **Falta lo que no se ve en ningún lado**: cumpleaños, hora, vuelo, si tiene
  cubierto asignado hoy.

### Propuesta: tres renglones en orden de urgencia

```
┌────────────────────────────────────────────────┐
│ 🇦🇷  María Nusynkier  ·10·  menor   🎂 hoy      │  identidad
│     ▸ sin lactosa   ▸ alergia maní             │  LO ACCIONABLE, primero
│     en casa · sale hoy 16:30 · LA 402          │  estadía, en lenguaje de salón
│     ⌄ texto original                           │  la obs, a un tap
│     ✎ nota del equipo                          │
└────────────────────────────────────────────────┘
```

Las tres decisiones detrás:

1. **La restricción sube al segundo renglón.** Es lo único que cambia lo que se
   sirve; hoy va tercera, después de la edad y de dos fechas.
2. **La estadía se dice en estado, no en fechas**: `en casa` / `llega 15:40` /
   `sale hoy 16:30`. Las fechas completas quedan a un tap, no en primer plano.
   Esto es lo que desbloquea `inAt`/`outAt` y los vuelos.
3. **La obs cruda se colapsa**, salvo cuando `revisar` está prendido — ahí se
   muestra abierta, porque es justamente el caso en que los chips no alcanzan.

### Lo que hay que decidir antes de tocar código

Son decisiones del owner (CLAUDE.md, regla 4), no mías:

- **¿La bandera reemplaza al avatar de iniciales, o conviven?** Hoy la tarjeta de
  persona ya usa bandera y la ficha usa avatar: son dos lenguajes distintos para
  la misma persona en dos pantallas. *(Caveat de `ARCHITECTURE.md` §12: las
  banderas emoji no renderizan en Windows — esto sólo se valida en iPhone.)*
- **¿El cumpleaños entra a la ficha con el mismo peso que en el banner?**
- **¿La obs cruda colapsada por defecto, o abierta como hoy?** Es la que más
  cambia la densidad de la pantalla en el Comande.
- **¿Mostramos el vuelo?** Suma una línea de información que no todos los turnos
  necesitan.

Con esas cuatro respuestas, el Tier 1 completo son cambios acotados a
`vjTravelerRow`, `vjRenderHabs`, `vjRenderStats` y `vjRenderComedor` — sin tocar
el script ni el shape del doc, o sea sin riesgo sobre la base de producción.

---

## 7. Exploraciones: lo que devolvió el sondeo (2026-09-15)

> Dos corridas de `--explore exploraciones` contra PGO real (runs 372 y 373).
> La primera falló en perfilar la columna del Geos porque la buscó por regex y
> se llama **`exp`**, no "excursión" — la lección está en el commit. La segunda
> trajo todo. **Ninguna escribió Firebase.**

### 7.1 El titular: ya estaban en el Reporte Geos, en dos columnas que tirábamos

El Geos no tiene 8 columnas sino **10**, y las dos que faltaban en toda la
documentación del repo son exactamente las que se pedían:

| Columna | Llenas | Formato (enmascarado) | Qué es |
|---|---|---|---|
| `exp` | **77/100** · 65 con AM/PM | `AM <nombre de exploración>` | **La exploración del día, con turno** |
| `historia` | **75/100** · 75 con AM/PM y fecha | `<nombre>-2 (PM 12-09)` | **Lo que ya hizo, con turno y fecha** |
| `tipo viajero` | 100/100 | una letra | sin identificar (¿adulto/niño?) |

`historia` **es el histórico de exploraciones**, ya resuelto por PGO, por
persona, en la misma fila del reporte que ya leemos. No hay que acumularlo
nosotros ni cruzar nada: viene servido.

Las dos se descartan hoy en `_remap()` porque `PGO_GEOS_COLS` no las mapea. Y
desde el 2026-08-17 el Geos **ni se abre** en el camino feliz, porque el roster
salió de la API — así que recuperarlas implica volver a pedir ese reporte.

### 7.2 La vía API: más rica, y con datos de F&B que no esperábamos

`hotelExplorationsDay(hotelId, date)` devolvió **28 filas** para el 15-09
(`hotelAllExplorationsDay`, 30). Tipo `ExplorationRegisterType`. Lo relevante:

| Campo | Muestra | Por qué importa acá |
|---|---|---|
| `outsideLunch` | booleano, 28/28 | **Quién almuerza fuera.** Es el "full/terreno" a nivel de exploración |
| `commentKitchen` | 1 con dato | **Comentario dirigido a cocina**, dentro de la exploración |
| `redWineCount` / `whiteWineCount` | 28/28 | **Vino que se lleva cada exploración** |
| `startTime` / `endTime` | `07:30:00` / `16:00:00` | Planificado: a qué hora vuelve el grupo |
| `realStartTime` | 19-21 con dato | Salida real. `realEndTime` viene vacío |
| `travellersIds` | `[888311, 890136, …]` | Ata la exploración a personas… **por ID, no por nombre** |
| `numTravellers` / `maxQuota` | `6` / `6` | Pax y cupo |
| `name`, `abbreviation`, `area`, `activity`, `code` | | Identidad de la exploración |
| `comments` | 15 con dato | Comentario general |

`futureExplorationsOnline(dateStart, dateEnd)` sobre los últimos 7 días trajo
**29 filas con fechas PASADAS** (10-09, 12-09): el "future" del nombre no es
literal. Trae `traveller` anidado con `id`, `firstName`, `lastName`, `age` — o
sea que **sí** liga exploración ↔ persona por nombre. Pero 29 filas en una
semana, contra 28-30 por día del otro endpoint, sugiere que sólo cubre las
reservadas online. **No es el histórico completo.**

⚠️ **No pedir `totalCash`**: el servidor de PGO revienta con
`'ManyRelatedManager' object is not iterable`. Curiosamente la respuesta
**degradó parcial** en vez de morir entera — devolvió las 30 filas con
`errors` al lado. Es lo contrario de lo documentado en §4.2 y conviene no
confiarse: el comportamiento seguro sigue siendo pedir sólo lo que se usa.

### 7.3 El problema abierto: cómo se ata a NUESTRO viajero

Las dos vías tienen el mismo obstáculo, y es la decisión que hay que tomar:

- **Por HTML (`exp` + `historia`)**: el cruce ya está hecho — vienen en la fila
  del viajero. **Costo:** volver a abrir el Reporte Geos en cada corrida (una
  navegación más) y depender de columnas HTML, que es de lo que veníamos
  saliendo. **Ganancia:** dos líneas en `PGO_GEOS_COLS` y listo.
- **Por API (`hotelExplorationsDay`)**: dato más rico y estable, pero liga por
  `travellersIds` — **IDs internos de PGO que nuestro doc no guarda**. El roster
  sale de `travellersInhouse`, que hoy no pide el `id` del traveller. Habría que
  pedirlo y guardarlo para poder cruzar.

**Recomendación:** empezar por el HTML, que resuelve lo que se pidió con el
menor riesgo, y dejar la API para cuando se quiera lo de F&B (`outsideLunch`,
`commentKitchen`, los conteos de vino) — que es material para su propia
conversación, porque eso ya no es la ficha del viajero sino insumo de cocina.

### 7.4 Verificación contra datos reales (dry run, 2026-09-15)

Implementada la vía HTML, un `dry_run` contra PGO (no escribe Firebase):

```
roster (API): 100 viajeros en 42 habitaciones · 93 con nombre de país
/report-geos: 100 filas · hab, tipo viajero, viajero, nac, in/out, edad,
              exp, grupo, comentario geos, historia
exploraciones: 77 con exploración del día · 75 con histórico
Modo debug — Firebase no modificado.
```

**Sin advertencia de `histórico sin parsear`: los 75 parsearon limpios.** Los
formatos se habían deducido de muestras enmascaradas, así que esto era lo que
quedaba por confirmar. El degradado a `historiaTxt` sigue en su lugar por si el
formato cambia.

`nacName` llega en **93 de 100**, así que el respaldo legible para los códigos
sin bandera está poblado.

**Suelto, para otro día:** el reporte `/dietas` tiene columnas `hr in` y
`hr out` que tampoco mapeamos. No hacen falta —las horas reales ya vienen por
`reportInOut`, y sin el redondeo del HTML (§4.2)—, pero quedan anotadas.
