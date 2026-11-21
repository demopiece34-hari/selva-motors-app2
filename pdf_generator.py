"""Reusable branded SELVA MOTORS PDF report builder (ReportLab)."""
from __future__ import annotations

import html
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence
from zoneinfo import ZoneInfo

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    KeepTogether,
    LongTable,
    PageBreak,
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
_TAMIL_FONT_READY = False


def _register_font() -> None:
    """Register a broad Latin/rupee font plus Tamil fallback for mixed-language reports."""
    global _FONT_NAME, _BOLD_FONT_NAME, _FONT_READY, _TAMIL_FONT_READY
    if _FONT_READY and _TAMIL_FONT_READY:
        return

    latin_candidates = [
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ),
        (
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ),
    ]
    for regular_path, bold_path in latin_candidates:
        if Path(regular_path).exists() and Path(bold_path).exists():
            try:
                pdfmetrics.registerFont(TTFont("SelvaSans", regular_path))
                pdfmetrics.registerFont(TTFont("SelvaSans-Bold", bold_path))
                _FONT_NAME, _BOLD_FONT_NAME = "SelvaSans", "SelvaSans-Bold"
                break
            except Exception:
                continue
    _FONT_READY = True

    tamil_candidates = [
        (
            "/usr/share/fonts/truetype/noto/NotoSansTamil-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansTamil-Bold.ttf",
        ),
        (
            "/usr/share/fonts/opentype/noto/NotoSansTamil-Regular.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansTamil-Bold.ttf",
        ),
    ]
    for regular_path, bold_path in tamil_candidates:
        if Path(regular_path).exists() and Path(bold_path).exists():
            try:
                pdfmetrics.registerFont(TTFont("SelvaTamil", regular_path))
                pdfmetrics.registerFont(TTFont("SelvaTamil-Bold", bold_path))
                _TAMIL_FONT_READY = True
                break
            except Exception:
                continue
    if not _TAMIL_FONT_READY:
        _TAMIL_FONT_READY = True  # Do not repeatedly scan paths; primary font remains the safe fallback.


def _pdf_text(value: Any) -> str:
    """Escape text and switch Tamil codepoints to the embedded Tamil font when installed."""
    escaped = html.escape(_safe_text(value))
    if "SelvaTamil" in pdfmetrics.getRegisteredFontNames():
        escaped = re.sub(r"([\u0B80-\u0BFF]+)", r'<font name="SelvaTamil">\1</font>', escaped)
    return escaped


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
    """Format rupees with Indian lakh/crore grouping and two decimals."""
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


def _is_currency_column(column: str) -> bool:
    text = str(column).casefold()
    terms = (
        "amount", "revenue", "labour", "spare", "oil", "sales", "collection",
        "expense", "salary", "balance", "gross", "net remaining", "total service",
    )
    return any(term in text for term in terms)


def _format_cell(column: str, value: Any) -> str:
    text = _safe_text(value)
    if text and _is_currency_column(column):
        try:
            return _pdf_text(format_inr(text))
        except Exception:
            pass
    return _pdf_text(text).replace("\n", "<br/>")


def _find_asset(asset_name: str) -> Optional[Path]:
    candidates = [
        Path("assets") / asset_name,
        Path(__file__).resolve().parent / "assets" / asset_name,
    ]
    return next((path for path in candidates if path.exists()), None)


class _HeroPagePainter:
    """Draw the approved Hero logo and SELVA MOTORS identity on each page."""

    def __init__(self, generated_at: str, page_size, report_title: str, period_text: str = ""):
        self.generated_at = generated_at
        self.page_size = page_size
        self.report_title = report_title
        self.period_text = period_text
        self.logo = _find_asset("hero_logo.png")

    def draw(self, pdf_canvas, page_number: int, total_pages: int) -> None:
        width, height = self.page_size
        pdf_canvas.saveState()

        # Header: Hero logo left, business identity right.
        if self.logo:
            try:
                pdf_canvas.drawImage(
                    str(self.logo), 15 * mm, height - 22 * mm,
                    width=48 * mm, height=16 * mm,
                    preserveAspectRatio=True, anchor="c", mask="auto",
                )
            except Exception:
                pass

        pdf_canvas.setFillColor(INK)
        pdf_canvas.setFont(_BOLD_FONT_NAME, 14)
        pdf_canvas.drawRightString(width - 15 * mm, height - 13 * mm, "SELVA MOTORS")
        pdf_canvas.setFillColor(SLATE)
        pdf_canvas.setFont(_FONT_NAME, 8)
        pdf_canvas.drawRightString(width - 15 * mm, height - 18 * mm, "Near Bypass, Kilvelur")

        title_style = ParagraphStyle(
            "SelvaRunningHeaderTitle", fontName=_BOLD_FONT_NAME, fontSize=8.5,
            leading=10, textColor=INK, alignment=TA_LEFT,
        )
        title_paragraph = Paragraph(_pdf_text(self.report_title), title_style)
        title_paragraph.wrapOn(pdf_canvas, width - 30 * mm, 8 * mm)
        title_paragraph.drawOn(pdf_canvas, 15 * mm, height - 30 * mm)
        if self.period_text:
            pdf_canvas.setFillColor(SLATE)
            pdf_canvas.setFont(_FONT_NAME, 7)
            pdf_canvas.drawString(15 * mm, height - 34 * mm, self.period_text[:100])

        pdf_canvas.setStrokeColor(HERO_RED)
        pdf_canvas.setLineWidth(1.5)
        pdf_canvas.line(15 * mm, height - 36 * mm, width - 15 * mm, height - 36 * mm)

        # Footer: generation timestamp and actual total page count.
        pdf_canvas.setStrokeColor(BORDER)
        pdf_canvas.setLineWidth(0.55)
        pdf_canvas.line(15 * mm, 14 * mm, width - 15 * mm, 14 * mm)
        pdf_canvas.setFillColor(SLATE)
        pdf_canvas.setFont(_FONT_NAME, 7)
        pdf_canvas.drawString(15 * mm, 9 * mm, f"SELVA MOTORS  |  Generated: {self.generated_at}")
        pdf_canvas.drawRightString(width - 15 * mm, 9 * mm, f"Page {page_number} of {total_pages}")
        pdf_canvas.restoreState()


