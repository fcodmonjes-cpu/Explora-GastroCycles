#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera la ficha de estudio en PDF del menú de almuerzo del handbook.

Los datos de los platos (nombre, guion, matriz de 9 ejes, notas) se LEEN de
`index.html`, no se transcriben a mano: así la ficha no puede quedar diciendo
algo distinto de lo que muestra la app. La prosa didáctica —los conceptos de
dieta, los ganchos de memoria, el cuestionario— vive acá.

Uso:  python3 generar_ficha_estudio.py [día]      (día 1..4, por defecto 1)
"""
import os
import re
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, NextPageTemplate,
                                PageBreak, PageTemplate, Paragraph, Spacer, Table,
                                TableStyle)

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FUENTE_HTML = os.path.join(RAIZ, 'index.html')
DIA = sys.argv[1] if len(sys.argv) > 1 else '1'
SALIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      'menu-almuerzo-dia-%s.pdf' % DIA)

# ── Tipografía ───────────────────────────────────────────────────────────────
# Serif para la prosa y mono para las franjas de veredicto, que es la misma
# división que usa el handbook (Cormorant Garamond + Courier Prime).
#
# Dos cuidados que no son opcionales:
#   1. Hay que registrar la FAMILIA, no sólo las caras sueltas. Sin
#      registerFontFamily, reportlab no encuentra la negrita y renderiza los
#      <b> en redonda, en silencio y sin avisar.
#   2. Ninguna serif de las disponibles trae ✗. Por eso TODA celda o párrafo
#      que lleve ✗ o ✓ va en monoespaciada (DejaVu Sans Mono sí los trae);
#      si no, salen como cajas vacías.
PLEX   = '/mnt/skills/examples/canvas-design/canvas-fonts'
DEJAVU = '/usr/share/fonts/truetype/dejavu'
for alias, ruta in [
        ('Serif',    os.path.join(PLEX, 'IBMPlexSerif-Regular.ttf')),
        ('Serif-B',  os.path.join(PLEX, 'IBMPlexSerif-Bold.ttf')),
        ('Serif-I',  os.path.join(PLEX, 'IBMPlexSerif-Italic.ttf')),
        ('Serif-BI', os.path.join(PLEX, 'IBMPlexSerif-BoldItalic.ttf')),
        ('Mono',     os.path.join(DEJAVU, 'DejaVuSansMono.ttf')),
        ('Mono-B',   os.path.join(DEJAVU, 'DejaVuSansMono-Bold.ttf')),
        ('Mono-I',   os.path.join(DEJAVU, 'DejaVuSansMono-Oblique.ttf')),
        ('Mono-BI',  os.path.join(DEJAVU, 'DejaVuSansMono-BoldOblique.ttf'))]:
    pdfmetrics.registerFont(TTFont(alias, ruta))
pdfmetrics.registerFontFamily('Serif', normal='Serif', bold='Serif-B',
                              italic='Serif-I', boldItalic='Serif-BI')
pdfmetrics.registerFontFamily('Mono', normal='Mono', bold='Mono-B',
                              italic='Mono-I', boldItalic='Mono-BI')

TINTA    = colors.HexColor('#1a1a1a')
SUAVE    = colors.HexColor('#5f5f5f')
ORO      = colors.HexColor('#9a6621')
ALERTA   = colors.HexColor('#a3341f')
LINEA    = colors.HexColor('#cfcfcf')
FONDO    = colors.HexColor('#f4f1ec')

S = {}
S['h1']    = ParagraphStyle('h1', fontName='Serif-B', fontSize=19, leading=24,
                            textColor=TINTA, spaceBefore=0, spaceAfter=3)
S['h2']    = ParagraphStyle('h2', fontName='Serif-B', fontSize=13, leading=17,
                            textColor=TINTA, spaceBefore=14, spaceAfter=5)
S['h3']    = ParagraphStyle('h3', fontName='Serif-B', fontSize=10.5, leading=14,
                            textColor=TINTA, spaceBefore=9, spaceAfter=2)
S['p']     = ParagraphStyle('p', fontName='Serif', fontSize=9.3, leading=13.4,
                            textColor=TINTA, alignment=TA_JUSTIFY, spaceAfter=5)
S['sub']   = ParagraphStyle('sub', fontName='Mono', fontSize=7.4, leading=11,
                            textColor=SUAVE, spaceAfter=8)
S['slot']  = ParagraphStyle('slot', fontName='Mono-B', fontSize=6.9, leading=10,
                            textColor=ORO, spaceAfter=1)
S['dish']  = ParagraphStyle('dish', fontName='Serif-B', fontSize=10.2, leading=13,
                            textColor=TINTA, spaceAfter=2)
S['strip'] = ParagraphStyle('strip', fontName='Mono', fontSize=7.6, leading=11,
                            textColor=ALERTA, spaceAfter=3)
S['li']    = ParagraphStyle('li', fontName='Serif', fontSize=9.0, leading=12.8,
                            textColor=TINTA, leftIndent=11, bulletIndent=2, spaceAfter=2.5)
S['nota']  = ParagraphStyle('nota', fontName='Serif', fontSize=8.5, leading=12,
                            textColor=SUAVE, leftIndent=11, spaceAfter=2.5)
S['cellh'] = ParagraphStyle('cellh', fontName='Mono-B', fontSize=7.2, leading=9.6,
                            textColor=TINTA)
S['cell']  = ParagraphStyle('cell', fontName='Serif', fontSize=8.2, leading=11)
S['cellm'] = ParagraphStyle('cellm', fontName='Mono', fontSize=7.4, leading=10.4,
                            textColor=ALERTA)
S['q']     = ParagraphStyle('q', fontName='Serif-B', fontSize=9.0, leading=12.6,
                            textColor=TINTA, spaceAfter=1)
S['a']     = ParagraphStyle('a', fontName='Serif', fontSize=9.0, leading=12.6,
                            textColor=SUAVE, leftIndent=11, spaceAfter=6)
# Igual que h3 pero pegado a lo que sigue: evita que el título de una sección
# quede huérfano al pie de la página. Es más liviano que envolver título y
# primera ficha en un KeepTogether, que empujaba la sección entera de página.
S['h3s']   = ParagraphStyle('h3s', parent=S['h3'], keepWithNext=1)
S['pre']   = ParagraphStyle('pre', fontName='Mono', fontSize=7.6, leading=11.6,
                            textColor=TINTA, spaceAfter=3)

# ── Los 9 ejes, en el orden en que la app los muestra ────────────────────────
EJES = [
    ('veg',   'Veg',   'Vegano'),
    ('vgt',   'Vgt',   'Vegetariano'),
    ('pesc',  'Pesc',  'Pescetariano'),
    ('mar',   'Mar',   'Sin mariscos'),
    ('fs',    'FS',    'Sin frutos secos'),
    ('lac',   'Lac',   'Sin lactosa'),
    ('ge',    'GE',    'Sin gluten estricto'),
    ('gs',    'GS',    'Sin gluten superficial'),
    ('halal', 'Halal', 'Sin cerdo / Halal'),
]
SLOTS = {
    'hojas': 'HOJAS', 'firmes': 'VEGETALES FIRMES', 'granos': 'GRANOS',
    'cocidos': 'VEGETALES COCIDOS', 'profria': 'PROTEÍNA FRÍA', 'prococ': 'PROTEÍNA COCIDA',
    'vegana': 'VEGANA', 'mar': 'DE MAR', 'avecerdo': 'AVE / CERDO', 'res': 'CARNE DE RES',
    'fruta': 'FRUTA', 'granos2': 'GRANOS Y CHOCOLATE', 'sinazucar': 'SIN AZÚCAR',
}


# ── Lectura del bloque de datos ──────────────────────────────────────────────
def _bloque(src, nombre):
    i = src.index('const %s = [' % nombre)
    return src[i:src.index('\n];', i)]


def _desescapar(s):
    return s.replace("\\'", "'").replace('\\"', '"').replace('\\\\', '\\')


def leer_platos(src, arreglo, dia):
    """Devuelve los platos del día pedido, con su matriz y sus notas."""
    salida = []
    for trozo in re.split(r"\n  (?=\{id:')", _bloque(src, arreglo)):
        trozo = trozo.strip()
        cab = re.match(r"\{id:'([^']+)',day:'(\d)'", trozo)
        if not cab or cab.group(2) != dia:
            continue
        d = {'id': cab.group(1)}
        for campo in ('slot', 'recipeDay', 'name', 'short', 'brief', 'extended', 'barTwin'):
            m = re.search(r"%s:'((?:[^'\\]|\\.)*)'" % campo, trozo)
            d[campo] = _desescapar(m.group(1)) if m else None
        d['diet'] = dict(re.findall(r"(\w+):\s*(0|1|'\*')",
                                    re.search(r"diet:\{([^}]*)\}", trozo).group(1)))
        notas = re.search(r"dietNotes:\{(.*?)\},\n", trozo, re.S)
        d['notes'] = ({k: _desescapar(v) for k, v in
                       re.findall(r"(\w+):'((?:[^'\\]|\\.)*)'", notas.group(1))}
                      if notas else {})
        salida.append(d)
    return salida


def valor(d, eje):
    """1 apto · 0 no apto · '*' condicional · None sin dato."""
    v = d['diet'].get(eje)
    return None if v is None else ('*' if v == "'*'" else int(v))


def franja(d):
    """La misma franja que la ficha cerrada del handbook, con su corte en 4."""
    no   = [a for a in EJES if valor(d, a[0]) == 0]
    cond = [a for a in EJES if valor(d, a[0]) == '*']
    sind = [a for a in EJES if valor(d, a[0]) is None]
    partes = []
    if no:
        partes.append('✗ ' + ' '.join(a[1] for a in no[:4]) +
                      (' +%d' % (len(no) - 4) if len(no) > 4 else ''))
    if cond:
        partes.append('✓* ' + ' '.join(a[1] for a in cond))
    if sind:
        partes.append('? ' + ' '.join(a[1] for a in sind))
    return '  ·  '.join(partes)


def no_aptos(d):
    return [a[2] for a in EJES if valor(d, a[0]) == 0]


def condicionales(d):
    return [(a[2], d['notes'].get(a[0], '')) for a in EJES if valor(d, a[0]) == '*']


# ── Maquetación ──────────────────────────────────────────────────────────────
def regla(ancho=None):
    t = Table([['']], colWidths=[ancho or 170 * mm], rowHeights=[0.6])
    t.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, -1), 0.6, LINEA)]))
    return t


def caja(titulo, filas, color_titulo=TINTA):
    """Bloque con fondo, para reglas y avisos que no deben perderse."""
    dentro = [Paragraph(titulo, ParagraphStyle('bt', parent=S['h3'], spaceBefore=0,
                                               textColor=color_titulo))]
    for f in filas:
        dentro.append(Paragraph(f, S['p']))
    t = Table([[dentro]], colWidths=[170 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), FONDO),
        ('LEFTPADDING', (0, 0), (-1, -1), 9), ('RIGHTPADDING', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LINEBEFORE', (0, 0), (0, -1), 2, ORO),
    ]))
    return t


def tabla(cabeceras, filas, anchos, mono_cols=()):
    """`mono_cols` son las columnas que van en monoespaciada. Es obligatorio
    para cualquier celda con ✗ o ✓: la serif de DejaVu no trae esos glifos y
    los dibuja como cajas vacías."""
    datos = [[Paragraph(c, S['cellh']) for c in cabeceras]]
    for f in filas:
        fila = []
        for i, c in enumerate(f):
            fila.append(Paragraph(c, S['cellm'] if i in mono_cols else S['cell']))
        datos.append(fila)
    t = Table(datos, colWidths=anchos, repeatRows=1)
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEBELOW', (0, 0), (-1, 0), 0.8, TINTA),
        ('LINEBELOW', (0, 1), (-1, -2), 0.3, LINEA),
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return t


def _inline(texto):
    """Escapa para reportlab y traduce **negrita**, *cursiva* y `mono`."""
    t = texto.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t)
    t = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'<i>\1</i>', t)
    t = re.sub(r'`(.+?)`', r'<font face="Mono" size="8">\1</font>', t)
    return t


def markdown_a_flowables(md):
    """Subconjunto de markdown suficiente para el anexo: títulos, listas,
    citas, tablas de pipes y separadores. Evita el volcado monoespaciado,
    que parte palabras y desborda el margen."""
    salida, buffer_tabla = [], []

    def cerrar_tabla():
        if not buffer_tabla:
            return
        filas = [[c.strip() for c in f.strip().strip('|').split('|')] for f in buffer_tabla]
        filas = [f for f in filas if not all(set(c) <= set('-: ') for c in f)]
        if filas:
            anchos = [26 * mm, 24 * mm, 120 * mm][:len(filas[0])]
            anchos[-1] = 170 * mm - sum(anchos[:-1])
            salida.append(tabla([_inline(c) for c in filas[0]],
                                [[_inline(c) for c in f] for f in filas[1:]], anchos))
            salida.append(Spacer(1, 6))
        buffer_tabla[:] = []

    for linea in md.split('\n'):
        s = linea.rstrip()
        if s.startswith('|'):
            buffer_tabla.append(s)
            continue
        cerrar_tabla()
        if not s.strip():
            continue
        if s.startswith('> '):
            salida.append(Paragraph(_inline(s[2:]), S['nota']))
        elif s.startswith('#'):
            nivel = len(s) - len(s.lstrip('#'))
            salida.append(Paragraph(_inline(s.lstrip('# ')),
                                    S['h3'] if nivel >= 2 else S['h2']))
        elif s.startswith('---'):
            salida.append(Spacer(1, 3)); salida.append(regla()); salida.append(Spacer(1, 5))
        elif s.lstrip().startswith('- '):
            salida.append(Paragraph(_inline(s.lstrip()[2:]), S['li'], bulletText='·'))
        elif re.match(r'^\d+\.\s', s):
            n, resto = s.split('.', 1)
            salida.append(Paragraph(_inline(resto.strip()), S['li'], bulletText=n + '.'))
        else:
            salida.append(Paragraph(_inline(s), S['p']))
    cerrar_tabla()
    return salida


def ficha(d, slot_label):
    """Una preparación: rótulo, nombre, franja, gancho y veredictos."""
    bl = [Paragraph(slot_label, S['slot']), Paragraph(d['name'], S['dish'])]
    f = franja(d)
    bl.append(Paragraph(f if f else 'sin exclusiones — apto en los nueve ejes', S['strip']))
    bl.append(Paragraph(d['brief'], S['p']))
    na = no_aptos(d)
    if na:
        bl.append(Paragraph('<b>No apto:</b> ' + ' · '.join(na), S['li']))
    for etiqueta, nota in condicionales(d):
        bl.append(Paragraph('<b>%s (con condición):</b> %s' % (etiqueta, nota), S['li']))
    for eje, nota in d['notes'].items():
        if valor(d, eje) == 0:
            lbl = dict((a[0], a[2]) for a in EJES)[eje]
            bl.append(Paragraph('<b>%s:</b> %s' % (lbl, nota), S['nota']))
    if d.get('barTwin'):
        bl.append(Paragraph('También en la Carta de Bar.', S['nota']))
    bl.append(Spacer(1, 4))
    return KeepTogether(bl)


def construir():
    src = open(FUENTE_HTML, encoding='utf-8').read()
    buffet = leer_platos(src, 'MENU_BUFFET', DIA)
    sopas  = leer_platos(src, 'MENU_SOPAS', DIA)
    prin   = leer_platos(src, 'MENU_PRINCIPALES', DIA)
    post   = leer_platos(src, 'MENU_POSTRES', DIA)
    todos  = buffet + sopas + prin + post

    orden_buffet = ['hojas', 'firmes', 'granos', 'cocidos', 'profria', 'prococ']
    orden_prin   = ['vegana', 'mar', 'avecerdo', 'res']
    orden_post   = ['fruta', 'granos', 'sinazucar']
    por_slot = lambda lista, orden: [next(x for x in lista if x['slot'] == s) for s in orden]
    buffet = por_slot(buffet, orden_buffet)
    prin   = por_slot(prin, orden_prin)
    post   = por_slot(post, orden_post)

    corto = {d['id']: d['short'] for d in todos}
    con   = lambda eje, v: [corto[d['id']] for d in todos if valor(d, eje) == v]

    H = []
    A = H.append

    # ── Portada ──────────────────────────────────────────────────────────────
    A(Paragraph('Menú de almuerzo · Día %s' % DIA, S['h1']))
    A(Paragraph('FICHA DE ESTUDIO · THE ATA HANDBOOK · EXPLORA ATACAMA', S['sub']))
    A(regla())
    A(Spacer(1, 8))
    A(Paragraph(
        'Este documento condensa lo que la tab <b>Menú › Almuerzo › D%s</b> del handbook muestra '
        'en pantalla, más la explicación de cómo se leen las restricciones alimentarias. Los '
        'nombres, los guiones y las matrices de dieta se extraen directamente del código de la '
        'aplicación: si el handbook cambia, este documento se regenera y cambia con él.' % DIA,
        S['p']))
    A(Paragraph(
        'Está pensado para memorizar, no para consultar en servicio. Para consultar está el '
        'handbook, que además filtra por restricción. Acá el objetivo es llegar al turno '
        'sabiendo de antemano qué hay, qué excluye cada plato y qué preguntar.', S['p']))
    A(Spacer(1, 4))
    A(caja('Cómo usar esta ficha', [
        '<b>1.</b> Aprende primero el esqueleto (§2): son siempre las mismas posiciones, lo único '
        'que rota es el plato que las ocupa. Sabiendo la percha, los platos se cuelgan solos.',
        '<b>2.</b> Lee §1 una vez y vuelve a ella cada vez que dudes entre dos ejes parecidos. '
        'GE contra GS y Pescetariano contra Sin mariscos son los dos pares que más se confunden.',
        '<b>3.</b> Pasa por §3 plato a plato, pero no intentes retener los ingredientes: retén el '
        'gancho de cada uno (§4) y la exclusión que lo define.',
        '<b>4.</b> Cierra con §6 en voz alta, tapando las respuestas. Si fallas una, vuelve sólo '
        'a esa ficha.',
    ]))

    # ── §1 Conceptos ─────────────────────────────────────────────────────────
    A(PageBreak())
    A(Paragraph('1 · Cómo se lee una restricción', S['h2']))
    A(Paragraph(
        'Cada preparación del handbook lleva una matriz de nueve ejes. Un eje no es un '
        'ingrediente: es <i>una persona con una necesidad</i>. La pregunta que responde no es '
        '«¿esto lleva lactosa?» sino «¿puedo servirle esto a alguien que evita la lactosa?».',
        S['p']))

    A(Paragraph('Los cuatro estados', S['h3']))
    A(Paragraph(
        'Todo eje de todo plato está en uno de cuatro estados. Confundirlos es el error que '
        'termina en un plato mal servido.', S['p']))
    A(tabla(
        ['EN LA FICHA', 'ESTADO', 'QUÉ SIGNIFICA Y QUÉ HACER'],
        [['(no aparece)', 'Apto',
          'Se puede servir tal cual. El handbook no lo dice: lo aptos se callan, para que lo que '
          'aparece en rojo sea exactamente lo que hay que mirar.'],
         ['✗', 'No apto',
          'No se sirve. No hay versión modificada. Se ofrece otra cosa.'],
         ['✓*', 'Apto con condición',
          'Sí se puede, pero <b>sólo</b> con el cambio que dice la nota, y la nota siempre está. '
          'Un asterisco sin nota sería un error del handbook, no una licencia para improvisar.'],
         ['?', 'Sin dato',
          'Nadie lo confirmó todavía. <b>Sin dato nunca es apto.</b> Se pregunta en cocina antes '
          'de servir. Es la diferencia entre «no» y «no sé», y el handbook la marca aparte a '
          'propósito.']],
        [26 * mm, 26 * mm, 118 * mm], mono_cols=(0,)))
    A(Spacer(1, 8))
    A(Paragraph(
        'En la ficha cerrada, la franja corta a los cuatro primeros no aptos y suma el resto: '
        '<font face="Mono">✗ Veg Vgt Pesc Mar +4</font> quiere decir ocho exclusiones, no cuatro. '
        'Abriendo la ficha se ven todas con nombre completo.', S['p']))

    A(Paragraph('Los nueve ejes', S['h3']))
    A(tabla(
        ['EJE', 'NOMBRE', 'A QUIÉN PROTEGE'],
        [['Veg', 'Vegano',
          'No consume ningún producto de origen animal: ni carne, ni pescado, ni lácteos, ni '
          'huevo, ni miel. La miel y el huevo son los que más se escapan.'],
         ['Vgt', 'Vegetariano',
          'No consume carne ni pescado, pero sí lácteos y huevo. Ojo con los caldos, las salsas '
          'de pescado y la anchoa: un plato sin carne visible puede no ser vegetariano.'],
         ['Pesc', 'Pescetariano',
          'Come pescado y mariscos, no carne ni ave. Un plato de pescado es apto; uno de pollo, '
          'no.'],
         ['Mar', 'Sin mariscos',
          'Alergia o rechazo a crustáceos y moluscos. <b>Es un eje distinto de Pesc:</b> un '
          'pescetariano puede comer camarón, un alérgico al marisco no.'],
         ['FS', 'Sin frutos secos',
          'Alergia a nueces, almendras, maní. Suele venir escondido en pralinés, harinas, '
          'crocantes y aceites.'],
         ['Lac', 'Sin lactosa',
          'Cubre desde la intolerancia hasta la alergia a la proteína de la leche. Si la nota '
          'dice que no hay versión modificable, no la hay.'],
         ['GE', 'Sin gluten estricto',
          'Celiaquía. Excluye no sólo el gluten del plato sino las trazas y la contaminación '
          'cruzada del pase: salsa de soya, miso, almidones, una sartén compartida.'],
         ['GS', 'Sin gluten superficial',
          'Quien evita el gluten por preferencia o molestia, no por enfermedad. Tolera trazas.'],
         ['Halal', 'Sin cerdo / Halal',
          'No consume cerdo. El handbook lo usa también como marca de las carnes que requieren '
          'confirmación para una dieta halal.']],
        [16 * mm, 34 * mm, 120 * mm]))

    A(Spacer(1, 6))
    A(caja('Los dos pares que se confunden', [
        '<b>GE contra GS.</b> Son dos personas distintas. Un plato marcado sólo <font face="Mono">'
        '✗ GE</font> no lleva gluten de verdad: lleva trazas (soya, miso, almidón) o comparte '
        'pase. Sirve para quien lo evita por preferencia; no sirve para un celíaco. Un plato '
        'marcado <font face="Mono">✗ GE ✗ GS</font> lleva gluten de verdad: harina, pan, pasta. '
        'La regla corta: <b>una sola cruz = trazas; dos cruces = el plato lo lleva.</b>',
        '<b>Pescetariano contra Sin mariscos.</b> El pescetariano es una <i>dieta</i>: incluye '
        'pescado y marisco. Sin mariscos suele ser una <i>alergia</i>: excluye crustáceos y '
        'moluscos, pero el pescado sigue en pie. Hay platos aptos para uno y no para el otro, y '
        'este día tiene dos.',
    ], color_titulo=ALERTA))

    # ── §2 Esqueleto ─────────────────────────────────────────────────────────
    A(PageBreak())
    A(Paragraph('2 · El esqueleto del día', S['h2']))
    A(Paragraph(
        'El almuerzo tiene siempre la misma arquitectura. Las posiciones no cambian nunca; lo '
        'único que rota es el plato que ocupa cada una. Aprender la percha primero convierte '
        'catorce nombres sueltos en cuatro grupos ordenados.', S['p']))
    A(Spacer(1, 3))
    A(Paragraph(
        '<font face="Mono-B" size="11">6 &#8211; 1 &#8211; 4 &#8211; 3&#160;&#160;=&#160;&#160;14 preparaciones</font>',
        ParagraphStyle('anchor', parent=S['p'], spaceAfter=7)))
    A(tabla(
        ['SECCIÓN', 'N°', 'LAS POSICIONES, SIEMPRE EN ESTE ORDEN'],
        [['Buffet', '6', 'Hojas → Vegetales firmes → Granos → Vegetales cocidos → '
                         'Proteína fría → Proteína cocida'],
         ['Sopa del día', '1', 'Una sola, ocupa el ancho de la vista'],
         ['Principales', '4', 'Vegana → De mar → Ave / cerdo → Carne de res'],
         ['Postres', '3', 'Fruta → Granos y chocolate → Sin azúcar']],
        [30 * mm, 10 * mm, 130 * mm]))
    A(Spacer(1, 7))
    A(caja('Por qué esto es la mitad del trabajo', [
        'Si un huésped pregunta «¿qué hay de vegetariano?», no hace falta repasar el menú: la '
        'posición <b>Vegana</b> de principales existe todos los días, y en el buffet siempre hay '
        'granos y vegetales. La percha responde antes que la memoria.',
        'Y al revés: si sabes que hoy el principal vegano es tal cosa, ya sabes que está en la '
        'primera posición de la sección de principales, no hay que buscarlo.',
    ]))

    A(Paragraph('Lo que este día permite', S['h3']))
    veganos = con('veg', 1)
    vegets  = con('vgt', 1)
    libres  = [d['short'] for d in todos
               if all(valor(d, a[0]) == 1 for a in EJES)]
    A(tabla(
        ['PARA QUIÉN', 'CUÁNTAS DE 14', 'CUÁLES'],
        [['Vegano', str(len(veganos)), ' · '.join(veganos)],
         ['Vegetariano', str(len(vegets)), ' · '.join(vegets)],
         ['Sin ninguna restricción marcada', str(len(libres)), ' · '.join(libres)]],
        [44 * mm, 22 * mm, 104 * mm]))

    # ── §3 El menú ───────────────────────────────────────────────────────────
    A(PageBreak())
    A(Paragraph('3 · El menú, preparación por preparación', S['h2']))
    A(Paragraph(
        'Tal como aparece en el handbook: rótulo de posición, nombre completo, la franja de '
        'exclusiones de la ficha cerrada y la descripción breve. Debajo, los veredictos '
        'desplegados.', S['p']))

    # El título de sección viaja pegado a su primera ficha: si no, queda
    # colgando solo al pie de una página y la sección empieza en la siguiente.
    def seccion(titulo, platos, rotulo):
        A(Paragraph(titulo, S['h3s']))
        for d in platos:
            A(ficha(d, rotulo(d)))

    seccion('Buffet · 6 bandejas', buffet, lambda d: SLOTS[d['slot']])
    seccion('Sopa del día', sopas, lambda d: 'SOPA DEL DÍA')
    seccion('Principales · 4', prin, lambda d: SLOTS[d['slot']])
    seccion('Postres · 3', post,
            lambda d: SLOTS['granos2' if d['slot'] == 'granos' else d['slot']])

    # ── §4 Ganchos ───────────────────────────────────────────────────────────
    A(PageBreak())
    A(Paragraph('4 · Un gancho por preparación', S['h2']))
    A(Paragraph(
        'Nadie memoriza catorce listas de ingredientes. Lo que sí se retiene es <i>una</i> imagen '
        'o una frase por plato, colgada de su posición fija. Estos son los ganchos de este día: '
        'la idea es que al oír el rótulo de la posición aparezca el gancho, y con el gancho, el '
        'plato.', S['p']))
    A(tabla(
        ['POSICIÓN', 'PLATO', 'EL GANCHO'],
        GANCHOS[DIA],
        [32 * mm, 40 * mm, 98 * mm]))

    # ── §5 Trampas ───────────────────────────────────────────────────────────
    A(PageBreak())
    A(Paragraph('5 · Las trampas de este día', S['h2']))
    A(Paragraph(
        'Lo que un plato parece y lo que un plato es no siempre coinciden. Estas son las '
        'discordancias de este día: son las que generan el error en mesa, y por eso van juntas '
        'en vez de repartidas entre las fichas.', S['p']))
    for titulo, cuerpo in TRAMPAS[DIA]:
        A(Paragraph(titulo, S['h3']))
        A(Paragraph(cuerpo, S['p']))

    A(Spacer(1, 4))
    A(Paragraph('El gluten de este día, ordenado', S['h3']))
    ge_solo = [d['short'] for d in todos if valor(d, 'ge') == 0 and valor(d, 'gs') == 1]
    ge_gs   = [d['short'] for d in todos if valor(d, 'ge') == 0 and valor(d, 'gs') == 0]
    ge_cond = [d['short'] for d in todos if valor(d, 'ge') == 0 and valor(d, 'gs') == '*']
    A(tabla(
        ['LECTURA', 'FRANJA', 'CUÁLES'],
        [['Lleva gluten de verdad — no sirve para nadie que lo evite',
          '✗ GE ✗ GS', ' · '.join(ge_gs) or '—'],
         ['Sólo trazas — sirve por preferencia, no para celíaco',
          '✗ GE', ' · '.join(ge_solo) or '—'],
         ['Separable — se quita la parte con gluten',
          '✗ GE ✓* GS', ' · '.join(ge_cond) or '—']],
        [62 * mm, 24 * mm, 84 * mm], mono_cols=(1,)))

    A(Spacer(1, 8))
    A(caja('Dudas abiertas — decirlas, no resolverlas', DUDAS[DIA], color_titulo=ALERTA))

    # ── §6 Autoevaluación ────────────────────────────────────────────────────
    A(PageBreak())
    A(Paragraph('6 · Autoevaluación', S['h2']))
    A(Paragraph(
        'En voz alta, tapando la respuesta. Responder mentalmente no sirve: el esfuerzo de '
        'recuperar es lo que fija el dato. Si fallas una, vuelve sólo a esa ficha y repite la '
        'tanda completa al día siguiente.', S['p']))
    A(Spacer(1, 3))
    for i, (q, a) in enumerate(PREGUNTAS[DIA], 1):
        A(Paragraph('%d. %s' % (i, q), S['q']))
        A(Paragraph(a, S['a']))

    # ── Anexo ────────────────────────────────────────────────────────────────
    A(PageBreak())
    A(Paragraph('Anexo · Prompt para generar el podcast de estudio', S['h2']))
    A(Paragraph(
        'Para convertir esta ficha en un episodio de audio de repaso. Se pega tal cual en la '
        'herramienta de generación de podcast, adjuntando este mismo PDF como fuente. El texto '
        'también está en <font face="Mono" size="8">docs/estudio/podcast-menu-almuerzo-dia-%s.prompt.md</font>, '
        'que es más cómodo para copiar.' % DIA, S['p']))
    A(Spacer(1, 3))
    prompt = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'podcast-menu-almuerzo-dia-%s.prompt.md' % DIA),
                  encoding='utf-8').read()
    for flow in markdown_a_flowables(prompt):
        A(flow)

    # ── Documento ────────────────────────────────────────────────────────────
    def pie(canvas, doc):
        canvas.saveState()
        canvas.setFont('Mono', 7)
        canvas.setFillColor(SUAVE)
        canvas.drawString(20 * mm, 12 * mm,
                          'The ATA Handbook · Menú de almuerzo · Día %s' % DIA)
        canvas.drawRightString(190 * mm, 12 * mm, str(doc.page))
        canvas.restoreState()

    doc = BaseDocTemplate(SALIDA, pagesize=A4,
                          leftMargin=20 * mm, rightMargin=20 * mm,
                          topMargin=18 * mm, bottomMargin=20 * mm,
                          title='Menú de almuerzo · Día %s · Ficha de estudio' % DIA,
                          author='The ATA Handbook', subject='Material de estudio')
    marco = Frame(20 * mm, 20 * mm, 170 * mm, 259 * mm, id='cuerpo',
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id='normal', frames=[marco], onPage=pie)])
    doc.build(H)
    return SALIDA, len(todos)


# ── Contenido didáctico, por día ─────────────────────────────────────────────
GANCHOS = {'1': [
    ['Hojas', 'César', 'La que engaña. Parece la ensalada segura y es de las más restringidas: '
                       'el aderezo lleva <b>anchoa</b> y el pan gratato lleva <b>maní</b>.'],
    ['Vegetales firmes', 'Papas doradas', 'Una de las dos que sirven a todo el mundo. '
                                          'Sin lácteos: el cuerpo se lo da un espesante.'],
    ['Granos', 'Arroz y coco', 'La otra que sirve a todo el mundo, y además vegana. '
                               'Coco tostado, cebolla frita.'],
    ['Vegetales cocidos', 'Brócoli salteado', 'Vegetariana pero <b>no</b> vegana, y la razón no '
                                              'se ve: la emulsión lleva huevo cocido.'],
    ['Proteína fría', 'Ceviche verde', 'Corte <b>sashimi</b>, no cubo. Es lo que lo distingue de '
                                       'los ceviches de los otros ciclos.'],
    ['Proteína cocida', 'Pavo', 'El que reemplazó al lomo de cerdo. Por eso hoy esta bandeja '
                                '<b>sí</b> sirve para quien no come cerdo.'],
    ['Sopa del día', 'Pantrucas de pescado', 'El caldo lleva almejas y choritos y <b>no se puede '
                                             'separar</b>. Además, alcohol: vino blanco y Shaoxing.'],
    ['Principal · Vegana', 'Coliflor frita', 'El único principal sin carne. Frita como pollo '
                                             'frito y apilada igual.'],
    ['Principal · De mar', 'Curry rojo', 'Pescado, pero la pasta de curry lleva <b>camarón</b>: '
                                         'sirve al pescetariano, no al alérgico al marisco.'],
    ['Principal · Ave/cerdo', 'Milanesa de cerdo', 'El plato que más excluye de todo el día: '
                                                   '<b>ocho de los nueve ejes</b>.'],
    ['Principal · Carne de res', 'Sahofan de entraña', 'Fideos de <b>arroz</b>, no de trigo. '
                                                       'El gluten viene de la soya, no de la pasta.'],
    ['Postre · Fruta', 'Leche con plátano', 'El <b>no negociable</b>: crema inglesa de leche '
                                            'entera, no existe versión sin lactosa.'],
    ['Postre · Granos', 'Mote con huesillo', 'Cuatro mochis que son <b>gomitas</b>, no mochi '
                                             'japonés. Y mote de trigo: lleva gluten.'],
    ['Postre · Sin azúcar', 'Peras al vino blanco', 'La familia se llama «sin azúcar», pero lleva '
                                                    '<b>miel y panela</b>. Hay que ser preciso.'],
]}

TRAMPAS = {'1': [
    ('La César no es vegetariana, ni quitándole el pollo',
     'Es el error más fácil del día. El aderezo lleva <b>anchoa</b>, así que la base sin pollo '
     'sigue sin ser apta para un vegetariano. El handbook la marca <font face="Mono">✗ Vgt</font> '
     'por eso. Hasta hace poco la ficha decía lo contrario; se corrigió cuando el asesor entregó '
     'el desglose del aderezo.'),
    ('Dos preparaciones llevan maní, y las dos son separables',
     'El <b>pan gratato</b> lleva maní. Aparece en la César y acompaña al brócoli. En los dos '
     'casos va marcado <font face="Mono">✓* FS</font>, no <font face="Mono">✗</font>, porque se '
     'puede servir aparte o no servirlo. La diferencia importa: no es «no se puede», es «se pide '
     'sin gratato».'),
    ('Pescetariano no es lo mismo que sin mariscos, y hoy se nota',
     'El <b>curry rojo</b> y las <b>pantrucas</b> están marcados <font face="Mono">✗ Mar</font> '
     'pero <font face="Mono">Pesc</font> apto. Un huésped pescetariano los come sin problema; uno '
     'con alergia al marisco, no. En las pantrucas además el caldo no es separable: no hay versión '
     'sin mariscos.'),
    ('El postre de fruta no se puede adaptar',
     'La <b>leche con plátano</b> es lo único del día con una nota que cierra la conversación en '
     'vez de abrirla: la base es crema inglesa de leche entera y no existe versión sin lactosa. '
     'Conviene decirlo de entrada y ofrecer otro postre, no negociarlo en mesa.'),
    ('«Sin azúcar» no quiere decir sin azúcar añadida',
     'Las <b>peras al vino blanco</b> están en la familia «sin azúcar», pero el praliné lleva '
     'panela y azúcar flor y el yogurt está endulzado con miel. A un huésped diabético hay que '
     'decírselo con esas palabras: el dulzor viene de la fruta, la miel y la panela.'),
    ('Dos platos llevan alcohol',
     'Las <b>pantrucas</b> (vino blanco en el caldo y Shaoxing en las albóndigas) y las <b>peras</b> '
     '(cocidas en Late Harvest). No hay eje de alcohol en la matriz, así que no aparece en la '
     'franja: hay que saberlo y decirlo.'),
]}

DUDAS = {'1': [
    'El <b>Sahofan de entraña</b> tiene una discordancia entre su texto y su matriz: el guion dice '
    '«no es apto para quienes evitan el gluten», pero la matriz lo da apto en gluten superficial '
    '(<font face="Mono">✗ GE ✓ GS</font>). En servicio manda la matriz —es la que filtra el '
    'handbook—, pero conviene confirmarlo con cocina y alinear el texto.',
    'El mismo plato figura <font face="Mono">✗ Halal</font> sin llevar cerdo. Viene así de la tabla '
    'del asesor, probablemente por el faenamiento ritual y no por el ingrediente. Hasta que se '
    'confirme, se dice lo que dice la matriz sin inventar el motivo.',
    'Del <b>pavo</b> sólo sabemos que es pavo: falta el corte. Si un huésped pregunta si es '
    'pechuga, se pregunta en cocina.',
]}

PREGUNTAS = {'1': [
    ('¿Cuántas preparaciones tiene el almuerzo y cómo se reparten?',
     'Catorce: 6 bandejas de buffet, 1 sopa, 4 principales y 3 postres. El número ancla es 6-1-4-3.'),
    ('Nombra las seis posiciones del buffet en orden.',
     'Hojas, vegetales firmes, granos, vegetales cocidos, proteína fría, proteína cocida.'),
    ('Un huésped vegetariano pide la César sin pollo. ¿Se la sirves?',
     'No. El aderezo lleva anchoa, así que la base tampoco es vegetariana. Se ofrece otra bandeja: '
     'papas doradas, arroz y coco, o brócoli.'),
    ('¿Qué diferencia hay entre ✗ GE y ✗ GE ✗ GS?',
     'Una sola cruz significa trazas o contaminación cruzada: sirve para quien evita el gluten por '
     'preferencia, no para un celíaco. Dos cruces significan que el plato lleva gluten de verdad y '
     'no sirve para ninguno de los dos.'),
    ('¿Qué platos del día llevan gluten de verdad?',
     'Tres: las pantrucas (pasta de harina), la milanesa de cerdo (panko) y el mote con huesillo '
     '(mote de trigo).'),
    ('Un huésped es alérgico al marisco. ¿Puede comer el curry rojo de pescado?',
     'No. La pasta de curry lleva camarón. Sí puede comerlo un pescetariano: son ejes distintos.'),
    ('¿Qué dos preparaciones llevan maní y qué se hace con ellas?',
     'El pan gratato de la César y el que acompaña al brócoli. En ambos casos se pide sin gratato '
     'o servido aparte: van marcadas ✓* FS, no ✗.'),
    ('¿Cuál es el único principal apto para veganos?',
     'La coliflor frita en salsa de sésamo. Está en la primera posición de principales, que es '
     'siempre la vegana.'),
    ('¿Qué tiene de particular el ceviche de este día?',
     'El corte es sashimi, no cubo. Es la diferencia con los ceviches de los otros ciclos y el '
     'documento pide destacarlo.'),
    ('Un huésped intolerante a la lactosa quiere el postre de fruta. ¿Qué le dices?',
     'Que no hay versión sin lactosa: la base es crema inglesa de leche entera y no es modificable. '
     'Se le ofrece el mote con huesillo, que es vegano.'),
    ('¿Por qué la proteína cocida de este día sirve para quien no come cerdo?',
     'Porque cambió de lomo de cerdo a pavo. El eje Halal pasó de no apto a apto con ese cambio.'),
    ('¿Qué le dices a un huésped diabético sobre el postre «sin azúcar»?',
     'Que el nombre de la familia no es literal: las peras llevan miel en el yogurt y panela en el '
     'praliné. El dulzor viene de la fruta, la miel y la panela.'),
    ('¿Qué platos llevan alcohol y por qué no aparece en la franja?',
     'Las pantrucas (vino blanco y Shaoxing) y las peras (Late Harvest). No hay eje de alcohol en '
     'la matriz de nueve ejes, así que es información que hay que aportar de memoria.'),
    ('Ves ? Lac en una ficha. ¿Qué haces?',
     'Preguntar en cocina antes de servir. Sin dato no es apto: significa que nadie lo confirmó.'),
]}


if __name__ == '__main__':
    ruta, n = construir()
    print('PDF generado: %s (%d preparaciones del día %s)' % (ruta, n, DIA))
