# -*- coding: utf-8 -*-
"""Genera el póster de salón: docs/poster-handbook.html (repo) y la versión
   para publicar como Artifact. Todo el póster es un solo SVG con viewBox en
   milímetros — 1 unidad = 1 mm de A4."""
import io, re, os

BASE = os.path.dirname(os.path.abspath(__file__))
REPO = '/home/user/Explora-GastroCycles'

qr_src = io.open(os.path.join(REPO, 'gastrocycles-qr.svg'), encoding='utf-8').read()
QR_D = re.search(r'<path style="fill:rgb\(0, 0, 0\)" d="([^"]+)"', qr_src).group(1)

# ── Contenido. Tono parte de servicio: sin verbos de relleno ni cláusulas
#    explicativas. Las líneas se cortan a mano porque SVG no reparte texto.
RAMAS = [
  ("Menú", [
     ["Servicio del día,", "D1 a D4"],
     ["Buffet · sopa ·", "principales · postres"],
     ["Restricciones por plato", "Veg · Vgt · GE · FS · Pesc"],
     ["Almuerzo, cena y bar", "por separado"],
  ]),
  ("Vinos", [
     ["Ficha por etiqueta"],
     ["Guion de venta"],
     ["Maridajes generales"],
     ["Tip del día, antes", "de Principales"],
  ]),
  ("PGO", [
     ["Dietas y alergias", "por habitación"],
     ["Restricciones", "y contadores"],
     ["Notas del equipo"],
     ["Se actualiza solo"],
  ]),
]
PIE = [("Se instala",   "Compartir → Agregar a inicio."),
       ("Tres idiomas", "Español · Inglés · Portugués."),
       ("Sin señal",    "Queda lo último que cargó.")]

# ── Grilla, en milímetros de A4 ───────────────────────────────────────────
M        = 15                 # margen lateral
CENTROS  = [45, 105, 165]     # centro de cada rama
AC_Y, AC_H = 51, 56           # bloque de acceso (la raíz)
Y_TRONCO_A  = 116             # el tronco baja hasta el travesaño
Y_BAJADA_A  = 124
Y_NOMBRE, Y_REGLA = 130.5, 134
Y_HOJA_1 = 145
LINEA_H  = 6.8                # entre líneas de una misma hoja
HOJA_GAP = 15.1               # entre hojas: separa ideas, no renglones
Y_PIE_R, Y_PIE_L, Y_PIE_T = 264, 271, 277.5

esc = lambda t: t.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
r2  = lambda v: round(v, 2)

# Ramas
ramas = []
for cx, (nombre, hojas) in zip(CENTROS, RAMAS):
    p = ['  <g>',
         f'    <text class="rama-n" x="{cx}" y="{Y_NOMBRE}">{esc(nombre.upper())}</text>',
         f'    <line class="rama-r" x1="{cx-23}" y1="{Y_REGLA}" x2="{cx+23}" y2="{Y_REGLA}"/>']
    y = Y_HOJA_1
    for i, hoja in enumerate(hojas):
        if i:
            p.append(f'    <circle class="sep" cx="{cx}" cy="{r2(y - HOJA_GAP/2 - 1.4)}" r="0.4"/>')
        for linea in hoja:
            p.append(f'    <text class="hoja" x="{cx}" y="{r2(y)}">{esc(linea)}</text>')
            y += LINEA_H
        y += HOJA_GAP
    p.append('  </g>')
    ramas.append("\n".join(p))

# Casillas del PIN
CX0, CW, CGAP, CY, CH = 78, 11.5, 2.8, 81, 15
casillas = []
for i in range(4):
    x = r2(CX0 + i*(CW+CGAP))
    casillas.append(f'    <rect class="casilla" x="{x}" y="{CY}" width="{CW}" height="{CH}" rx="0.8"/>')
    casillas.append(f'    <text class="pin-d" id="pin-{i}" x="{r2(x+CW/2)}" y="{CY+CH-4.4}"></text>')

