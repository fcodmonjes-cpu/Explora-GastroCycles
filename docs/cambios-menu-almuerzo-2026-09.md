# Menú de almuerzo · Cotejo con "Información Complementaria Dossier Menú de 4 Ciclos"

> Insumo: `INFORMACION_COMPLEMENTARIA_DOSSIER_MENU__DE_4_CICLOS_RESTAURANT.docx`
> (asesor, sin fecha en el archivo). Cotejado el 2026-09-07 contra
> `MENU_BUFFET` / `MENU_SOPAS` / `MENU_POSTRES` / `MENU_PRINCIPALES` de `index.html`.
> Estado: **plan, nada aplicado todavía.** Las decisiones marcadas ⚠ necesitan
> confirmación de cocina antes de tocar la matriz (regla dura de §7 Receta 1b:
> se transcribe, no se infiere).

---

## 0. Verificación anti-desfase (lo primero que se revisó)

El documento numera **Día #1 a #4 del ciclo**, la misma numeración que usa el
campo `day` de los arrays nuevos (el offset a D1-D4 de la app se aplica una sola
vez, en `menuToDish`). El cotejo se hizo plato por plato, por nombre:

| Día doc | Hojas | Veg. firmes | Granos | Cocidos | Prot. fría | Prot. caliente | Sopa | Postres |
|---|---|---|---|---|---|---|---|---|
| 1 | César ✓ | Papas doradas ✓ | Arroz y coco ✓ | Brócoli ✓ | Ceviche verde ✓ | *(el doc no lo trae)* | Pantrucas ✓ | Leche c/plátano · Mote c/huesillo · Peras v. blanco ✓ |
| 2 | Mostaza y rúcula ✓ | Berenjenas ✓ | Tabulé de mote ✓ | Repollo ✓ | Tartar ✓ | Pechuga de pollo ✓ | Quinoa ✓ | Duraznos · Almendrado · Membrillos ✓ |
| 3 | Rúcula y espinaca ✓ | Zapallo italiano ✓ | Garbanzos ✓ | Hongos ✓ | Salpicón camarón ✓ | Roast beef ✓ | Tomate tatemado ✓ | Peras v. tinto · Coulant · Piña ✓ |
| 4 | Lechuga y tomate ✓ | Pepino y kiwi ✓ | Porotos ✓ | Alcachofa y habas ✓ | Ceviche merkén ✓ | Pechuga de pato ✓ | Papa y puerro ✓ | Mil hojas · Arroz c/leche · Pomelo ✓ |

**Resultado: 23/24 bandejas + 4 sopas + 12 postres coinciden 1:1. Ningún plato
cambió de día ni de bandeja.** Todo lo que sigue son cambios *dentro* del plato.

La única bandeja sin información nueva es la **proteína caliente del Día 1**
(hoy "Lomo de Cerdo"): el documento no la menciona. → confirmar en briefing que
sigue siendo lomo de cerdo.

Recordatorio para el briefing: **doc Día 1 → D3 en la app**, doc 2 → D4,
doc 3 → D1, doc 4 → D2 (`MENU_CYCLE_OFFSET = 2`).

---

## 1. Cambios de MATRIZ (alergias / dietas) — lo que hay que corregir sí o sí

Estos son los que pueden terminar en un plato servido a quien no debía.

### 1.1 🔴 El pan gratato lleva **MANÍ**

El doc lo define por primera vez: *"Panko, **Maní**, Ajo, jengibre, aceite
vegetal y sal fina"*. Hoy ningún plato con pan gratato declara frutos secos.

| Plato | Línea | Hoy | Propuesta |
|---|---|---|---|
| `bf1-hojas` César | 2656 | `fs:1` | `fs:'*'` + nota "El pan gratato lleva maní; sin él, el plato no lleva frutos secos" |
| `bf2-profria` Tartar de vacuno | 2716 | `fs:1` | **`fs:0`** — sus propias `dietNotes` dicen que el gratato va *mezclado*, no aparte |
| `pr4-avecerdo` Pollo escabechado | 2924 | `fs:1` | **`fs:0`** — el `extended` dice "con pan gratato y orégano por encima" ⚠ |
| `bf1-cocidos` Brócoli · `bf2-cocidos` Repollo | 2673 / 2709 | `fs:1` | Se mantiene (gratato aparte), pero el `extended` debe decir que **lleva maní** |
| `bar-cesar` (carta de bar) | 3067 | sin eje `fs` | Agregar la advertencia de maní al `brief`/`extended` |