class _NumberedCanvas(rl_canvas.Canvas):
    """Canvas that waits until the total page count is known before painting footers."""

    def __init__(self, *args, page_painter: _HeroPagePainter, **kwargs):
        self._page_painter = page_painter
        self._saved_page_states = []
        super().__init__(*args, **kwargs)

    def showPage(self):  # noqa: N802 - ReportLab API
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            page_number = self._pageNumber
            self._page_painter.draw(self, page_number, total_pages)
            super().showPage()
        super().save()


def _normalize_sections(
    dataframe: Optional[pd.DataFrame],
    sections: Optional[Iterable[tuple[str, pd.DataFrame]]],
) -> list[tuple[str, pd.DataFrame]]:
    normalized: list[tuple[str, pd.DataFrame]] = []
    if sections is not None:
        for title, frame in sections:
            safe_frame = frame.copy() if isinstance(frame, pd.DataFrame) else pd.DataFrame(frame or [])
            normalized.append((str(title or "Report Details"), safe_frame))
    elif isinstance(dataframe, pd.DataFrame):
        normalized.append(("Report Details", dataframe.copy()))
    elif dataframe is not None:
        normalized.append(("Report Details", pd.DataFrame(dataframe)))
    else:
        normalized.append(("Report Details", pd.DataFrame()))
    return normalized or [("Report Details", pd.DataFrame())]


