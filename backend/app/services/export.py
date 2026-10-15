from __future__ import annotations

import csv
import io
from xml.sax.saxutils import escape

from app.models import Scan

COLUMNS = [
    "#", "medicine", "strength", "dose", "frequency", "duration", "timing",
    "notes", "status", "confidence", "catalogue name", "composition",
]

DISCLAIMER = (
    "Machine read from a prescription image and reviewed by the user. "
    "This is not a prescription. Check every item against the original."
)


def _rows(scan: Scan) -> list[list[str]]:
    rows = []
    for i, item in enumerate(scan.items, 1):
        rows.append([
            str(i),
            item.name,
            item.strength or "",
            item.dose or "",
            item.frequency or "",
            item.duration or "",
            item.timing or "",
            item.notes or "",
            item.status,
            f"{item.confidence:.2f}" if item.confidence is not None else "",
            item.medicine.name if item.medicine else "",
            (item.medicine.composition or "") if item.medicine else "",
        ])
    return rows


def to_csv(scan: Scan) -> bytes:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(COLUMNS)
    writer.writerows(_rows(scan))
    # BOM so Excel opens it as UTF-8 (½, µ and non-Latin names survive).
    return ("﻿" + out.getvalue()).encode("utf-8")


def to_pdf(scan: Scan) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4), leftMargin=16 * mm, rightMargin=16 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm, title=scan.title,
    )
    ink = colors.HexColor("#141413")
    muted = colors.HexColor("#6b6a65")
    title = ParagraphStyle("t", fontName="Times-Roman", fontSize=26, leading=30, textColor=ink)
    meta = ParagraphStyle("m", fontName="Helvetica", fontSize=9, leading=12, textColor=muted)
    cell = ParagraphStyle("c", fontName="Helvetica", fontSize=9, leading=11, textColor=ink)
    head = ParagraphStyle("h", parent=cell, fontName="Helvetica-Bold", textColor=muted)

    created = scan.created_at.strftime("%d %b %Y, %H:%M")
    story = [
        Paragraph(escape(scan.title), title),
        Spacer(1, 4),
        Paragraph(f"{created} &nbsp;&middot;&nbsp; read with {escape(scan.provider)} "
                  f"&nbsp;&middot;&nbsp; {len(scan.items)} items", meta),
        Spacer(1, 14),
    ]

    shown = ["#", "medicine", "strength", "dose", "frequency", "duration", "timing", "notes", "status"]
    idx = [COLUMNS.index(c) for c in shown]
    data = [[Paragraph(c.capitalize() if c != "#" else "#", head) for c in shown]]
    for row in _rows(scan):
        data.append([Paragraph(escape(row[i]), cell) for i in idx])
    if len(data) == 1:
        data.append([Paragraph("No items", cell)] + [""] * (len(shown) - 1))

    widths = [10 * mm, 62 * mm, 22 * mm, 24 * mm, 30 * mm, 22 * mm, 26 * mm, 40 * mm, 22 * mm]
    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, ink),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#e4e2db")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [table, Spacer(1, 18), Paragraph(DISCLAIMER, meta)]
    doc.build(story)
    return buf.getvalue()