⚠ **Conflicto entre documentos:** la matriz de `MENU_PRINCIPALES` salió "textual
de la tabla de Restricciones del asesor (verificada plato por plato: 0
discrepancias)". Esa tabla dice `fs:1` para el pollo escabechado; este documento
dice que el gratato lleva maní. **Lo resuelve el asesor o cocina, no nosotros.**

Bonus del mismo bullet: el gratato se tuesta en **aceite vegetal**, no en
mantequilla. Los `extended` de `bf1-hojas` y `bar-cesar` dicen "tostado en
mantequilla y ajo" → corregir (el lácteo del César es el parmesano del aderezo,
no el pan).

### 1.2 🔴 El aderezo César **lleva anchoas**

Doc: *"Aderezo: yema de huevo, queso parmesano, **anchoas**, ajo, mostaza de
Dijon, tabasco, salsa inglesa…"*.

- `bf1-hojas` (2657) tiene hoy: `dietNotes.vgt = 'Sin el pollo ni el pan gratato. **El dressing no lleva anchoa.**'` → **es falso**.
- `bar-cesar` (3070) afirma "La base sin extras es vegetariana" → también cae.

⚠ Pregunta de briefing: **¿cocina prepara un aderezo sin anchoa a pedido?**
- Si sí → `vgt:'*'` con la nota corregida ("sin pollo, sin pan gratato y con aderezo sin anchoa, avisando a cocina").
- Si no → `vgt:0` en ambos platos.

(La salsa inglesa suele llevar anchoa y trazas de gluten: refuerza el punto.)

### 1.3 🔴 Frutos secos que hoy no están declarados

| Plato | Línea | Hoy | Propuesta | Fuente |
|---|---|---|---|---|
| `po3-granos` Coulant de chocolate | 2986 | `fs:1` | **`fs:0`** | *"El Coulant se hace con **harina de almendras**"* |
| `po2-fruta` Duraznos a la brasa | 2961 | `fs:1` | **`fs:0`** (o `'*'` si la granola va aparte) | *"la granola es un mix de cereales, cacao, miel, **frutos secos**, a excepción del maní"* |

El coulant es el más grave: es un postre de chocolate, nadie espera almendra.
⚠ De paso, ese "mix de cereales" de la granola abre duda de gluten
(`po2-fruta` hoy `ge:1, gs:1`) → **preguntar si el mix lleva avena/trigo.**

### 1.4 🟡 Platos que se ABREN (hoy los marcamos más restrictivos de lo que son)

| Plato | Línea | Hoy | Propuesta | Fuente |
|---|---|---|---|---|
| `bf4-firmes` Pepino, kiwi y yogurt | 2767 | `lac:0` | **`lac:1`** | *"El yogurt es **sin lactosa**"* |
| `po4-fruta` Mil hojas de manzana | 2999 | `lac:0`, `gs:0` | **`lac:'*'`** ("sin el helado") y **`gs:'*'`** ("sin la masa sablé") | *"apto … si le quitamos el helado" / "… si le quitamos la masa sablé"* |
| `po4-sinazucar` Pomelo, miel y quinoa | 3009 | `lac:0` | **`lac:'*'`** ("sin el helado") | *"apto … si le quitamos el helado"* |
| `po2-sinazucar` Membrillos asados | 2973 | `lac:'*'` | **`lac:1`** | *"Este postre **es lactose free**, pero NO vegano"* |

Sobre `po4-fruta`: quitando la sablé también se va la harina de almendra
→ ⚠ preguntar si `fs` pasa de `0` a `'*'`. Y ojo con `ge` (celiaquía): el doc
habla de "intolerancia al gluten", que en nuestra lectura es `gs`; **`ge` lo
dejo en 0 salvo que cocina confirme que no hay contaminación cruzada.**

### 1.5 ⚠ Tres preguntas de matriz que el documento abre y no cierra

