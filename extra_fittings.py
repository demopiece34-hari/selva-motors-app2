"""SELVA MOTORS - EXTRA FITTINGS INVOICE module for an existing Streamlit app.

Import this module only on the dedicated page. It does not configure Streamlit,
connect to databases, or access Google Sheets. PDF bytes are created only when
an operator clicks Generate Invoice.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import secrets
from datetime import date, datetime
from html import escape
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import streamlit as st
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

DEALERSHIP_NAME = "SELVA MOTORS"
DEALERSHIP_ADDRESS = "Katchanam Road, Near Bypass, Kilvelur"
DEALERSHIP_PHONE_TEXT = "9842538709 / 9894120041 / 9442176514"
INDIA_TZ = ZoneInfo("Asia/Kolkata")
CATALOGUE_FILENAME = "vehicle_catalogue.json"
MANUAL_MODEL_OPTION = "Other / Enter manually"
LOGO_RELATIVE_PATH = Path("assets") / "hero_logo.png"
LOGO_PATH = Path(__file__).resolve().parent / LOGO_RELATIVE_PATH

MOTORCYCLE_FITTINGS = [
    "Number Plate", "Engine Card", "Hand Grip", "Tank Cover", "Seat Cover",
    "Brake Rubber", "Indicator Buzzer", "Sticker", "Helmet",
]
SCOOTER_FITTINGS = [
    "Number Plate", "Mat", "Footrest", "Grill Set – Front", "Grill Set – Back",
    "Grill Set – Mudguard", "Indicator Buzzer",
]

SERVICE_SCHEDULES = {
    "Motorcycle": [
        ("1st Free Service", "500–750 km", "60 Days"),
        ("2nd Free Service", "3,000–3,500 km", "160 Days"),
        ("3rd Free Service", "6,000–6,500 km", "260 Days"),
        ("4th Free Service", "9,000–9,500 km", "360 Days"),
    ],
    "Scooter": [
        ("1st Free Service", "500–750 km", "60 Days"),
        ("2nd Free Service", "3,000–3,500 km", "160 Days"),
        ("3rd Free Service", "6,000–6,500 km", "260 Days"),
        ("4th Free Service", "9,000–9,500 km", "360 Days"),
        ("5th Free Service", "12,000–12,500 km", "460 Days"),
    ],
}

RED = colors.HexColor("#C8102E")
DARK = colors.HexColor("#24262B")
GREY = colors.HexColor("#5B616B")
MID_GREY = colors.HexColor("#AEB4BC")
LIGHT_GREY = colors.HexColor("#DFE3E8")
PALE = colors.HexColor("#F7F8FA")
PALE_RED = colors.HexColor("#FFF5F6")
WHITE = colors.white


def _today_india() -> date:
    return datetime.now(INDIA_TZ).date()


def make_invoice_number() -> str:
    """Create a readable invoice reference with a timestamp and random suffix."""
    stamp = datetime.now(INDIA_TZ).strftime("%Y%m%d-%H%M%S")
    return f"SM-EFI-{stamp}-{secrets.token_hex(4).upper()}"


def _slug(value: str, fallback: str = "Invoice") -> str:
    value = re.sub(r"[^A-Za-z0-9-]+", "_", str(value or "").strip()).strip("_")
    value = re.sub(r"_+", "_", value)
    return (value[:72] or fallback).strip("_") or fallback


def build_pdf_filename(invoice_number: str, customer_name: str = "") -> str:
    """Build the requested invoice filename, based on its unique reference."""
    safe_invoice = _slug(invoice_number, "SM-EFI-UNKNOWN")
    return f"Selva_Motors_Extra_Fittings_Invoice_{safe_invoice}.pdf"


def normalize_indian_mobile(raw_phone: str) -> str | None:
    """Accept a 10-digit Indian mobile, optionally prefixed with +91 or 0."""
    digits = re.sub(r"\D", "", str(raw_phone or ""))
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) != 10 or digits[0] not in "6789":
        return None
    return digits


def format_phone_for_document(raw_phone: str) -> str:
    normalized = normalize_indian_mobile(raw_phone)
    if not normalized:
        return str(raw_phone or "Not provided").strip() or "Not provided"
    return f"+91 {normalized[:5]} {normalized[5:]}"


def format_inr(amount: float) -> str:
    """Format an amount with Indian digit grouping and two decimal places."""
    value = f"{float(amount):.2f}"
    integer, decimal = value.split(".")
    if len(integer) > 3:
        last_three, remaining = integer[-3:], integer[:-3]
        pairs: list[str] = []
        while remaining:
            pairs.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        integer = ",".join(pairs + [last_three])
    return f"₹{integer}.{decimal}"


def _signature(payload: dict[str, Any]) -> str:
    safe = dict(payload)
    if isinstance(safe.get("date"), date):
        safe["date"] = safe["date"].isoformat()
    encoded = json.dumps(safe, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _catalogue_path() -> Path:
    return Path(__file__).resolve().with_name(CATALOGUE_FILENAME)


def _load_catalogue() -> tuple[dict[str, list[dict[str, Any]]], str | None]:
    path = _catalogue_path()
    if not path.exists():
        return {"Motorcycle": [], "Scooter": []}, (
            f"{CATALOGUE_FILENAME} is missing. You can still enter a model manually."
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        categories = raw.get("categories") if isinstance(raw, dict) else None
        if not isinstance(categories, dict):
            raise ValueError("The 'categories' object is missing.")
        clean: dict[str, list[dict[str, Any]]] = {"Motorcycle": [], "Scooter": []}
        for category in clean:
            entries = categories.get(category, [])
            if not isinstance(entries, list):
                raise ValueError(f"'{category}' must contain a list of models.")
            seen: set[str] = set()
            for item in entries:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "")).strip()
                if not name or name in seen or name == MANUAL_MODEL_OPTION:
                    continue
                variants_raw = item.get("variants", [])
                variants = [str(v).strip() for v in variants_raw if str(v).strip()] if isinstance(variants_raw, list) else []
                clean[category].append({
                    "name": name,
                    "variants": variants,
                    "status": str(item.get("status", "owner-provided; verify")),
                    "source_url": str(item.get("source_url", "")).strip(),
                })
                seen.add(name)
        return clean, None
    except Exception as exc:
        return {"Motorcycle": [], "Scooter": []}, (
            f"Could not read {CATALOGUE_FILENAME}: {exc}. Enter the model manually."
        )


def _register_pdf_fonts() -> tuple[str, str, bool]:
    """Use a Unicode font when available so the rupee sign and punctuation print cleanly."""
    root = Path(__file__).resolve().parent
    font_pairs = [
        (root / "DejaVuSans.ttf", root / "DejaVuSans-Bold.ttf"),
        (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
        (Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf")),
    ]
    for regular_path, bold_path in font_pairs:
        if regular_path.is_file() and bold_path.is_file():
            try:
                if "SelvaInvoiceSans" not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont("SelvaInvoiceSans", str(regular_path)))
                if "SelvaInvoiceSans-Bold" not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont("SelvaInvoiceSans-Bold", str(bold_path)))
                return "SelvaInvoiceSans", "SelvaInvoiceSans-Bold", True
            except Exception:
                continue
    return "Helvetica", "Helvetica-Bold", False


def _styles(regular: str, bold: str) -> dict[str, ParagraphStyle]:
    return {
        "title": ParagraphStyle("InvTitle", fontName=bold, fontSize=13, leading=15, textColor=RED, alignment=TA_LEFT),
        "section": ParagraphStyle("InvSection", fontName=bold, fontSize=8.2, leading=10, textColor=RED, spaceBefore=1, spaceAfter=3),
        "label": ParagraphStyle("InvLabel", fontName=bold, fontSize=6.7, leading=8, textColor=GREY, splitLongWords=1),
        "value": ParagraphStyle("InvValue", fontName=regular, fontSize=7.5, leading=9.3, textColor=DARK, splitLongWords=1, wordWrap="CJK"),
        "small": ParagraphStyle("InvSmall", fontName=regular, fontSize=6.4, leading=8, textColor=GREY, splitLongWords=1),
        "body": ParagraphStyle("InvBody", fontName=regular, fontSize=7.2, leading=9.2, textColor=DARK, splitLongWords=1),
        "estimate_label": ParagraphStyle("InvEstimateLabel", fontName=bold, fontSize=8, leading=10, textColor=DARK),
        "estimate_value": ParagraphStyle("InvEstimateValue", fontName=bold, fontSize=12, leading=14, textColor=RED),
        "table_head": ParagraphStyle("InvTableHead", fontName=bold, fontSize=6.8, leading=8, textColor=WHITE, alignment=TA_LEFT),
        "table_cell": ParagraphStyle("InvTableCell", fontName=regular, fontSize=7, leading=8.5, textColor=DARK),
    }


def _safe_text(value: Any, empty: str = "Not provided") -> str:
    value = str(value or "").strip()
    return value if value else empty


class CheckboxItem(Flowable):
    """Vector checkbox that works without a special checkbox font."""
    def __init__(self, label: str, checked: bool, regular_font: str):
        super().__init__()
        self.label = label
        self.checked = bool(checked)
        self.regular_font = regular_font
        self.paragraph: Paragraph | None = None
        self.label_height = 0
        self.width = 0
        self.height = 14

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        style = ParagraphStyle("FitText", fontName=self.regular_font, fontSize=7.4, leading=9, textColor=DARK, splitLongWords=1)
        self.paragraph = Paragraph(escape(self.label), style)
        _, self.label_height = self.paragraph.wrap(max(1, availWidth - 18), availHeight)
        self.height = max(14, self.label_height + 2)
        return availWidth, self.height

    def draw(self):
        size = 7.5
        y = (self.height - size) / 2
        self.canv.setLineWidth(0.75)
        self.canv.setStrokeColor(RED if self.checked else GREY)
        self.canv.rect(1, y, size, size, stroke=1, fill=0)
        if self.checked:
            path = self.canv.beginPath()
            path.moveTo(2.2, y + 3.8)
            path.lineTo(3.5, y + 1.9)
            path.lineTo(7.0, y + 6.4)
            self.canv.setLineWidth(1.2)
            self.canv.setStrokeColor(RED)
            self.canv.drawPath(path, stroke=1, fill=0)
        if self.paragraph:
            self.paragraph.drawOn(self.canv, 13, (self.height - self.label_height) / 2)


def _draw_logo_placeholder(canvas, x: float, y: float, width: float, height: float) -> None:
    """Draw a neutral logo slot, never an imitation of the official brand logo."""
    canvas.saveState()
    canvas.setStrokeColor(LIGHT_GREY)
    canvas.setLineWidth(0.6)
    canvas.setDash(2, 2)
    canvas.rect(x, y, width, height, stroke=1, fill=0)
    canvas.setDash()
    canvas.setFillColor(GREY)
    canvas.setFont("Helvetica-Bold", 6.6)
    canvas.drawCentredString(x + width / 2, y + height / 2 + 1, "OFFICIAL HERO LOGO ASSET")
    canvas.setFont("Helvetica", 5.5)
    canvas.drawCentredString(x + width / 2, y + height / 2 - 7, "assets/hero_logo.png")
    canvas.restoreState()


class SignatureBox(Flowable):
    def __init__(self, label: str, regular_font: str, bold_font: str, height: float = 42):
        super().__init__()
        self.label, self.regular_font, self.bold_font = label, regular_font, bold_font
        self.height = height
        self.width = 0

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        return availWidth, self.height

    def draw(self):
        self.canv.setStrokeColor(MID_GREY)
        self.canv.setLineWidth(0.7)
        self.canv.line(5, 13, self.width - 5, 13)
        self.canv.setFont(self.bold_font, 6.8)
        self.canv.setFillColor(DARK)
        self.canv.drawCentredString(self.width / 2, 2, self.label)


def _section(text: str, styles: dict[str, ParagraphStyle]) -> Paragraph:
    return Paragraph(escape(text.upper()), styles["section"])


def _field_table(rows: list[list[tuple[str, str]]], usable_width: float, styles: dict[str, ParagraphStyle]) -> Table:
    """Build 2/4-column detail rows. A single field may occupy the full width."""
    data = []
    widths: list[float] | None = None
    for row in rows:
        if len(row) == 1:
            label, value = row[0]
            data.append([Paragraph(escape(label), styles["label"]), Paragraph(escape(value), styles["value"])])
            widths = [33 * mm, usable_width - 33 * mm]
        elif len(row) == 2:
            (label1, value1), (label2, value2) = row
            data.append([
                Paragraph(escape(label1), styles["label"]), Paragraph(escape(value1), styles["value"]),
                Paragraph(escape(label2), styles["label"]), Paragraph(escape(value2), styles["value"]),
            ])
            widths = [25 * mm, (usable_width - 50 * mm) / 2, 25 * mm, (usable_width - 50 * mm) / 2]
        else:
            raise ValueError("Detail table rows must contain one or two fields.")
    # Rows have either 2 or 4 columns; make separate tables to keep widths predictable.
    result = []
    for row in rows:
        if len(row) == 1:
            label, value = row[0]
            table = Table([[Paragraph(escape(label), styles["label"]), Paragraph(escape(value), styles["value"])]], colWidths=[33 * mm, usable_width - 33 * mm])
        else:
            (label1, value1), (label2, value2) = row
            table = Table([[
                Paragraph(escape(label1), styles["label"]), Paragraph(escape(value1), styles["value"]),
                Paragraph(escape(label2), styles["label"]), Paragraph(escape(value2), styles["value"]),
            ]], colWidths=[25 * mm, (usable_width - 50 * mm) / 2, 25 * mm, (usable_width - 50 * mm) / 2])
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, LIGHT_GREY),
            ("BACKGROUND", (0, 0), (0, -1), PALE),
            ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        result.append(table)
    return Table([[item] for item in result], colWidths=[usable_width], style=TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]))


def build_extra_fittings_pdf(payload: dict[str, Any]) -> bytes:
    """Generate a printer-friendly A4 PDF from a validated invoice snapshot."""
    customer_name = _safe_text(payload.get("customer_name"), "")
    normalized_phone = normalize_indian_mobile(str(payload.get("customer_phone", "")))
    category = str(payload.get("vehicle_category", "")).strip()
    if category not in SERVICE_SCHEDULES:
        raise ValueError("Vehicle category must be Motorcycle or Scooter.")
    model = _safe_text(payload.get("vehicle_model"), "")
    variant = _safe_text(payload.get("vehicle_variant"), "Not specified")
    invoice_number = _safe_text(payload.get("invoice_number"), "")
    if not customer_name:
        raise ValueError("Customer name is required.")
    if not normalized_phone:
        raise ValueError("Enter a valid 10-digit Indian mobile number.")
    if not model:
        raise ValueError("Vehicle model is required.")
    if not invoice_number:
        raise ValueError("Invoice number is required.")
    try:
        amount = float(payload.get("estimate_amount", 0))
    except (TypeError, ValueError):
        raise ValueError("Estimate amount must be a valid number.")
    if amount < 0:
        raise ValueError("Estimate amount cannot be negative.")
    selected_date = payload.get("date", _today_india())
    if isinstance(selected_date, str):
        try:
            selected_date = date.fromisoformat(selected_date)
        except ValueError:
            raise ValueError("Invoice date is invalid.")
    if not isinstance(selected_date, date):
        raise ValueError("Invoice date is invalid.")

    all_fittings = MOTORCYCLE_FITTINGS if category == "Motorcycle" else SCOOTER_FITTINGS
    submitted = payload.get("selected_fittings", [])
    if not isinstance(submitted, (list, tuple, set)):
        submitted = []
    selected_fittings = {str(value) for value in submitted}.intersection(all_fittings)

    regular, bold, has_unicode_rupee = _register_pdf_fonts()
    styles = _styles(regular, bold)
    buffer = io.BytesIO()
    page_width, page_height = A4
    left_margin = 13 * mm
    right_margin = 13 * mm
    usable_width = page_width - left_margin - right_margin

    def draw_chrome(canvas, doc):
        canvas.saveState()
        # Repeating clean header. A real logo is drawn only when the provided asset exists.
        top = page_height - 9 * mm
        logo_x = left_margin
        logo_y = top - 18 * mm
        logo_w = 36 * mm
        logo_h = 14 * mm
        if LOGO_PATH.is_file():
            try:
                canvas.drawImage(ImageReader(str(LOGO_PATH)), logo_x, logo_y, width=logo_w, height=logo_h,
                                 preserveAspectRatio=True, anchor="c", mask="auto")
            except Exception:
                _draw_logo_placeholder(canvas, logo_x, logo_y, logo_w, logo_h)
        else:
            _draw_logo_placeholder(canvas, logo_x, logo_y, logo_w, logo_h)
        right_x = page_width - right_margin
        canvas.setFillColor(DARK)
        canvas.setFont(bold, 15)
        canvas.drawRightString(right_x, top - 6 * mm, DEALERSHIP_NAME)
        canvas.setFillColor(GREY)
        canvas.setFont(regular, 7.2)
        canvas.drawRightString(right_x, top - 10 * mm, DEALERSHIP_ADDRESS)
        canvas.drawRightString(right_x, top - 14 * mm, DEALERSHIP_PHONE_TEXT.replace(" / ", "  |  "))
        canvas.setStrokeColor(RED)
        canvas.setLineWidth(1.4)
        canvas.line(left_margin, top - 21 * mm, right_x, top - 21 * mm)
        # Footer
        canvas.setStrokeColor(RED)
        canvas.setLineWidth(0.65)
        canvas.line(left_margin, 34, right_x, 34)
        canvas.setFillColor(GREY)
        canvas.setFont(regular, 6.4)
        canvas.drawString(left_margin, 22, f"SELVA MOTORS | {DEALERSHIP_ADDRESS}")
        canvas.setFont(regular, 6.2)
        canvas.drawString(left_margin, 10, DEALERSHIP_PHONE_TEXT.replace(" / ", "  |  "))
        canvas.drawRightString(right_x, 10, "Thank you for choosing Selva Motors.")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=left_margin, rightMargin=right_margin,
        topMargin=30 * mm, bottomMargin=15 * mm,
        title="SELVA MOTORS - EXTRA FITTINGS INVOICE", author=DEALERSHIP_NAME,
        subject="Extra fittings estimate and free service schedule",
    )

    # Invoice title and metadata strip.
    title_table = Table([[
        Paragraph("EXTRA FITTINGS INVOICE", styles["title"]),
        Paragraph(f"<b>Invoice No.</b> {escape(invoice_number)}<br/><b>Date</b> {selected_date.strftime('%d-%m-%Y')}",
                  ParagraphStyle("InvMeta", parent=styles["value"], alignment=TA_RIGHT, fontSize=7.2, leading=9.2)),
    ]], colWidths=[usable_width * 0.53, usable_width * 0.47])
    title_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE_RED), ("BOX", (0, 0), (-1, -1), 0.55, colors.HexColor("#E9B7BF")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    customer_rows = [
        [("Customer Name", customer_name), ("Customer Phone", format_phone_for_document(normalized_phone))],
    ]
    vehicle_rows = [
        [("Category", category), ("Model", model)],
        [("Variant", variant)],
        [("Chassis Number", _safe_text(payload.get("chassis_number")))],
        [("Engine Number", _safe_text(payload.get("engine_number")))],
    ]
    customer_table = _field_table(customer_rows, usable_width, styles)
    vehicle_table = _field_table(vehicle_rows, usable_width, styles)

    fitting_flowables = [CheckboxItem(item, item in selected_fittings, regular) for item in all_fittings]
    if len(fitting_flowables) % 2:
        fitting_flowables.append(Spacer(1, 14))
    fitting_rows = [fitting_flowables[i:i + 2] for i in range(0, len(fitting_flowables), 2)]
    checklist = Table(fitting_rows, colWidths=[usable_width / 2, usable_width / 2], hAlign="LEFT")
    checklist.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.55, LIGHT_GREY), ("INNERGRID", (0, 0), (-1, -1), 0.35, LIGHT_GREY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))

    amount_text = format_inr(amount) if has_unicode_rupee else f"INR {format_inr(amount)[1:]}"
    remarks = str(payload.get("remarks", "") or "").strip()
    remarks_para = Paragraph(f"<b>Remarks</b><br/>{escape(remarks)}" if remarks else "<b>Remarks</b><br/>Not provided", styles["body"])
    estimate_table = Table([[
        [Paragraph("ESTIMATED EXTRA FITTINGS AMOUNT", styles["estimate_label"]), Spacer(1, 3), Paragraph(escape(amount_text), styles["estimate_value"])],
        remarks_para,
    ]], colWidths=[usable_width * 0.48, usable_width * 0.52])
    estimate_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, LIGHT_GREY), ("INNERGRID", (0, 0), (-1, -1), 0.35, LIGHT_GREY),
        ("BACKGROUND", (0, 0), (0, 0), PALE_RED), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    schedule_data = [[
        Paragraph("SERVICE NO.", styles["table_head"]),
        Paragraph("RECOMMENDED KILOMETRES", styles["table_head"]),
        Paragraph("TIME INTERVAL", styles["table_head"]),
    ]]
    for service_name, kilometres, days in SERVICE_SCHEDULES[category]:
        schedule_data.append([
            Paragraph(escape(service_name), styles["table_cell"]),
            Paragraph(escape(kilometres), styles["table_cell"]),
            Paragraph(escape(days), styles["table_cell"]),
        ])
    schedule_table = Table(schedule_data, colWidths=[usable_width * 0.42, usable_width * 0.34, usable_width * 0.24], repeatRows=1, hAlign="LEFT")
    schedule_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), RED), ("BOX", (0, 0), (-1, -1), 0.55, LIGHT_GREY),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, LIGHT_GREY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, 0), 4), ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
        ("TOPPADDING", (0, 1), (-1, -1), 3), ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PALE]),
    ]))
    schedule_note = Paragraph(
        "Intervals shown are dealership-provided guidance for this document. Please follow the applicable official Hero owner's manual and confirm the service plan with the dealership.",
        styles["small"],
    )
    declaration = Paragraph(
        "The selected extra fittings and estimated amount have been recorded for reference. This is an estimate, not a final tax invoice or proof of payment. The final payable amount may differ after confirmation of actual fitment and charges.",
        styles["body"],
    )
    signature_table = Table([[
        SignatureBox("CUSTOMER SIGNATURE", regular, bold, 39),
        SignatureBox("FOR SELVA MOTORS - AUTHORIZED SIGNATURE", regular, bold, 39),
    ]], colWidths=[usable_width / 2, usable_width / 2])
    signature_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    story = [
        title_table, Spacer(1, 5), _section("A. Customer Details", styles), customer_table,
        Spacer(1, 4), _section("B. Vehicle Details", styles), vehicle_table,
        Spacer(1, 4), _section("C. Extra Fittings Selection", styles),
        Paragraph("Selected items are ticked; unselected applicable items remain unchecked.", styles["small"]),
        Spacer(1, 2), checklist, Spacer(1, 5), _section("D. Estimate", styles), estimate_table,
        Spacer(1, 5), KeepTogether([
            _section("E. HERO FREE SERVICE SCHEDULE", styles), schedule_table,
            Spacer(1, 2), schedule_note,
        ]),
        Spacer(1, 5), KeepTogether([
            _section("F. Customer Declaration", styles), declaration, Spacer(1, 4),
            _section("G. Signatures", styles), signature_table,
        ]),
    ]
    doc.build(story, onFirstPage=draw_chrome, onLaterPages=draw_chrome)
    return buffer.getvalue()


def _reset_form_state() -> None:
    """Clear this module's fields and generated PDF, leaving the host app untouched."""
    for key in list(st.session_state.keys()):
        if str(key).startswith("ef_") and key != "ef_reset_button":
            st.session_state.pop(key, None)


