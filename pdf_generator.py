"""Reusable premium Hero / Selva Motors PDF report builder."""
from __future__ import annotations

import html
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional
from zoneinfo import ZoneInfo

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

HERO_RED = colors.HexColor("#E31837")
INK = colors.HexColor("#111827")
SLATE = colors.HexColor("#475569")
PALE = colors.HexColor("#F4F6F8")
BORDER = colors.HexColor("#D9DEE5")
WHITE = colors.white

_FONT_NAME = "Helvetica"
_BOLD_FONT_NAME = "Helvetica-Bold"
_FONT_READY = False


def _register_font() -> None:
    global _FONT_NAME, _BOLD_FONT_NAME, _FONT_READY
    if _FONT_READY:
        return
    candidates = [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
    ]
    for regular_path, bold_path in candidates:
        if Path(regular_path).exists() and Path(bold_path).exists():
            try:
                pdfmetrics.registerFont(TTFont("SelvaSans", regular_path))
                pdfmetrics.registerFont(TTFont("SelvaSans-Bold", bold_path))
                _FONT_NAME, _BOLD_FONT_NAME = "SelvaSans", "SelvaSans-Bold"
                break
            except Exception:
                continue
    _FONT_READY = True


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def format_inr(value: Any) -> str:
    """Format rupees with Indian lakh/crore digit grouping and two decimals."""
    try:
        amount = float(str(value).replace(",", "").replace("₹", "").replace("Rs.", "").strip() or 0)
    except Exception:
        amount = 0.0
    sign = "-" if amount < 0 else ""
    integer_text, decimal_text = f"{abs(amount):.2f}".split(".")
    if len(integer_text) > 3:
        last_three = integer_text[-3:]
        remaining = integer_text[:-3]
        pairs = []
        while remaining:
            pairs.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        integer_text = ",".join(pairs + [last_three])
    prefix = "₹" if _FONT_NAME != "Helvetica" else "Rs. "
    return f"{prefix}{sign}{integer_text}.{decimal_text}"


def _currency_column(column: str) -> bool:
    text = column.lower()
    return any(term in text for term in ("amount", "revenue", "labour", "spare"))


def _format_cell(column: str, value: Any) -> str:
    text = _safe_text(value)
    if _currency_column(column) and text:
        return html.escape(format_inr(text))
    return html.escape(text).replace("\n", "<br/>")


def _find_asset(asset_name: str) -> Optional[Path]:
    candidates = [
        Path("assets") / asset_name,
        Path(__file__).resolve().parent / "assets" / asset_name,
    ]
    return next((p for p in candidates if p.exists()), None)


def _letterpad_watermark():
    path = _find_asset("selva_letterpad_bg.png")
    if not path:
        return None
    try:
        from PIL import Image
        image = Image.open(path).convert("RGBA")
        alpha = image.getchannel("A").point(lambda value: int(value * 0.055))
        image.putalpha(alpha)
        return ImageReader(image)
    except Exception:
        return None


class _HeroCanvas:
    """Page callback helper for a consistent header/footer on every page."""

    def __init__(self, generated_at: str, report_title: str, page_size=A4):
        self.generated_at = generated_at
        self.report_title = report_title
        self.page_size = page_size
        self.logo = _find_asset("hero_logo.png")
        self.watermark = _letterpad_watermark()

    def on_page(self, canvas, doc):
        canvas.saveState()
        width, height = self.page_size
        if self.watermark:
            try:
                canvas.drawImage(self.watermark, 0, 0, width=width, height=height, mask="auto", preserveAspectRatio=False)
            except Exception:
                pass

        # Branded red rule and logo.
        if self.logo:
            try:
                canvas.drawImage(str(self.logo), 15 * mm, height - 25 * mm, width=52 * mm, height=17 * mm,
                                 preserveAspectRatio=True, anchor="c", mask="auto")
            except Exception:
                pass
        canvas.setFillColor(INK)
        canvas.setFont(_BOLD_FONT_NAME, 8)
        canvas.drawRightString(width - 15 * mm, height - 14 * mm, "SELVA MOTORS ERP")
        canvas.setFillColor(HERO_RED)
        canvas.setStrokeColor(HERO_RED)
        canvas.setLineWidth(1.4)
        canvas.line(15 * mm, height - 28 * mm, width - 15 * mm, height - 28 * mm)

        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.5)
        canvas.line(15 * mm, 13 * mm, width - 15 * mm, 13 * mm)
        canvas.setFillColor(SLATE)
        canvas.setFont(_FONT_NAME, 7)
        canvas.drawString(15 * mm, 8.5 * mm, "SELVA MOTORS  |  Confidential business report")
        canvas.drawRightString(width - 15 * mm, 8.5 * mm, f"Page {doc.page}")
        canvas.restoreState()