1. **`so2` Sopa de quinoa — ¿sigue llevando mantequilla?** El doc entrega la
   receta completa (sofrito + SALCA + vino blanco + paprika/comino/menta seca +
   **aquafaba** + cacho de cabra) y **no menciona lácteos en ninguna parte**. La
   página dice "ligado con mantequilla para dar cuerpo… no apta para veganos por
   la mantequilla del caldo" (`veg:0, lac:0`). La aquafaba es exactamente el
   sustituto de ese rol. → **Si cocina confirma, la sopa pasa a `veg:1, lac:1`**
   y gana una opción vegana en un día que hoy no la tiene en la sopa.
2. **`so1` Pantrucas — ¿el caldo sigue llevando almejas y choritos?** Hoy
   `mar:0` con nota "el caldo base lleva almejas y choritos — no es separable".
   El doc describe el caldo (sofrito + caldo de pescado + arvejas) **sin
   mariscos**. → Si ya no los lleva, `mar:0 → 1` (y se cae la nota).
   *Dato nuevo del mismo plato:* las albóndigas llevan **Shaoxing** (vino de
   arroz) y el caldo **vino blanco** → relevante para quien no consume alcohol.
3. **`po2-granos` Almendrado — ¿es sin lactosa?** El financier lleva
   "mantequilla **sin lactosa**" y el semifrío es de leche de almendra. Hoy
   `lac:0`. → Preguntar si queda algún lácteo con lactosa; si no, `lac:1`.
   Además el doc suma **Kosher** al veto del colapez → agregarlo a
   `dietNotes.halal` (no hay eje Kosher, va en el texto).

### 1.6 🟡 Alérgenos sin eje propio que el doc revela y hoy no se dicen en ningún texto

No cambian la matriz (no hay eje), pero deben entrar al `extended` porque son
los que preguntan en mesa:

- **Huevo:** la emulsión del brócoli (`bf1-cocidos`) lleva **huevo cocido** —de
  ahí su `veg:0`, que hoy el texto no explica—; el ceviche del Día 1 lleva
  **mayo alimonada**; el aderezo César lleva yema.
- **Sésamo:** salsa del tartar (aceite de sésamo), hummus y zapallo (tahini),
  praliné de los membrillos, aderezo de los hongos.
- **Mostaza:** adobo del roast beef (mostaza Dijon), además del César y el tartar.
- **Pescado/anchoa:** aderezo César y aderezo vietnamita de `bf2-hojas` (salsa
  de pescado).
- **Ají nomoto (glutamato):** aparece en ~15 preparaciones del documento. No es
  alérgeno, pero lo preguntan. → Sugerencia: una línea en el brief general, no
  plato por plato.

---

## 2. Cambios de PLATO / INGREDIENTE relevantes para el briefing

Cambian lo que el garzón dice, no la matriz.

### 2.1 Correcciones donde la página hoy dice algo que el doc contradice

| Plato | La página dice | El doc dice |
|---|---|---|
| `so2` Sopa de quinoa | "con **tomate** y pimentón, menta fresca aparte" (2 veces) | **"Esta sopa ya no irá con tomates como parte de los vegetales"** (confirmar en briefing). Toppings aparte: menta fresca + **pimentón rojo horneado en cubitos** |
| `bf2-hojas` | aderezo "de sabor **asiático**" / "ensaladas del **sudeste asiático**" | **"es estilo vietnamita y NO asiático (SON TOTALMENTE DISTINTOS)"** |
| `bf2-profria` Tartar | salsa de yema, mostaza Dijon y **miso blanco**; lleva **rabanito** | salsa de yema + vinagre de arroz + **aceite de sésamo** + aceite vegetal; **no menciona miso ni rabanito**; cebolla **morada**; hierbas: perejil y ciboulette |
| `bf1-firmes` Papas | el aderezo toma cuerpo "con **el caldo de las mismas papas**" | el cuerpo lo da la **chantana (espesante)**; papas **blanqueadas** antes del horno; topping **ciboulette** |
| `bf3-hojas` | "**fruta de estación**"; charqui "en **hebras**" | la fruta es **membrillo**; el charqui es de **trucha salmonada** y va **casi en polvo**; **las hojas también pasan por la brasa**; se agregan **berros frescos** |
| `po4-granos` Arroz con leche | "leche y **horchata de arroz**" | la horchata es **leche evaporada + leche condensada + canela china + agua** (no lleva arroz) |
| `bf4-firmes` Pepino y kiwi | "sofrito de cebollín, ajo y **pieles de cítricos**" | aceite infusionado de 12 especias (jengibre, cebollín, ajo, cilantro, laurel, hinojo, comino, anís, clavo, pimienta, canela china) — **sin cítricos**; la salsa verde es puré de **jalapeños encurtidos** + cebollín + pepino + kiwi |
| `so4` Papa y puerro | guarniciones aparte: charqui, papas fritas, **ajo frito y cebolla frita** | sólo **ciboulette + papas fritas en cubitos**; puerro **sólo parte blanca**; la sopa se **licúa** |
| `bf3-granos` Garbanzos | "tomates **y pimentón** asados" | sólo **tomates al horno**; los **garbanzos fritos van aparte** como topping |
| `bf4-cocidos` Alcachofas | con "**pimentón asado**" | el doc no lo menciona; hierbas: hinojo, eneldo, menta, huacatay, albahaca |
| `bf4-profria` Ceviche | el nombre dice "**merkén**" | el doc no menciona merkén: el ahumado/picor viene del **cacho de cabra**; pescado = **pesca blanca** (mero, lenguado, vieja, corvina) |