pie = [f'  <line class="pie-r" x1="{M}" y1="{Y_PIE_R}" x2="{210-M}" y2="{Y_PIE_R}"/>']
for x, (label, texto) in zip([M, 75, 135], PIE):
    pie.append(f'  <text class="pie-l" x="{x}" y="{Y_PIE_L}">{esc(label.upper())}</text>')
    pie.append(f'  <text class="pie-t" x="{x}" y="{Y_PIE_T}">{esc(texto)}</text>')

SVG = f'''<figure class="poster">
<svg viewBox="0 0 210 297" role="img"
     aria-label="Póster del ATA Handbook: una entrada por QR y clave, y tres destinos — Menú, Vinos y PGO.">

  <rect class="fondo" x="0" y="0" width="210" height="297"/>

  <!-- Cabecera. La regla mide el ancho de HANDBOOK, como el ícono (§2.1). -->
  <text class="marca" x="105" y="30">The <tspan class="ata">ATA</tspan> Handbook</text>
  <line class="regla" x1="63" y1="35.5" x2="147" y2="35.5"/>
  <text class="tagline" x="105" y="43">El detalle, a mano.</text>

  <!-- RAÍZ: la única puerta. De acá cuelga todo lo demás. -->
  <g>
    <rect class="acceso" x="{M}" y="{AC_Y}" width="{210-2*M}" height="{AC_H}"/>
    <rect class="qr-fondo" x="20" y="54" width="50" height="50" rx="1"/>
    <g transform="translate(23 57) scale({round(44/990, 6)})"><path class="qr" d="{QR_D}"/></g>
    <text class="paso" x="78" y="66">ESCANEAR · O ESCRIBIR EN EL NAVEGADOR</text>
    <text class="url"  x="78" y="75.5">gastrocycles.company</text>
{chr(10).join(casillas)}
    <text class="acceso-n" x="78" y="102">La clave del salón. Una sola vez por teléfono.</text>
  </g>

  <!-- El ramaje: una entrada, tres destinos. -->
  <line class="rama-c" x1="105" y1="{AC_Y+AC_H}" x2="105" y2="{Y_TRONCO_A}"/>
  <line class="rama-c" x1="{CENTROS[0]}" y1="{Y_TRONCO_A}" x2="{CENTROS[2]}" y2="{Y_TRONCO_A}"/>
{chr(10).join(f'  <line class="rama-c" x1="{c}" y1="{Y_TRONCO_A}" x2="{c}" y2="{Y_BAJADA_A}"/>' for c in CENTROS)}

{chr(10).join(ramas)}

{chr(10).join(pie)}
</svg>
<figcaption class="cap">Una entrada — el QR y la clave — y tres destinos.</figcaption>
</figure>'''