def generate_professional_report_pdf(
    dataframe: pd.DataFrame,
    title: str,
    output_path: str | Path,
    *,
    metadata: Optional[Mapping[str, Any]] = None,
    kpis: Optional[Iterable[tuple[str, Any]]] = None,
    columns: Optional[list[str]] = None,
    report_kind: str = "service",
) -> str:
    """Render a consistent A4 report with wrapped tables and repeated headers."""
    _register_font()
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    safe_title = re.sub(r"[^A-Za-z0-9 _-]", "", title).strip() or "Selva Motors Report"
    metadata = dict(metadata or {})
    generated_at = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d-%m-%Y %I:%M:%S %p")

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "SelvaTitle", parent=styles["Title"], fontName=_BOLD_FONT_NAME, fontSize=17,
        leading=21, textColor=INK, alignment=TA_LEFT, spaceAfter=4,
    )
    meta_style = ParagraphStyle(
        "SelvaMeta", parent=styles["Normal"], fontName=_FONT_NAME, fontSize=8,
        leading=11, textColor=SLATE,
    )
    cell_style = ParagraphStyle(
        "SelvaCell", parent=styles["Normal"], fontName=_FONT_NAME, fontSize=7,
        leading=9, textColor=INK, wordWrap="CJK",
    )
    header_style = ParagraphStyle(
        "SelvaHeader", parent=cell_style, fontName=_BOLD_FONT_NAME, fontSize=7,
        leading=8, textColor=WHITE,
    )
    kpi_label_style = ParagraphStyle(
        "SelvaKpiLabel", parent=meta_style, fontName=_BOLD_FONT_NAME, fontSize=7,
        textColor=SLATE, alignment=TA_CENTER,
    )
    kpi_value_style = ParagraphStyle(
        "SelvaKpiValue", parent=meta_style, fontName=_BOLD_FONT_NAME, fontSize=12,
        leading=15, textColor=INK, alignment=TA_CENTER,
    )

    df = dataframe.copy() if dataframe is not None else pd.DataFrame()
    if report_kind == "daily_technician":
        # The daily technician PDF deliberately excludes Total Amount.
        df = df.drop(columns=["Total Amount"], errors="ignore")
    if columns:
        visible = [col for col in columns if col in df.columns]
        df = df[visible]
    page_size = landscape(A4) if len(df.columns) >= 8 else A4

    story = [Spacer(1, 2 * mm), Paragraph(html.escape(safe_title), title_style)]
    meta_parts = [f"<b>Generated:</b> {html.escape(generated_at)}"]
    for key, value in metadata.items():
        if value not in (None, ""):
            meta_parts.append(f"<b>{html.escape(str(key))}:</b> {html.escape(_safe_text(value))}")
    story.append(Paragraph("&nbsp;&nbsp; | &nbsp;&nbsp;".join(meta_parts), meta_style))
    story.append(Spacer(1, 5 * mm))

    kpi_items = list(kpis or [])
    if kpi_items:
        kpi_cells = []
        for label, value in kpi_items:
            if isinstance(value, (int, float)) and any(word in str(label).lower() for word in ("revenue", "amount", "labour", "spare")):
                display = format_inr(value)
            else:
                display = _safe_text(value)
            kpi_cells.append([
                Paragraph(html.escape(str(label)), kpi_label_style),
                Paragraph(html.escape(display), kpi_value_style),
            ])
        grid_rows = []
        for index in range(0, len(kpi_cells), 4):
            chunk = kpi_cells[index:index + 4]
            chunk += [[Paragraph("", kpi_label_style), Paragraph("", kpi_value_style)]] * (4 - len(chunk))
            grid_rows.append([
                Table([[cell[0]], [cell[1]]], colWidths=[(page_size[0] - 34 * mm) / 4 - 5 * mm])
                for cell in chunk
            ])
        kpi_table = Table(grid_rows, colWidths=[(page_size[0] - 30 * mm) / 4] * 4, hAlign="LEFT")
        kpi_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PALE),
            ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.extend([kpi_table, Spacer(1, 5 * mm)])

    story.append(Paragraph("Report Details", ParagraphStyle(
        "SelvaSection", parent=styles["Heading2"], fontName=_BOLD_FONT_NAME,
        fontSize=10, leading=13, textColor=HERO_RED, spaceAfter=3,
    )))

    if df.empty:
        story.append(Paragraph("No records matched the selected filters.", meta_style))
    else:
        headers = list(df.columns)
        available_width = page_size[0] - 30 * mm
        # Set practical relative widths: dates/amounts compact, descriptive text flexible.
        weights = []
        for column in headers:
            label = column.lower()
            if any(key in label for key in ("job card", "registration", "date", "time", "status", "role", "user id", "count")):
                weights.append(1.0)
            elif any(key in label for key in ("amount", "revenue", "labour", "spare")):
                weights.append(1.05)
            elif any(key in label for key in ("bike model", "technician", "name", "service type")):
                weights.append(1.45)
            else:
                weights.append(1.15)
        total_weight = sum(weights) or 1.0
        col_widths = [available_width * weight / total_weight for weight in weights]

        table_data = [[Paragraph(html.escape(str(head)), header_style) for head in headers]]
        for _, row in df.iterrows():
            table_data.append([
                Paragraph(_format_cell(column, row.get(column, "")), cell_style)
                for column in headers
            ])

        details = LongTable(
            table_data,
            colWidths=col_widths,
            repeatRows=1,
            splitByRow=1,
            hAlign="LEFT",
        )
        details.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), INK),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PALE]),
            ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(details)

    # Wide reports (eight or more columns) use landscape A4 for readable fields
    # without clipping or excessive wrapping. Daily technician reports stay portrait.
    page_painter = _HeroCanvas(generated_at, safe_title, page_size=page_size)
    doc = SimpleDocTemplate(
        str(output), pagesize=page_size,
        rightMargin=15 * mm, leftMargin=15 * mm,
        topMargin=34 * mm, bottomMargin=20 * mm,
        title=safe_title, author="SELVA MOTORS ERP",
    )
    doc.build(story, onFirstPage=page_painter.on_page, onLaterPages=page_painter.on_page)
    return str(output)


# Compatibility wrapper used by older code paths; new report pages call the
# professional generator directly and always supply a report_kind.
def simple_pdf(output_path, title, rows, subtitle="SELVA MOTORS"):
    frame = pd.DataFrame(rows[1:], columns=rows[0]) if rows else pd.DataFrame()
    return Path(generate_professional_report_pdf(frame, title, output_path, metadata={"Subtitle": subtitle}))