### 2.2 Detalles que el doc pide destacar en servicio

- **`bf1-profria` Ceviche verde:** el corte es **sashimi**, y el doc pide
  destacarlo *"en comparación de otros ceviches de otros ciclos, que son en
  cubo"*. Los pepinos van **encurtidos por ósmosis**; la leche de tigre es más
  un **agua chile** que una leche de tigre tradicional.
- **`po3-granos` Coulant: hay que avisar la espera de 10–15 minutos** al tomar
  el pedido, para que el centro quede líquido. Montaje **en plato, no bowl**.
  Helado **70% cacao**.
- **`po4-fruta` Mil hojas:** montaje **en plato, no bowl**. Manzana **roja**.
- **`po4-granos` Arroz con leche:** **bowl** y **porción pequeña**.
- **`po3-fruta` Peras al vino tinto:** **bowl**; topping de **piel de pera en
  almíbar** crocante; el vino es carmenere o cabernet.
- **`po1-granos` Mote con huesillo:** son **4 mochis**, y el doc insiste en la
  referencia: es una **gomita masticable**, *no* un mochi japonés.
- **`po2-fruta` Duraznos:** montaje en **bowl**; la compota lleva albahaca y
  menta; el helado es de leche de cabra y **sí tiene lactosa**.
- **`po1-fruta` Leche con plátano:** el doc lo subraya en mayúsculas —
  **no es modificable, no puede ser lactose free** (leche entera + crema
  inglesa). → agregar `dietNotes.lac` para cortar la negociación en mesa.
- **Global:** *"todas las proteínas se condimentan con sal escamosa, pimienta y
  aceite de oliva"* y la mayoría va a **cocción lenta al vacío**.

### 2.3 🟡 "Sin azúcar añadida" — revisar el claim

`po1-sinazucar` y `po2-sinazucar` afirman hoy en el `extended`: *"Es parte de
nuestra carta de postres sin azúcar añadida"*. El documento muestra lo
contrario en dos de los tres:

- **Peras al vino blanco:** el praliné lleva **panela y azúcar flor**, el yogurt
  está **endulzado con miel**, las nueces se caramelizan con miel.
- **Piña asada:** el jengibre confitado se hace con **almíbar de azúcar
  invertida**.