def _section_heading(text: str) -> None:
    st.markdown(
        f"<div style='margin:12px 0 7px;padding:8px 11px;border-left:4px solid #C8102E;"
        f"background:#FFF5F6;border-radius:4px;color:#24262B;font-weight:800;'>{escape(text)}</div>",
        unsafe_allow_html=True,
    )


def _form_payload(
    customer_name: str, raw_phone: str, category: str, model: str, variant: str,
    chassis: str, engine: str, invoice_date: date, invoice_number: str,
    amount: float, remarks: str, selected_fittings: list[str],
) -> dict[str, Any]:
    return {
        "customer_name": customer_name.strip(), "customer_phone": raw_phone.strip(),
        "vehicle_category": category, "vehicle_model": model.strip(), "vehicle_variant": variant.strip(),
        "chassis_number": chassis.strip(), "engine_number": engine.strip(), "date": invoice_date,
        "invoice_number": invoice_number.strip(), "estimate_amount": float(amount),
        "remarks": remarks.strip(), "selected_fittings": list(selected_fittings),
    }


def _validate_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    name = str(payload.get("customer_name", "")).strip()
    if len(name) < 2 or not any(character.isalpha() for character in name):
        errors.append("Enter a valid customer name (at least 2 characters, including a letter).")
    if not normalize_indian_mobile(str(payload.get("customer_phone", ""))):
        errors.append("Enter a valid Indian mobile number (10 digits, optionally with +91).")
    if payload.get("vehicle_category") not in SERVICE_SCHEDULES:
        errors.append("Select Motorcycle or Scooter.")
    if not str(payload.get("vehicle_model", "")).strip():
        errors.append("Vehicle Model is required. Select a model or enter it manually.")
    if not str(payload.get("invoice_number", "")).strip():
        errors.append("Invoice number is missing. Reset the form to create a new reference.")
    try:
        amount = float(payload.get("estimate_amount", 0))
        if amount < 0:
            errors.append("Estimate amount cannot be negative.")
    except (TypeError, ValueError):
        errors.append("Enter a valid estimate amount.")
    if not isinstance(payload.get("date"), date):
        errors.append("Select a valid invoice date.")
    return errors


