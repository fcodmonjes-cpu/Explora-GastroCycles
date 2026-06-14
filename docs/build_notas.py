#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Genera docs/notas-de-version.pdf a partir de docs/notas-de-version.md.

Documento vivo: editar el .md y volver a correr `py docs/build_notas.py`.
Usa fpdf2 (pip install fpdf2). Fuentes core (Helvetica), así que el texto se
sanea a latin-1 (sustituyendo guiones largos, vinetas, etc.) para no romper.
"""
import os
from fpdf import FPDF

HERE = os.path.dirname(os.path.abspath(__file__))
MD   = os.path.join(HERE, "notas-de-version.md")
PDF  = os.path.join(HERE, "notas-de-version.pdf")

GOLD   = (186, 117, 23)    # #BA7517  acento principal
SIENNA = (199, 92, 42)     # #C75C2A  marca ATA
DARK   = (34, 34, 34)
MUTED  = (110, 110, 110)
RULE   = (210, 200, 188)

# Sustituciones para que el texto entre en latin-1 (fuentes core de fpdf2).
SUBS = {
    "—": "-", "–": "-", "…": "...",
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "✕": "x", "✦": "", "✎": "", "•": "-",
}

def san(s):
    for k, v in SUBS.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")


class Notas(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_y(10)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 6, san("The ATA Handbook - Notas de version"), align="R")
        self.ln(8)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 6, san("Pagina %d - documento vivo (staging)" % self.page_no()), align="C")


def build():
    pdf = Notas(format="A4")
    pdf.set_title("The ATA Handbook - Notas de version")
    pdf.set_author("Explora Atacama - F&B")
    pdf.set_auto_page_break(True, margin=18)
    pdf.set_margins(20, 18, 20)
    pdf.add_page()

    with open(MD, encoding="utf-8") as f:
        lines = f.read().split("\n")

    def para(text, gap=2.2):
        pdf.set_font("Helvetica", "", 10.5)
        pdf.set_text_color(*DARK)
        pdf.multi_cell(0, 5.4, san(text), markdown=True)
        pdf.ln(gap)

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            pdf.ln(1.6)
            continue
        if line.startswith("# "):
            pdf.set_font("Helvetica", "B", 21)
            pdf.set_text_color(*SIENNA)
            pdf.multi_cell(0, 9, san(line[2:]))
            pdf.ln(1)
        elif line.startswith("## "):
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 14)
            pdf.set_text_color(*GOLD)
            pdf.multi_cell(0, 7, san(line[3:]))
            y = pdf.get_y() + 0.5
            pdf.set_draw_color(*RULE)
            pdf.set_line_width(0.3)
            pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
            pdf.ln(3)
        elif line.startswith("### "):
            pdf.ln(1.5)
            pdf.set_font("Helvetica", "B", 11.5)
            pdf.set_text_color(*DARK)
            pdf.multi_cell(0, 6, san(line[4:]))
            pdf.ln(1.2)
        elif line.startswith("> "):
            pdf.set_font("Helvetica", "I", 10)
            pdf.set_text_color(*MUTED)
            pdf.multi_cell(0, 5.2, san(line[2:]))
            pdf.ln(2)
        elif line.startswith("    "):  # bloque de codigo / comando
            pdf.set_font("Courier", "", 9.5)
            pdf.set_text_color(*MUTED)
            pdf.multi_cell(0, 5, san(line.strip()))
            pdf.ln(1)
        elif line.lstrip().startswith("- "):
            indent = (len(line) - len(line.lstrip())) // 2
            txt = line.lstrip()[2:]
            pdf.set_font("Helvetica", "", 10.5)
            pdf.set_text_color(*DARK)
            x0 = pdf.l_margin + 4 + indent * 5
            pdf.set_x(x0)
            pdf.set_text_color(*GOLD)
            pdf.cell(4, 5.4, san("·"))  # midpoint, latin-1 safe
            pdf.set_text_color(*DARK)
            pdf.set_x(x0 + 4)
            pdf.multi_cell(0, 5.4, san(txt), markdown=True)
            pdf.ln(0.8)
        else:
            para(line)

    pdf.output(PDF)
    print("PDF generado:", PDF)


if __name__ == "__main__":
    build()