CABEZA = '''<title>Póster de salón ATA</title>
<!--
  Póster de salón · A4 vertical · back-of-house.

  LA CLAVE NO VIVE EN ESTE ARCHIVO, y no debe: el repo es público, así que un
  PIN commiteado acá queda publicado y anula el gate de §4.4. Entra por tres
  vías, en este orden:
      poster-handbook.html?pin=1234   → la URL
      el campo de pantalla            → no se imprime
      lo que ese navegador recuerde   → de una impresión anterior
  Sin ninguna, las casillas van vacías y se escribe a mano.

  TODO EL PÓSTER ES UN SOLO SVG, viewBox en milímetros (1 unidad = 1 mm de A4).
  No es capricho: un layout de cajas HTML se recorre solo al cambiar de
  impresora, y esto se imprime en cualquier equipo que haya en el office. En
  SVG la grilla es la misma en pantalla, en A4 y en A3.

  OJO al editar el CSS: dentro de un SVG los tamaños van en px (= unidades del
  viewBox = mm acá). Un `font-size: 4.1` sin unidad es una declaración
  inválida, y el texto hereda los 16 px del body escalados por el viewBox —
  sale gigante y encimado.

  Imprimir: Chrome/Safari → Imprimir → A4 → activar "Gráficos de fondo".
-->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,600;1,400;1,500;1,600;1,700&family=Courier+Prime:wght@400;700&display=swap">
<style>
  /* La paleta del handbook trasladada al papel. Los acentos son los mismos
     (sienna del lockup, oro de la regla); cambia el soporte — una A4 en negro
     sale gris sucio en la impresora del office. El único bloque oscuro es el
     de acceso, y es una cita de la pantalla de la app. */
  :root{
    --papel:#F6F2EA; --hoja:#FFFDF9;
    --tinta:#22201c; --tinta-2:#5f584e; --tinta-3:#9a9186;
    --sienna:#c75c2a; --oro:#a8721a; --pantalla:#1a1917; --oro-luz:#c9902f;
    --serif:'Cormorant Garamond','Palatino Linotype',Georgia,serif;
    --mono:'Courier Prime','Courier New',monospace;
  }
  *{ box-sizing:border-box; }
  html,body{ margin:0; padding:0; }
  body{ background:var(--papel); color:var(--tinta); font-family:var(--mono);
        padding:22px 14px; -webkit-font-smoothing:antialiased; }

  .poster{ margin:0 auto; width:210mm; max-width:100%; }
  .poster svg{ display:block; width:100%; height:auto;
               box-shadow:0 2px 28px rgba(34,32,28,0.16); }
  .cap{ font-size:10px; letter-spacing:0.09em; color:var(--tinta-3);
        text-align:center; margin-top:9px; }

  /* Tipografía del póster. En px, que dentro del SVG son unidades del
     viewBox — o sea milímetros de papel. */
  .fondo{ fill:var(--hoja); }
  .marca{ font-family:var(--serif); font-size:13.5px; font-style:italic;
          font-weight:500; fill:var(--tinta); text-anchor:middle; }
  .marca .ata{ fill:var(--sienna); font-weight:700; letter-spacing:0.5px; }
  .regla{ stroke:var(--oro); stroke-width:0.25; }
  .tagline{ font-family:var(--serif); font-size:4.4px; font-style:italic;
            fill:var(--tinta-2); text-anchor:middle; }

  .acceso{ fill:var(--pantalla); }
  .qr-fondo{ fill:#ffffff; }
  .qr{ fill:#111111; }
  .paso{ font-family:var(--mono); font-size:2.7px; letter-spacing:0.36px; fill:var(--oro-luz); }
  .url{ font-family:var(--mono); font-size:5.6px; fill:#f0eeea; }
  .casilla{ fill:none; stroke:rgba(201,144,47,0.55); stroke-width:0.22; }
  .pin-d{ font-family:var(--mono); font-size:8.4px; font-weight:700;
          fill:var(--oro-luz); text-anchor:middle; }
  .acceso-n{ font-family:var(--serif); font-size:4px; font-style:italic; fill:#a8a099; }

  .rama-c{ stroke:var(--tinta-3); stroke-width:0.22; }
  .rama-n{ font-family:var(--mono); font-size:4.2px; font-weight:700;
           letter-spacing:0.5px; fill:var(--tinta); text-anchor:middle; }
  .rama-r{ stroke:var(--oro); stroke-width:0.22; }
  .hoja{ font-family:var(--serif); font-size:4.1px; fill:var(--tinta-2); text-anchor:middle; }
  .sep{ fill:var(--oro); opacity:0.5; }

  .pie-r{ stroke:var(--tinta-3); stroke-width:0.18; opacity:0.5; }
  .pie-l{ font-family:var(--mono); font-size:2.6px; letter-spacing:0.3px; fill:var(--oro); }
  .pie-t{ font-family:var(--serif); font-size:3.6px; fill:var(--tinta-2); }

  /* Control de pantalla: la clave antes de imprimir. No se imprime y no toca
     el archivo — queda en el navegador de quien imprime, que es donde debe. */
  .ctrl{ width:210mm; max-width:100%; margin:0 auto 11px; display:flex;
         align-items:center; gap:10px; flex-wrap:wrap; font-size:11px;
         letter-spacing:0.05em; color:var(--tinta-2); }
  .ctrl label{ text-transform:uppercase; letter-spacing:0.13em; color:var(--tinta-3); }
  .ctrl input{ width:76px; padding:5px 8px; font-family:var(--mono); font-size:14px;
               letter-spacing:0.28em; text-align:center; color:var(--tinta);
               background:var(--hoja); border:1px solid rgba(168,114,26,0.4);
               border-radius:3px; }
  .ctrl input:focus{ outline:2px solid var(--oro); outline-offset:1px; }
  .ctrl-nota{ color:var(--tinta-3); }

  @page{ size:A4 portrait; margin:0; }
  @media print{
    body{ background:#fff; padding:0; }
    .ctrl, .cap{ display:none; }
    .poster{ width:auto; }
    .poster svg{ width:210mm; height:297mm; box-shadow:none; }
    /* Blanco puro en papel: el tono del fondo no vale una pasada de tinta. */
    .fondo{ fill:#ffffff; }
  }
</style>'''