def render_extra_fittings_page() -> None:
    """Render this module's Streamlit page when called from the existing app."""
    st.title("Extra Fittings Invoice")
    st.caption("SELVA MOTORS | HERO MOTOCORP | Printable A4 estimate with free service schedule")
    if not LOGO_PATH.is_file():
        st.info(f"Official logo not installed. Add an authorized logo image at `{LOGO_RELATIVE_PATH.as_posix()}` to show it in the PDF. No substitute logo is drawn.")
    try:
        catalogue, warning = _load_catalogue()
    except Exception as exc:
        catalogue, warning = {"Motorcycle": [], "Scooter": []}, str(exc)
    if warning:
        st.warning(warning)
    st.caption("The model catalogue is configurable. Confirm the exact model and variant against the vehicle documents; manual entry is available.")

    if "ef_invoice_number" not in st.session_state:
        st.session_state["ef_invoice_number"] = make_invoice_number()

    _section_heading("1. Customer Details")
    name_col, phone_col = st.columns(2)
    with name_col:
        customer_name = st.text_input("Customer Name *", key="ef_customer_name", placeholder="Enter customer's full name")
    with phone_col:
        raw_phone = st.text_input("Customer Phone Number *", key="ef_customer_phone", placeholder="10-digit Indian mobile number")

    _section_heading("2. Vehicle Details")
    category_col, date_col = st.columns(2)
    with category_col:
        category = st.selectbox("Vehicle Category *", ["Motorcycle", "Scooter"], key="ef_category")
    with date_col:
        invoice_date = st.date_input("Invoice Date", value=_today_india(), key="ef_invoice_date", format="DD-MM-YYYY")
    inv_col, chassis_col, engine_col = st.columns([1.25, 1, 1])
    with inv_col:
        st.text_input("Invoice Number (auto-generated)", key="ef_invoice_number", disabled=True, help="Reset the form to create a new unique invoice reference.")
    with chassis_col:
        chassis = st.text_input("Chassis Number", key="ef_chassis", placeholder="Enter manually if available")
    with engine_col:
        engine = st.text_input("Engine Number", key="ef_engine", placeholder="Enter manually if available")

    models = catalogue.get(category, [])
    model_options = [str(item.get("name", "")).strip() for item in models if str(item.get("name", "")).strip()]
    model_options.append(MANUAL_MODEL_OPTION)
    model_key = f"ef_model_{category.lower()}"
    if st.session_state.get(model_key) not in model_options:
        st.session_state[model_key] = model_options[0]
    selected_model_option = st.selectbox("Hero Vehicle Model *", model_options, key=model_key)
    if selected_model_option == MANUAL_MODEL_OPTION:
        model = st.text_input("Enter Vehicle Model *", key=f"ef_manual_model_{category.lower()}", placeholder="As shown in vehicle documents").strip()
        variants: list[str] = []
    else:
        model = selected_model_option
        record = next((item for item in models if item.get("name") == selected_model_option), {})
        variants = record.get("variants", []) if isinstance(record.get("variants"), list) else []

    if variants and selected_model_option != MANUAL_MODEL_OPTION:
        options = ["Not specified"] + variants + [MANUAL_MODEL_OPTION]
        variant_key = f"ef_variant_{category.lower()}_{_slug(model, 'model').lower()}"
        if st.session_state.get(variant_key) not in options:
            st.session_state[variant_key] = options[0]
        chosen_variant = st.selectbox("Vehicle Variant", options, key=variant_key)
        if chosen_variant == MANUAL_MODEL_OPTION:
            variant = st.text_input("Enter Vehicle Variant", key=f"ef_manual_variant_{category.lower()}_{_slug(model, 'model').lower()}").strip()
        elif chosen_variant == "Not specified":
            variant = ""
        else:
            variant = chosen_variant
    else:
        variant = st.text_input("Vehicle Variant (manual entry)", key=f"ef_variant_manual_{category.lower()}_{_slug(model or 'model', 'model').lower()}", placeholder="Enter exact variant if available").strip()

    _section_heading("3. Extra Fittings Selection")
    available_fittings = MOTORCYCLE_FITTINGS if category == "Motorcycle" else SCOOTER_FITTINGS
    selected_fittings: list[str] = []
    left_col, right_col = st.columns(2, gap="medium")
    for index, fitting in enumerate(available_fittings):
        with (left_col if index % 2 == 0 else right_col):
            key = f"ef_fit_{category.lower()}_{_slug(fitting, 'item').lower()}"
            if st.checkbox(fitting, key=key):
                selected_fittings.append(fitting)
    st.caption(f"Selected: {len(selected_fittings)} of {len(available_fittings)} applicable fittings. Only the selected category is included in the PDF.")

    _section_heading("4. Estimate Amount")
    amt_col, remarks_col = st.columns([1, 1.3])
    with amt_col:
        amount = st.number_input("Estimated Extra Fittings Amount (₹)", min_value=0.0, value=0.0, step=100.0, format="%.2f", key="ef_estimate")
        st.caption(f"Estimate preview: {format_inr(amount)}. This is not a final tax invoice amount.")
    with remarks_col:
        remarks = st.text_area("Optional Remarks", key="ef_remarks", height=85, placeholder="Additional note for customer/dealership record")

    _section_heading("5. Free Service Schedule Preview")
    st.markdown("**HERO FREE SERVICE SCHEDULE**")
    schedule = SERVICE_SCHEDULES[category]
    st.table([{"Service No.": row[0], "Recommended Kilometres": row[1], "Time Interval": row[2]} for row in schedule])
    st.caption("Intervals are provided by the dealership for this form. Follow the applicable official Hero owner's manual and dealership guidance.")

    current_payload = _form_payload(
        customer_name, raw_phone, category, model, variant, chassis, engine,
        invoice_date, st.session_state["ef_invoice_number"], amount, remarks, selected_fittings,
    )
    current_signature = _signature(current_payload)
    saved_signature = st.session_state.get("ef_pdf_signature")
    if saved_signature and saved_signature != current_signature:
        for key in ("ef_pdf_bytes", "ef_pdf_filename", "ef_pdf_signature"):
            st.session_state.pop(key, None)

    _section_heading("6. Generate Invoice")
    gen_col, reset_col = st.columns([1.4, 1])
    with gen_col:
        generate_clicked = st.button("Generate Invoice", type="primary", use_container_width=True, key="ef_generate_invoice")
    with reset_col:
        st.button("Reset Form / New Invoice", use_container_width=True, key="ef_reset_button", on_click=_reset_form_state)

    if generate_clicked:
        errors = _validate_payload(current_payload)
        if errors:
            for key in ("ef_pdf_bytes", "ef_pdf_filename", "ef_pdf_signature"):
                st.session_state.pop(key, None)
            for message in errors:
                st.error(message)
        else:
            current_payload["customer_phone"] = normalize_indian_mobile(current_payload["customer_phone"]) or current_payload["customer_phone"]
            try:
                pdf_bytes = build_extra_fittings_pdf(current_payload)
                filename = build_pdf_filename(current_payload["invoice_number"], current_payload["customer_name"])
                st.session_state["ef_pdf_bytes"] = pdf_bytes
                st.session_state["ef_pdf_filename"] = filename
                st.session_state["ef_pdf_signature"] = current_signature
                st.success("EXTRA FITTINGS INVOICE generated successfully. Review the preview details and download below.")
            except Exception as exc:
                for key in ("ef_pdf_bytes", "ef_pdf_filename", "ef_pdf_signature"):
                    st.session_state.pop(key, None)
                st.error(f"Invoice PDF generation failed: {exc}")

    saved_pdf = st.session_state.get("ef_pdf_bytes")
    saved_filename = st.session_state.get("ef_pdf_filename")
    if saved_pdf and st.session_state.get("ef_pdf_signature") == current_signature:
        st.markdown("**EXTRA FITTINGS INVOICE - PDF Preview / Download**")
        st.caption(f"Ready file: {saved_filename}")
        st.download_button("Download EXTRA FITTINGS INVOICE PDF", data=saved_pdf, file_name=saved_filename, mime="application/pdf", use_container_width=True, key="ef_download_invoice_pdf")
    elif st.session_state.get("ef_pdf_signature"):
        st.info("The form changed after the last PDF was generated. Press Generate Invoice again to create a PDF with the latest values.")
