from __future__ import annotations
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from pathlib import Path

def simple_pdf(output_path, title, rows, subtitle="SELVA MOTORS"):
    doc = SimpleDocTemplate(str(output_path), pagesize=A4, rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    story = [Paragraph(f"<b>{title}</b>", styles["Title"]), Paragraph(subtitle, styles["Normal"]), Spacer(1, 12)]
    table = Table(rows, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#111827")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("BACKGROUND", (0,1), (-1,-1), colors.whitesmoke),
    ]))
    story.append(table)
    doc.build(story)
    return Path(output_path)