CONTROL = '''<div class="ctrl">
  <label for="pin-in">Clave del salón</label>
  <input id="pin-in" inputmode="numeric" pattern="[0-9]*" maxlength="4" placeholder="····" aria-describedby="ctrl-nota">
  <span class="ctrl-nota" id="ctrl-nota">Se escribe acá antes de imprimir. No queda en el archivo — sólo en este navegador.</span>
</div>'''

SCRIPT = '''<script>
  // El PIN nunca vive en el archivo. Entra por la URL (?pin=1234), por el
  // campo de pantalla, o por lo que este navegador recuerde de una impresión
  // anterior. Sin ninguna, las casillas van vacías y se escribe a mano.
  (function(){
    var CLAVE = 'ata.poster.pin';
    var campo = document.getElementById('pin-in');
    var digitos = [0,1,2,3].map(function(i){ return document.getElementById('pin-' + i); });
    var casillas = document.querySelectorAll('.casilla');

    function pintar(pin){
      var ok = /^[0-9]{4}$/.test(pin);
      for (var i = 0; i < 4; i++) digitos[i].textContent = ok ? pin[i] : '';
      // Vacías, las casillas se atenúan: se leen como espacio para escribir a
      // mano, no como un error de impresión.
      for (var j = 0; j < casillas.length; j++) casillas[j].style.opacity = ok ? '1' : '0.55';
    }

    var guardado = '';
    try { guardado = localStorage.getItem(CLAVE) || ''; } catch(e){}
    var inicial = new URLSearchParams(location.search).get('pin') || guardado;
    if (/^[0-9]{4}$/.test(inicial)) campo.value = inicial;
    pintar(campo.value);

    campo.addEventListener('input', function(){
      campo.value = campo.value.replace(/[^0-9]/g, '').slice(0, 4);
      pintar(campo.value);
      try {
        if (/^[0-9]{4}$/.test(campo.value)) localStorage.setItem(CLAVE, campo.value);
        else localStorage.removeItem(CLAVE);
      } catch(e){}
    });
  })();
</script>'''

io.open(os.path.join(BASE,'poster-artifact.html'),'w',encoding='utf-8',newline='').write(
    CABEZA + "\n" + CONTROL + "\n" + SVG + "\n" + SCRIPT + "\n")
io.open(os.path.join(REPO,'docs/poster-handbook.html'),'w',encoding='utf-8',newline='').write(
    '<!doctype html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
    + CABEZA + '\n</head>\n<body>\n' + CONTROL + "\n" + SVG + "\n" + SCRIPT + '\n</body>\n</html>\n')
print('generado')