def generate_professional_report_pdf(
    dataframe: Optional[pd.DataFrame],
    title: str,
    output_path: str | Path,
    *,
    metadata: Optional[Mapping[str, Any]] = None,
    kpis: Optional[Iterable[tuple[str, Any]]] = None,
    columns: Optional[list[str]] = None,
    report_kind: str = "service",
    sections: Optional[Iterable[tuple[str, pd.DataFrame]]] = None,
) -> str:
    """Create a branded, paginated A4 PDF with repeated table headers."""
    _register_font()
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    safe_title = re.sub(r"[\r\n]+", " ", _safe_text(title)) or "SELVA MOTORS Report"
    metadata = dict(metadata or {})
    generated_at = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d-%m-%Y %I:%M:%S %p")

    report_sections = _normalize_sections(dataframe, sections)
    prepared_sections: list[tuple[str, pd.DataFrame]] = []
    for section_title, frame in report_sections:
        df = frame.copy()
        if report_kind == "daily_technician":
            df = df.drop(columns=["Total Amount"], errors="ignore")
        if section_title == "Report Details" and columns:
            visible = [col for col in columns if col in df.columns]
            df = df[visible]
        prepared_sections.append((section_title, df))

    max_columns = max((len(frame.columns) for _, frame in prepared_sections), default=0)
    page_size = landscape(A4) if max_columns >= 8 else A4
    page_width = page_size[0]

    styles = getSampleStyleSheet()
    meta_style = ParagraphStyle(
        "SelvaMeta", parent=styles["Normal"], fontName=_FONT_NAME,
        fontSize=7.5, leading=10, textColor=SLATE,
    )
    section_style = ParagraphStyle(
        "SelvaSection", parent=styles["Heading2"], fontName=_BOLD_FONT_NAME,
        fontSize=9.5, leading=12, textColor=HERO_RED, spaceBefore=5,
        spaceAfter=4, keepWithNext=True,
    )
    cell_style = ParagraphStyle(
        "SelvaCell", parent=styles["Normal"], fontName=_FONT_NAME,
        fontSize=6.7, leading=8.5, textColor=INK, wordWrap="CJK",
    )
    header_style = ParagraphStyle(
        "SelvaHeader", parent=cell_style, fontName=_BOLD_FONT_NAME,
        fontSize=6.5, leading=8, textColor=WHITE,
    )
    kpi_label_style = ParagraphStyle(
        "SelvaKpiLabel", parent=meta_style, fontName=_BOLD_FONT_NAME,
        fontSize=7, leading=8.5, textColor=SLATE, alignment=TA_CENTER,
    )
    kpi_value_style = ParagraphStyle(
        "SelvaKpiValue", parent=meta_style, fontName=_BOLD_FONT_NAME,
        fontSize=11.5, leading=14, textColor=INK, alignment=TA_CENTER,
    )

    story = [Spacer(1, 1 * mm)]
    meta_parts = []
    for key, value in metadata.items():
        if value not in (None, ""):
            meta_parts.append(f"<b>{_pdf_text(key)}:</b> {_pdf_text(value)}")
    meta_parts.append(f"<b>Report Generated:</b> {html.escape(generated_at)}")
    story.append(Paragraph("&nbsp;&nbsp; | &nbsp;&nbsp;".join(meta_parts), meta_style))
    story.append(Spacer(1, 4 * mm))

    kpi_items = list(kpis or [])
    if kpi_items:
        story.append(Paragraph("Summary at a Glance", section_style))
        grid_rows = []
        for offset in range(0, len(kpi_items), 4):
            row_items = kpi_items[offset:offset + 4]
            cells = []
            for label, value in row_items:
                is_money = any(word in str(label).casefold() for word in (
                    "amount", "sales", "labour", "spare", "oil", "collection",
                    "expense", "salary", "balance", "revenue", "gross", "net",
                ))
                if is_money:
                    display = format_inr(value)
                elif isinstance(value, (int, float)):
                    display = f"{value:,.2f}" if isinstance(value, float) and not float(value).is_integer() else f"{int(value):,}"
                else:
                    display = _safe_text(value)
                cells.append([
                    Paragraph(_pdf_text(label), kpi_label_style),
                    Paragraph(_pdf_text(display), kpi_value_style),
                ])
            while len(cells) < 4:
                cells.append([Paragraph("", kpi_label_style), Paragraph("", kpi_value_style)])
            grid_rows.append([
                Table([[item[0]], [item[1]]], colWidths=[(page_width - 30 * mm) / 4 - 3 * mm])
                for item in cells
            ])
        kpi_table = Table(grid_rows, colWidths=[(page_width - 30 * mm) / 4] * 4, hAlign="LEFT")
        kpi_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PALE),
            ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.extend([kpi_table, Spacer(1, 4 * mm)])

    usable_width = page_width - 30 * mm
    for section_title, frame in prepared_sections:
        story.append(Paragraph(_pdf_text(section_title), section_style))
        if frame.empty:
            story.append(Paragraph("No records matched the selected filters.", meta_style))
            story.append(Spacer(1, 2 * mm))
            continue

        headers = [str(column) for column in frame.columns]
        weights = []
        for column in headers:
            label = column.casefold()
            if any(key in label for key in ("job card", "registration", "date", "time", "status", "count", "quantity")):
                weights.append(1.0)
            elif _is_currency_column(label):
                weights.append(1.05)
            elif any(key in label for key in ("technician", "customer", "description", "service type", "bike model", "vehicle")):
                weights.append(1.55)
            else:
                weights.append(1.2)
        total_weight = sum(weights) or 1.0
        col_widths = [usable_width * weight / total_weight for weight in weights]

        table_data = [[Paragraph(_pdf_text(header), header_style) for header in headers]]
        for _, row in frame.iterrows():
            table_data.append([
                Paragraph(_format_cell(column, row.get(column, "")), cell_style)
                for column in headers
            ])

        detail_table = LongTable(
            table_data,
            colWidths=col_widths,
            repeatRows=1,
            splitByRow=1,
            hAlign="LEFT",
        )
        detail_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), INK),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PALE]),
            ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(detail_table)
        story.append(Spacer(1, 3 * mm))

    period_text = next((f"{key}: {_safe_text(value)}" for key, value in metadata.items() if str(key).casefold() in {"report period", "report date", "month"} and value not in (None, "")), "")
    page_painter = _HeroPagePainter(generated_at, page_size=page_size, report_title=safe_title, period_text=period_text)
    doc = SimpleDocTemplate(
        str(output), pagesize=page_size,
        rightMargin=15 * mm, leftMargin=15 * mm,
        topMargin=40 * mm, bottomMargin=20 * mm,
        title=safe_title, author="SELVA MOTORS",
    )

    def canvas_factory(*args, **kwargs):
        return _NumberedCanvas(*args, page_painter=page_painter, **kwargs)

    doc.build(story, canvasmaker=canvas_factory)
    return str(output)


def simple_pdf(output_path, title, rows, subtitle="SELVA MOTORS"):
    """Compatibility wrapper retained for existing non-report callers."""
    frame = pd.DataFrame(rows[1:], columns=rows[0]) if rows else pd.DataFrame()
    return Path(generate_professional_report_pdf(
        frame, title, output_path, metadata={"Subtitle": subtitle},
    ))
