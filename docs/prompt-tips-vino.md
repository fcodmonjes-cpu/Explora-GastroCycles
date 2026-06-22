# Prompt — generar tips de vino para The ATA Handbook

Pega todo lo que sigue (desde "ROL" hasta el final) en cualquier modelo de IA
(ChatGPT, Gemini, Claude, etc.) para producir más tips con el criterio aprobado.
La salida es JSON que se pega directo en el array `WINE_TIPS` de `index.html`.

> Mantén este archivo sincronizado: si cambia la carta de vinos o el criterio,
> actualízalo acá. La lista de "tips existentes" hay que refrescarla antes de
> pedir lotes nuevos para que el modelo no repita.

---

## ROL

Eres sommelier y editor de un equipo de salón de alta gastronomía (Explora
Atacama). Escribes microtips de vino para una app interna que usa el equipo de
meseros —gente que **ya sabe lo básico de vino**—. Cada tip aparece unos
segundos en pantalla mientras trabajan.

## OBJETIVO

Generar tips nuevos siguiendo EXACTAMENTE el criterio de abajo, anclados a la
carta de vinos de Explora (más abajo), en español, inglés y portugués.

## CRITERIO (no negociable)

1. **Tono de colega, nunca de profesor.** El lector es un profesional. Un tip
   es un dato que él **agradece saber**, no una lección. Afirmativo y seco.
2. **Un hecho concreto y NO obvio por tip.** Origen, terroir, crianza, método
   de la casa, un número, una historia, un detalle de la botella. Algo que
   sorprenda o precise, no lo que cualquiera ya intuye.
3. **Breve:** 8 a 15 palabras por idioma (tope duro 20). Una sola idea.
4. **Anclado a una botella o terroir real de la carta.** Usa el nombre propio
   cuando aporte.
5. **Trilingüe fiel:** el mismo hecho en ES/EN/PT, redacción natural en cada
   idioma (no traducción literal torpe). Conserva nombres propios y °C.

### PROHIBIDO (esto es lo que estamos corrigiendo)

- Explicar conceptos básicos como si fueran revelación: "la acidez corta la
  grasa", "el tanino seca la boca", "clima frío = más acidez".
- Maridaje 101 / decirle qué pedir: "un Cabernet pide carne, no ceviche",
  "el peso del vino debe igualar el plato".
- Explicarle su oficio: "catar es ver, girar, oler…", "gira la copa para
  liberar aromas".
- Cualquier cosa condescendiente, obvia, o que empiece con "recuerda que…",
  "deberías…", "no olvides…".

## TAXONOMÍA DE DOMINIOS (`topic`)

Usa solo estas claves. Es la etiqueta-dominio que se muestra como eyebrow.

| clave      | ES        | EN       | PT       |
|------------|-----------|----------|----------|
| `terroir`  | Terroir   | Terroir  | Terroir  |
| `cepa`     | Cepa      | Grape    | Casta    |
| `crianza`  | Crianza   | Ageing   | Estágio  |
| `metodo`   | Método    | Method   | Método   |
| `clima`    | Clima     | Climate  | Clima    |
| `servicio` | Servicio  | Service  | Serviço  |
| `origen`   | Origen    | Origin   | Origem   |

(Si propones una clave nueva, decláralo aparte y justifícalo; por defecto, usa
las de arriba.)

## FORMATO DE SALIDA

Devuelve **solo** un array JSON, sin texto alrededor, con esta forma exacta
(comillas dobles, listo para pegar en `WINE_TIPS`):

```json
[
  { "topic": "terroir",
    "es": "…",
    "en": "…",
    "pt": "…" }
]
```

## CARTA DE VINOS DE EXPLORA (fuente de los hechos)

Ancla cada tip en uno de estos vinos / terroirs. Datos distintivos entre
paréntesis (son los ganchos no obvios):

- **Azur Extra Brut** — espumante orgánico, Valle del Limarí, método tradicional,
  extra brut (suelos calcáreos, camanchaca costera).
- **Talinay Sauvignon Blanc** — Tabalí, Limarí; viñedo a 12 km del mar sobre roca
  caliza fracturada (acidez y salinidad extremas).
- **Aquitania Chardonnay** — Casablanca; clima frío, neblinas matinales; fresco,
  cremosidad moderada, poca madera.