El slot se llama "sin azúcar", pero decirle "sin azúcar añadida" a un viajero
diabético es un riesgo real. → **Decisión de owner + cocina**: o se corrige el
texto ("postre de fruta, con azúcar de la propia fruta y miel/panela en las
guarniciones") o se confirma qué significa exactamente la familia.

### 2.4 Enriquecimientos menores (van al `extended`, sin urgencia)

Tabulé (pepino, tomate brunoise, cebolla morada, **salsa tatemada**, limón
fermentado semanas en sal) · Arroz y coco (pieles **sólo de limón**; el sofrito
es un aceite infusionado llamado **"Lilaceas"** con lemongrass) · Berenjenas
(salsa macha con cebolla blanca; se termina con perejil y cebollín frescos) ·
Hongos (**shiitake y portobello**, cebolla morada, perejil, sezte de limón) ·
Repollo (**miso blanco = koji + fermento de poroto**; mantequilla sin lactosa
confirmada) · Roast beef (adobo con Dijon) · Porotos (charqui de **filete de
res**, cebolla **en pluma**) · Lechuga y tomate (aderezo con **ají amarillo**) ·
Peras al vino blanco (el vino es **Late Harvest**) · Zapallo italiano (soya
dulce = soya + azúcar china; aceite de ají con 9 especias) · Sopa de tomate
tatemado (ají verde, vino blanco, **aquafaba**) · Almendrado (financier con
levadura y vainilla de Madagascar; garrapiñadas con clara y sal).

---

## 3. Sólo redacción (no accionable, no va al briefing)

Definiciones de referencia que el doc da para que el garzón explique
(praliné, curd, hummus ligero, horchata, financier, mochi, colapez), nombres de
cortes (chifonade, brunoise, juliana, pluma), y precisiones de técnica sin
impacto operativo (sopleteado del pomelo, huevo en formato tortilla, blanqueado
previo). Se absorben al reescribir los `extended` de los platos que ya tocamos;
no justifican un commit propio.

---

## 4. Plan de implementación

Todo vive en `index.html` (bloque de datos, líneas 2652-3115). No hay i18n que
tocar: los platos nuevos son sólo español (`DISH_TRANS` cubre únicamente los
`d1..d60` legacy).

**Orden sugerido — tres commits, en una rama `fix/menu-almuerzo-complementario`:**

1. **`fix: alérgenos del menú de almuerzo (maní, almendra, anchoa)`** — sólo
   §1.1, §1.2 y §1.3. Es lo que no puede esperar al briefing salvo el conflicto
   ⚠ del pollo escabechado. Toca `diet`, `dietNotes` y el `extended` de:
   `bf1-hojas`, `bf2-profria`, `pr4-avecerdo`, `po3-granos`, `po2-fruta`,
   `bar-cesar` (+ mención de maní en `bf1-cocidos` y `bf2-cocidos`).
2. **`feat: aperturas de matriz confirmadas`** — §1.4 (yogurt sin lactosa,
   "sin el helado", "sin la masa sablé", membrillos lactose free). Cada `'*'`
   nuevo **obliga** a su entrada en `dietNotes` (regla dura §7 Receta 1b).
3. **`docs: correcciones de guion del menú de almuerzo`** — §2, después del
   briefing, con las respuestas de cocina ya en mano.

**Lo que NO se toca hasta el briefing:** §1.5 completo (sopa de quinoa,
pantrucas, almendrado), el eje `ge` de las mil hojas, el `veg:'*'` de membrillos
y piña, el pimentón de garbanzos y alcachofas, las aceitunas del pepino/kiwi, y
el claim "sin azúcar añadida".

**Validación antes de decir "listo"** (§12): paridad de backticks = 0 · sin
bytes NUL · `node --check` sobre los `<script>` inline · screenshot headless de
la vista Almuerzo en los 4 días · revisar a máquina que ningún `'*'` quede sin
su `dietNotes`.

---

## 5. Checklist para el briefing con cocina

1. ¿El pan gratato lleva maní en **todas** las preparaciones que lo usan?
2. ¿Se puede hacer el **aderezo César sin anchoa** a pedido, o el César queda no-vegetariano?
3. ¿La **granola** de los duraznos lleva avena/trigo? ¿Va aparte o mezclada?
4. ¿La **sopa de quinoa** todavía lleva mantequilla, o la aquafaba la reemplazó? ¿Sale el tomate?
5. ¿El caldo de las **pantrucas** sigue llevando almejas y choritos?
6. ¿El **almendrado** es sin lactosa (única mantequilla = sin lactosa)?
7. ¿Existe versión **sin mantequilla** de membrillos y piña, o son "no veganos" y punto?
8. **Mil hojas sin masa sablé**: ¿apto sólo para intolerancia, o también para celíaco (contaminación cruzada)?
9. ¿Las **aceitunas negras** son del pepino/kiwi o del bullet de porotos?
10. ¿Garbanzos y alcachofas siguen llevando **pimentón asado**?
11. ¿La proteína caliente del **Día 1** sigue siendo lomo de cerdo?
12. ¿Qué significa exactamente la familia **"sin azúcar"** de postres?
