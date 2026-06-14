# The ATA Handbook - Notas de versión

> Paquete en revisión (staging) - documento vivo, se actualiza con cada mejora.

Este documento explica, en lenguaje claro, las mejoras que vienen en el paquete
que está en QA en staging y que aún no pasa a producción. La fuente editable es
`docs/notas-de-version.md`; el PDF se regenera con `docs/build_notas.py`.

## Paquete actual - 14 de junio de 2026

### 1. Comandera, ahora "Comande Smart"

La comandera (E-Check) se transformó en una herramienta de pedido más rápida,
completa y fácil de leer.

- **Nombre y tono.** La pestaña pasó de "E-Check" a **"Comande"**. Al entrar, el
  encabezado muestra la firma manuscrita **"Comande Smart"** - se lee como una
  invitación, con letra recatada, sobre el título funcional "Mesas activas".
- **Carta de bar ampliada.** Se agregaron categorías nuevas, organizadas por
  marca para acceso rápido (sin sub-menús que pinchar):
  - **Jugos & Bebidas:** bebidas (Coca regular/light/zero, ginger beer, agua
    tónica, fanta, sprite, sprite zero, ginger ale) y jugos naturales (chirimoya,
    mango, maracuyá, frutilla, frambuesa, piña, limonada y variantes).
  - **Cervezas:** Austral (Lager, Calafate) y Tropera (Strong Ale, Blonde Ale).
  - **Café & Té:** los cafés del manual de la pestaña Café, más Té Twinings
    (6 variedades) e Infusiones naturales (manzanilla, melisa, cedrón, digestivo,
    menta, rica rica, boldo, hoja de coca).
  - **Snack Bar:** Pizza, Empanadas, Hamburguesas (incluida la Vegetariana),
    Ensalada Bar. Pensada para ir creciendo estos días.
- **"Otro" en todas las categorías.** Cada categoría tiene un comodín para anotar
  algo fuera de la lista; al tocarlo se agrega la línea y se abre la nota para
  escribir el detalle. En Platos hay un **Special Request por tiempo**
  (Entrada / Principal / Postre), que cae en el curso correcto.
- **"Comanda completa", más útil.** Ahora abre en vista **Resumen**: cuántas
  unidades de cada producto hay en la mesa, de un vistazo (cuántos ceviches,
  cuántas copas de vino), con un toggle a la vista "Por comensal" de siempre.
- **Más rápida y ordenada.** El catálogo se muestra como una grilla de botones
  grandes (menos scroll, mejor para la hora pico), las categorías quedan
  alineadas en columnas parejas, y el teclado para cambiar/crear mesa ya no se
  traba al teclear.
- **Menos errores.** El comodín "Otro" solo queda grabado si se confirma con
  **Guardar** (cancelar no deja nada). Se eliminó un refresco automático que
  reiniciaba la lista al inicio mientras el mesero la estaba mirando.

### 2. Pantalla principal

- **Botón "86".** Nuevo recuadro para anotar lo que está **temporalmente no
  disponible**. A diferencia de los postres, el dato se queda fijo hasta que
  alguien lo edite o lo borre.
- **Layout más prolijo.** "Postres del servicio" se acortó a **"Postres"** para
  ganar espacio; Postres y 86 quedan lado a lado y justificados. Cuando hay datos
  cargados, se ordenan en columna - **Datos Turno, Postres, 86** - separados por
  líneas horizontales discretas.
- **Botón "Checklist & Protocolos" más sutil.** Se bajó el brillo (tinte tenue,
  borde fino): sigue destacando como punto de entrada, pero ya no compite con el
  resto de la pantalla.

### 3. Vinos

- **Vuelven dos Chardonnay.** Se reincorporó el **Aquitania Chardonnay**
  (Valle de Casablanca) junto al **SOLdeSOL Chardonnay** (Valle del Malleco).
  Ahora son dos vinos distintos, cada uno con su ficha correcta en español,
  inglés y portugués - se corrigió un cruce que mostraba el vino equivocado al
  cambiar de idioma. Ambos maridan con los mismos platos.
- **Filtro más claro.** Los botones "Vinos Premium" y "Maridajes" muestran una
  marca de cerrar cuando están activos, para que se entienda a primera vista que
  son un filtro que se prende y apaga.

## Contexto del paquete (mejoras previas ya en staging)

Este paquete también arrastra mejoras anteriores que aún no están en producción:
la pestaña **Checklist & Protocolos** (montaje al frente, estaciones, buscador
transversal, fotos de referencia), el **telón de carga** del arranque, la
**navegación** de pestañas en fila deslizable y la **armonización visual** de
Cocktails con el lenguaje editorial del programa.

## Notas operativas

- El botón **86** requiere una regla de Firebase para el path `/eightysix`
  (ya aplicada).
- Todo el paquete está **en revisión desde iPhone** antes de aprobarse para
  producción.

## Cómo se actualiza este documento

Editar `docs/notas-de-version.md` y regenerar el PDF:

    py docs/build_notas.py

El PDF queda en `docs/notas-de-version.pdf`, versionado en el repositorio.