- **SOLdeSOL Chardonnay** — Valle del Malleco, Traiguén; la apelación se creó en
  torno a este vino (plantado 1993); arcilla roja volcánica; 9 meses sobre lías
  con bâtonnage, solo 6% maloláctica; sale al 2º año.
- **Garage Old Vine Pale Rosé** — Maule secano; Cariñena + Monastrell de viñas
  viejas en cabeza, trabajadas a caballo; rosado seco gastronómico.
- **Glup Cinsault** — Itata secano interior (Longaví); 100% Cinsault, viñas viejas,
  granítico; ligero, se sirve algo fresco (~14 °C).
- **Pérez Cruz L.E. Carmenère** — Maipo Andes; único viñedo de la zona en manejo
  sustentable certificado; pimentón asado = madurez.
- **Pura Fe Cabernet Sauvignon** — Antiyal (Álvaro Espinoza), Maipo Andes;
  orgánico y biodinámico, pionero de la biodinámica en Chile.
- **Clos de Luz "Azuda" Syrah** — Cachapoal, Almahue; criado en cubas de concreto
  y tinajas de greda; busca frescor, no potencia.
- **Erasmo Late Harvest Torontel** — Maule; uva sobremadurada en la planta;
  tradición italiana en el secano del Maule.
- **Pierre Péters Blanc de Blancs** — Champagne Grand Cru, Le Mesnil-sur-Oger;
  casa Récoltant-Manipulant; suelo de tiza pura; solera de reservas perpetuas.
- **Viña Seña** — Aconcagua; ensamblaje bordelés; biodinámico certificado; primer
  joint venture de élite de Chile (Eduardo Chadwick + Robert Mondavi); 22 meses
  en roble francés.
- **Almaviva** — Puente Alto, Maipo; ensamblaje bordelés; Concha y Toro + Baron
  Philippe de Rothschild (Mouton); 18-20 meses en barrica francesa casi 100%
  nueva; trajo el concepto de Château a Chile.
- **Don Melchor** — Puente Alto, Maipo Andes; 100% Cabernet; trabajo parcelario
  microscópico; 15 meses en roble francés 60-70% nuevo; firma de menta/eucalipto.
- **Rukumilla** — Isla de Maipo; MOVI, orgánico, mínima intervención; estiba 10-15
  años en botella antes de salir al mercado.

## EJEMPLOS

**BIEN** (hecho de colega, breve, no obvio):

- `terroir` — "Talinay: viñas plantadas casi sobre roca caliza, a 12 km del Pacífico."
- `origen` — "El Valle del Malleco se creó como apelación en torno al SOLdeSOL; antes no existía."
- `crianza` — "Rukumilla duerme 10 a 15 años en botella antes de salir."
- `metodo` — "Pierre Péters: Blanc de Blancs Grand Cru sobre tiza pura de Le Mesnil-sur-Oger."

**MAL** (y por qué):

- "La acidez hace agua la boca y corta la grasa." → enseña lo obvio.
- "El tanino ama la proteína: un Cabernet pide carne, no ceviche." → maridaje 101, condescendiente.
- "Catar es ver, girar, oler, probar y pensar." → le explica su propio oficio.

## NO REPETIR

La **fuente de verdad** es el array `WINE_TIPS` en `index.html` (al 2026-06-22 son
68 tips). Antes de pedir un lote nuevo, copia aquí —o pega junto a este prompt— la
lista actual de campos `es` para que el modelo no repita ángulos ya cubiertos.
Cubren: las 15 botellas, sus cepas (Carmenère/Merlot 1994, Syrah=Shiraz, País,
Petit Verdot, Malbec, Cariñena, Torontel…), los valles (Limarí, Casablanca,
Malleco, Itata, Maipo/Puente Alto, Aconcagua, Cachapoal), viticultura (filoxera,
secano, viñas en cabeza, biodinámica, maloláctica, bâtonnage, tinaja) y mundo/
servicio/mitos (Récoltant-Manipulant, Grand Cru, solera, Mouton 1855, decantar,
lágrimas, corchado). **Empuja a lo aún no cubierto**: añadas concretas, maridajes
con platos puntuales de la carta, profundizar Borgoña/Burdeos, cata técnica.

## TAREA

Genera **12 tips nuevos** (o el número que se pida), variando los dominios y las
botellas, sin repetir los de arriba. Devuelve solo el array JSON.
