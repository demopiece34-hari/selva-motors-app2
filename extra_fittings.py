"""SELVA MOTORS - Extra Fittings Mark Sheet Generator.

This module is designed to be imported lazily from an existing Streamlit app.
It does not call st.set_page_config(), connect to a database, read Google Sheets,
or generate a PDF until the user opens the page and clicks Generate PDF.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
from datetime import date, datetime
from html import escape
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import streamlit as st

# ReportLab is already included in the supplied requirements.txt.
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
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

MOTORCYCLE_FITTINGS = [
    "Number Plate",
    "Engine Card",
    "Hand Grip",
    "Tank Cover",
    "Seat Cover",
    "Brake Rubber",
    "Indicator Buzzer",
    "Sticker",
    "Helmet",
]

SCOOTER_FITTINGS = [
    "Number Plate",
    "Mat",
    "Footrest",
    "Grill Set – Front",
    "Grill Set – Back",
    "Grill Set – Mudguard",
    "Indicator Buzzer",
]

RED = colors.HexColor("#C8102E")
DARK = colors.HexColor("#22252A")
GREY = colors.HexColor("#5B616B")
LIGHT_GREY = colors.HexColor("#E2E5E9")
PALE = colors.HexColor("#F7F8FA")
PALE_RED = colors.HexColor("#FFF5F6")
WHITE = colors.white


# ---------- Small, independently testable helpers ----------
def _today_india() -> date:
    return datetime.now(INDIA_TZ).date()


def _slug(value: str, fallback: str = "Customer") -> str:
    """Create a safe, readable filename segment without path characters."""
    value = str(value or "").strip()
    value = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    value = re.sub(r"_+", "_", value)
    return (value[:60] or fallback).strip("_") or fallback


def build_pdf_filename(customer_name: str, selected_date: date | str) -> str:
    """Return the requested PDF filename in a filesystem-safe form."""
    if isinstance(selected_date, date):
        date_text = selected_date.strftime("%Y-%m-%d")
    else:
        raw_date = str(selected_date or "").strip()
        try:
            date_text = date.fromisoformat(raw_date).strftime("%Y-%m-%d")
        except ValueError:
            date_text = _today_india().strftime("%Y-%m-%d")
    return f"Selva_Motors_Extra_Fittings_{_slug(customer_name)}_{date_text}.pdf"


def normalize_indian_mobile(raw_phone: str) -> str | None:
    """Accept a 10-digit Indian mobile, optionally prefixed by +91 or 0."""
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


def _signature(payload: dict[str, Any]) -> str:
    """Fingerprint the exact visible form values to avoid stale PDF downloads."""
    safe_payload = dict(payload)
    if isinstance(safe_payload.get("date"), date):
        safe_payload["date"] = safe_payload["date"].isoformat()
    serialised = json.dumps(safe_payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


def _catalogue_path() -> Path:
    return Path(__file__).resolve().with_name(CATALOGUE_FILENAME)


def _load_catalogue() -> tuple[dict[str, list[dict[str, Any]]], str | None]:
    """Load catalogue on page access only; malformed/missing files allow manual entry."""
    path = _catalogue_path()
    if not path.exists():
        return {"Motorcycle": [], "Scooter": []}, (
            f"Vehicle catalogue file not found ({CATALOGUE_FILENAME}). "
            "You can still use 'Other / Enter manually' for the model and variant."
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
                variants = (
                    [str(v).strip() for v in variants_raw if str(v).strip()]
                    if isinstance(variants_raw, list)
                    else []
                )
                clean[category].append(
                    {
                        "name": name,
                        "variants": variants,
                        "status": str(item.get("status", "configurable")),
                        "source_url": str(item.get("source_url", "")).strip(),
                    }
                )
                seen.add(name)
        return clean, None
    except Exception as exc:
        return {"Motorcycle": [], "Scooter": []}, (
            f"Vehicle catalogue could not be read ({exc}). "
            "You can still use 'Other / Enter manually' for the model and variant."
        )


def _register_pdf_fonts() -> tuple[str, str, bool]:
    """Use DejaVu Sans when installed for ₹; fall back safely to Helvetica/INR."""
    fonts_to_try = [
        (
            Path(__file__).resolve().with_name("DejaVuSans.ttf"),
            Path(__file__).resolve().with_name("DejaVuSans-Bold.ttf"),
        ),
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ),
        (
            Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
        ),
    ]
    for regular_path, bold_path in fonts_to_try:
        if regular_path.exists() and bold_path.exists():
            try:
                if "SelvaDejaVu" not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont("SelvaDejaVu", str(regular_path)))
                if "SelvaDejaVu-Bold" not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont("SelvaDejaVu-Bold", str(bold_path)))
                return "SelvaDejaVu", "SelvaDejaVu-Bold", True
            except Exception:
                pass
    return "Helvetica", "Helvetica-Bold", False


class CheckboxItem(Flowable):
    """Vector checkbox + wrapped fitting name; does not depend on Unicode glyphs."""

    def __init__(self, label: str, checked: bool, regular_font: str):
        super().__init__()
        self.label = label
        self.checked = bool(checked)
        self.regular_font = regular_font
        self.paragraph = None
        self.label_height = 0
        self.width = 0
        self.height = 14

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        text_style = ParagraphStyle(
            "FittingItemText",
            fontName=self.regular_font,
            fontSize=8.2,
            leading=10,
            textColor=DARK,
            splitLongWords=1,
        )
        self.paragraph = Paragraph(escape(self.label), text_style)
        _, self.label_height = self.paragraph.wrap(max(1, availWidth - 20), availHeight)
        self.height = max(15, self.label_height + 2)
        return availWidth, self.height

    def draw(self):
        box_size = 8.5
        box_x = 1
        box_y = (self.height - box_size) / 2
        self.canv.setLineWidth(0.8)
        self.canv.setStrokeColor(RED if self.checked else GREY)
        self.canv.rect(box_x, box_y, box_size, box_size, stroke=1, fill=0)
        if self.checked:
            self.canv.setStrokeColor(RED)
            self.canv.setLineWidth(1.4)
            path = self.canv.beginPath()
            path.moveTo(box_x + 1.5, box_y + 4.1)
            path.lineTo(box_x + 3.4, box_y + 1.7)
            path.lineTo(box_x + 7.2, box_y + 7.1)
            self.canv.drawPath(path, stroke=1, fill=0)
        if self.paragraph:
            self.paragraph.drawOn(
                self.canv,
                15,
                (self.height - self.label_height) / 2,
            )


class SignatureBox(Flowable):
    """Draw a wide handwriting area and a signature caption."""

    def __init__(self, label: str, regular_font: str, bold_font: str):
        super().__init__()
        self.label = label
        self.regular_font = regular_font
        self.bold_font = bold_font
        self.width = 0
        self.height = 104

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        return availWidth, self.height

    def draw(self):
        self.canv.setStrokeColor(colors.HexColor("#AEB4BC"))
        self.canv.setLineWidth(0.8)
        self.canv.line(8, 17, max(20, self.width - 8), 17)
        self.canv.setFillColor(DARK)
        self.canv.setFont(self.bold_font, 7.6)
        self.canv.drawCentredString(self.width / 2, 5, self.label)


def _paragraph_styles(regular_font: str, bold_font: str) -> dict[str, ParagraphStyle]:
    return {
        "hero_brand": ParagraphStyle(
            "HeroBrand", fontName=bold_font, fontSize=18, leading=18,
            textColor=RED, alignment=TA_LEFT, spaceAfter=1,
        ),
        "hero_subbrand": ParagraphStyle(
            "HeroSubBrand", fontName=bold_font, fontSize=6.8, leading=8,
            textColor=GREY, alignment=TA_LEFT,
        ),
        "dealer_name": ParagraphStyle(
            "DealerName", fontName=bold_font, fontSize=15, leading=17,
            textColor=DARK, alignment=TA_RIGHT,
        ),
        "dealer_details": ParagraphStyle(
            "DealerDetails", fontName=regular_font, fontSize=7.3, leading=9.3,
            textColor=GREY, alignment=TA_RIGHT, splitLongWords=1,
        ),
        "document_title": ParagraphStyle(
            "DocumentTitle", fontName=bold_font, fontSize=13.2, leading=16,
            textColor=RED, alignment=TA_CENTER,
        ),
        "section": ParagraphStyle(
            "Section", fontName=bold_font, fontSize=9, leading=11,
            textColor=RED, spaceBefore=1, spaceAfter=4,
        ),
        "field_label": ParagraphStyle(
            "FieldLabel", fontName=bold_font, fontSize=7, leading=8.5,
            textColor=GREY, splitLongWords=1,
        ),
        "field_value": ParagraphStyle(
            "FieldValue", fontName=regular_font, fontSize=8.1, leading=10.2,
            textColor=DARK, splitLongWords=1,
        ),
        "small": ParagraphStyle(
            "Small", fontName=regular_font, fontSize=7, leading=8.7,
            textColor=GREY, splitLongWords=1,
        ),
        "normal": ParagraphStyle(
            "Normal", fontName=regular_font, fontSize=8, leading=10.5,
            textColor=DARK, splitLongWords=1,
        ),
        "estimate_label": ParagraphStyle(
            "EstimateLabel", fontName=bold_font, fontSize=8.2, leading=10,
            textColor=DARK,
        ),
        "estimate_value": ParagraphStyle(
            "EstimateValue", fontName=bold_font, fontSize=12, leading=14,
            textColor=RED,
        ),
        "remarks": ParagraphStyle(
            "Remarks", fontName=regular_font, fontSize=7.6, leading=10,
            textColor=DARK, splitLongWords=1,
        ),
    }


def _safe_text(value: Any, empty: str = "Not provided") -> str:
    text = str(value or "").strip()
    return text if text else empty


def _amount_for_pdf(amount: float, unicode_rupee: bool) -> str:
    amount_text = f"{float(amount):,.2f}"
    return f"₹{amount_text}" if unicode_rupee else f"INR {amount_text}"


def build_extra_fittings_pdf(payload: dict[str, Any]) -> bytes:
    """Create an A4 PDF in memory from a clean customer snapshot."""
    customer_name = _safe_text(payload.get("customer_name"), "")
    normalized_phone = normalize_indian_mobile(str(payload.get("customer_phone", "")))
    category = str(payload.get("vehicle_category", "")).strip()
    if category not in ("Motorcycle", "Scooter"):
        raise ValueError("Vehicle category must be Motorcycle or Scooter.")
    model = _safe_text(payload.get("vehicle_model"), "")
    variant = _safe_text(payload.get("vehicle_variant"), "Not specified")
    if not customer_name:
        raise ValueError("Customer name is required.")
    if not normalized_phone:
        raise ValueError("Enter a valid 10-digit Indian mobile number.")
    if not model:
        raise ValueError("Vehicle model is required.")

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
            selected_date = _today_india()
    if not isinstance(selected_date, date):
        selected_date = _today_india()

    all_fittings = MOTORCYCLE_FITTINGS if category == "Motorcycle" else SCOOTER_FITTINGS
    submitted_selected = payload.get("selected_fittings", [])
    if not isinstance(submitted_selected, (list, tuple, set)):
        submitted_selected = []
    selected_fittings = {str(item) for item in submitted_selected}
    # Ignore any fitting that does not belong to the selected category.
    selected_fittings.intersection_update(all_fittings)

    regular_font, bold_font, unicode_rupee = _register_pdf_fonts()
    styles = _paragraph_styles(regular_font, bold_font)

    buffer = io.BytesIO()
    page_width, _ = A4
    left_margin = 14 * mm
    right_margin = 14 * mm
    usable_width = page_width - left_margin - right_margin

    def draw_footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(RED)
        canvas.setLineWidth(0.8)
        canvas.line(left_margin, 27, page_width - right_margin, 27)
        canvas.setFillColor(GREY)
        canvas.setFont(regular_font, 6.8)
        canvas.drawString(left_margin, 15, f"SELVA MOTORS  |  {DEALERSHIP_PHONE_TEXT}")
        canvas.drawRightString(page_width - right_margin, 15, "Thank you for choosing us.")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=right_margin,
        leftMargin=left_margin,
        topMargin=13 * mm,
        bottomMargin=12 * mm,
        title="SELVA MOTORS - EXTRA FITTINGS MARK SHEET",
        author=DEALERSHIP_NAME,
        subject="Customer extra fittings record and estimate",
    )

    hero_brand = Paragraph(
        "HERO<br/><font size='6.8' color='#5B616B'>MOTO CORP</font>",
        styles["hero_brand"],
    )
    dealer_details = Paragraph(
        f"{escape(DEALERSHIP_ADDRESS)}<br/>{escape(DEALERSHIP_PHONE_TEXT)}",
        styles["dealer_details"],
    )
    dealer_block = Table(
        [[
            Table([[hero_brand]], colWidths=[38 * mm]),
            Table(
                [[Paragraph(escape(DEALERSHIP_NAME), styles["dealer_name"])], [dealer_details]],
                colWidths=[usable_width - 44 * mm],
            ),
        ]],
        colWidths=[44 * mm, usable_width - 44 * mm],
    )
    dealer_block.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LINEBELOW", (0, 0), (-1, -1), 1.6, RED),
    ]))

    title_table = Table(
        [[Paragraph("EXTRA FITTINGS MARK SHEET", styles["document_title"])]],
        colWidths=[usable_width],
    )
    title_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE_RED),
        ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#F3C1C9")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))

    field_pairs = [
        ("Customer Name", customer_name),
        ("Customer Phone", format_phone_for_document(normalized_phone)),
        ("Vehicle Category", category),
        ("Vehicle Model", model),
        ("Vehicle Variant", variant),
        ("Date", selected_date.strftime("%d-%m-%Y")),
        ("Chassis Number", _safe_text(payload.get("chassis_number"))),
        ("Engine Number", _safe_text(payload.get("engine_number"))),
    ]
    detail_rows = []
    for row_index in range(0, len(field_pairs), 2):
        label_1, value_1 = field_pairs[row_index]
        label_2, value_2 = field_pairs[row_index + 1]
        detail_rows.append([
            Paragraph(escape(label_1), styles["field_label"]),
            Paragraph(escape(value_1), styles["field_value"]),
            Paragraph(escape(label_2), styles["field_label"]),
            Paragraph(escape(value_2), styles["field_value"]),
        ])
    label_width = 24 * mm
    value_width = (usable_width - 2 * label_width) / 2
    details_table = Table(
        detail_rows,
        colWidths=[label_width, value_width, label_width, value_width],
        hAlign="LEFT",
    )
    details_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), WHITE),
        ("BACKGROUND", (0, 0), (0, -1), PALE),
        ("BACKGROUND", (2, 0), (2, -1), PALE),
        ("GRID", (0, 0), (-1, -1), 0.45, LIGHT_GREY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
    ]))

    fitting_flowables = [
        CheckboxItem(item, item in selected_fittings, regular_font)
        for item in all_fittings
    ]
    if len(fitting_flowables) % 2:
        fitting_flowables.append(Spacer(1, 14))
    fitting_rows = [fitting_flowables[i:i + 2] for i in range(0, len(fitting_flowables), 2)]
    checklist_table = Table(
        fitting_rows,
        colWidths=[usable_width / 2, usable_width / 2],
        hAlign="LEFT",
    )
    checklist_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, LIGHT_GREY),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, LIGHT_GREY),
        ("BACKGROUND", (0, 0), (-1, -1), WHITE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    amount_text = _amount_for_pdf(amount, unicode_rupee)
    remarks = str(payload.get("remarks", "") or "").strip()
    if remarks:
        remarks_para = Paragraph(f"<b>Remarks</b><br/>{escape(remarks)}", styles["remarks"])
    else:
        remarks_para = Paragraph(
            "<b>Remarks</b><br/>________________________________________________<br/>________________________________________________",
            styles["remarks"],
        )
    estimate_table = Table(
        [[
            [Paragraph("Estimated Extra Fittings Amount", styles["estimate_label"]),
             Spacer(1, 3),
             Paragraph(escape(amount_text), styles["estimate_value"])],
            remarks_para,
        ]],
        colWidths=[usable_width * 0.46, usable_width * 0.54],
        hAlign="LEFT",
    )
    estimate_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.7, LIGHT_GREY),
        ("INNERGRID", (0, 0), (-1, -1), 0.45, LIGHT_GREY),
        ("BACKGROUND", (0, 0), (0, 0), PALE_RED),
        ("BACKGROUND", (1, 0), (1, 0), WHITE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))

    declaration_heading = Paragraph("CUSTOMER DECLARATION", styles["section"])
    declaration = Paragraph(
        "The fittings ticked above are recorded for reference. The amount shown is an estimate only "
        "and may differ from the final invoice depending on actual work, fitment, applicable charges, "
        "and customer-approved changes. This mark sheet is not a tax invoice or proof of payment.",
        styles["normal"],
    )
    signature_table = Table(
        [[
            SignatureBox("Customer Signature", regular_font, bold_font),
            SignatureBox("For SELVA MOTORS - Authorized Signature", regular_font, bold_font),
        ]],
        colWidths=[usable_width / 2, usable_width / 2],
        hAlign="LEFT",
    )
    signature_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    story = [
        dealer_block,
        Spacer(1, 5),
        title_table,
        Spacer(1, 7),
        Paragraph("CUSTOMER & VEHICLE DETAILS", styles["section"]),
        details_table,
        Spacer(1, 7),
        Paragraph("EXTRA FITTINGS CHECKLIST", styles["section"]),
        Paragraph("Ticked boxes indicate selected items; empty boxes indicate items not selected.", styles["small"]),
        Spacer(1, 3),
        checklist_table,
        Spacer(1, 7),
        Paragraph("ESTIMATE & REMARKS", styles["section"]),
        estimate_table,
        Spacer(1, 7),
        KeepTogether([
            declaration_heading,
            declaration,
            Spacer(1, 12),
            signature_table,
        ]),
    ]
    doc.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    return buffer.getvalue()


# ---------- Streamlit UI ----------
def _reset_form_state() -> None:
    """Reset only this module's session keys; leave the existing app untouched."""
    keys_to_remove = [key for key in list(st.session_state.keys()) if str(key).startswith("ef_")]
    for key in keys_to_remove:
        if key != "ef_reset_button":
            st.session_state.pop(key, None)


def _section_heading(text: str) -> None:
    st.markdown(
        f"<div style='margin:14px 0 7px;padding:8px 11px;border-left:4px solid #C8102E;"
        f"background:#FFF5F6;border-radius:5px;color:#22252A;font-weight:800;'>{escape(text)}</div>",
        unsafe_allow_html=True,
    )


def _form_payload(
    customer_name: str,
    raw_phone: str,
    category: str,
    model: str,
    variant: str,
    chassis: str,
    engine: str,
    selected_date: date,
    amount: float,
    remarks: str,
    selected_fittings: list[str],
) -> dict[str, Any]:
    return {
        "customer_name": customer_name.strip(),
        "customer_phone": raw_phone.strip(),
        "vehicle_category": category,
        "vehicle_model": model.strip(),
        "vehicle_variant": variant.strip(),
        "chassis_number": chassis.strip(),
        "engine_number": engine.strip(),
        "date": selected_date,
        "estimate_amount": float(amount),
        "remarks": remarks.strip(),
        "selected_fittings": list(selected_fittings),
    }


def _validate_payload(payload: dict[str, Any]) -> list[str]:
    errors = []
    if not payload.get("customer_name", "").strip():
        errors.append("Customer Name is required.")
    if not normalize_indian_mobile(payload.get("customer_phone", "")):
        errors.append("Enter a valid Indian mobile number (10 digits, optionally with +91).")
    if payload.get("vehicle_category") not in ("Motorcycle", "Scooter"):
        errors.append("Select Motorcycle or Scooter.")
    if not payload.get("vehicle_model", "").strip():
        errors.append("Vehicle Model is required. Select a model or enter it manually.")
    try:
        if float(payload.get("estimate_amount", 0)) < 0:
            errors.append("Estimate amount cannot be negative.")
    except (TypeError, ValueError):
        errors.append("Enter a valid estimate amount.")
    return errors


def render_extra_fittings_page() -> None:
    """Render the page only when explicitly called from the existing app."""
    try:
        catalogue, catalogue_warning = _load_catalogue()
    except Exception as exc:  # Defensive boundary for a module loaded by a larger app.
        catalogue, catalogue_warning = {"Motorcycle": [], "Scooter": []}, str(exc)

    st.markdown(
        """
        <div style="border-bottom:3px solid #C8102E;padding:4px 0 12px;margin-bottom:14px;">
          <div style="font-size:11px;letter-spacing:2px;color:#C8102E;font-weight:800;">HERO MOTOCORP</div>
          <div style="font-size:27px;font-weight:900;line-height:1.15;color:#22252A;">SELVA MOTORS</div>
          <div style="font-size:13px;color:#5B616B;">EXTRA FITTINGS MARK SHEET</div>
          <div style="font-size:12px;color:#5B616B;margin-top:5px;">Katchanam Road, Near Bypass, Kilvelur &nbsp;|&nbsp; 9842538709 / 9894120041 / 9442176514</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Create a printable A4 extra fittings record and estimate. PDF generation happens only when you press Generate PDF.")
    if catalogue_warning:
        st.warning(catalogue_warning)
    st.info(
        "Vehicle list is a configurable offline starter catalogue, not live dealer inventory. "
        "Please confirm the exact model/variant against the vehicle documents; manual entry is available."
    )

    _section_heading("1. Customer Details")
    customer_col, phone_col = st.columns(2)
    with customer_col:
        customer_name = st.text_input(
            "Customer Name *", key="ef_customer_name", placeholder="Enter customer's full name"
        )
    with phone_col:
        raw_phone = st.text_input(
            "Customer Phone Number *", key="ef_customer_phone", placeholder="10-digit Indian mobile number"
        )

    _section_heading("2. Vehicle Details")
    cat_col, date_col = st.columns(2)
    with cat_col:
        category = st.selectbox(
            "Vehicle Category *", ["Motorcycle", "Scooter"], key="ef_category"
        )
    with date_col:
        selected_date = st.date_input(
            "Date", value=_today_india(), key="ef_date", format="DD-MM-YYYY"
        )

    category_models = catalogue.get(category, [])
    model_names = [str(item.get("name", "")).strip() for item in category_models if item.get("name")]
    model_options = model_names + [MANUAL_MODEL_OPTION]
    if not model_options:
        model_options = [MANUAL_MODEL_OPTION]
    model_key = f"ef_model_{category.lower()}"
    if st.session_state.get(model_key) not in model_options:
        st.session_state[model_key] = model_options[0]
    selected_model_option = st.selectbox(
        "Vehicle Model * (type to search)", model_options, key=model_key
    )
    if selected_model_option == MANUAL_MODEL_OPTION:
        model = st.text_input(
            "Enter Vehicle Model *", key=f"ef_manual_model_{category.lower()}",
            placeholder="Enter model name exactly as shown in vehicle documents",
        ).strip()
        variants: list[str] = []
        model_record: dict[str, Any] = {}
    else:
        model = selected_model_option
        model_record = next(
            (item for item in category_models if item.get("name") == selected_model_option), {}
        )
        variants = model_record.get("variants", []) if isinstance(model_record.get("variants", []), list) else []

    if variants and selected_model_option != MANUAL_MODEL_OPTION:
        variant_options = ["Not specified"] + variants + [MANUAL_MODEL_OPTION]
        variant_key = f"ef_variant_{category.lower()}_{_slug(model, 'model').lower()}"
        if st.session_state.get(variant_key) not in variant_options:
            st.session_state[variant_key] = variant_options[0]
        selected_variant_option = st.selectbox(
            "Vehicle Variant", variant_options, key=variant_key
        )
        if selected_variant_option == MANUAL_MODEL_OPTION:
            variant = st.text_input(
                "Enter Vehicle Variant", key=f"ef_manual_variant_{category.lower()}_{_slug(model, 'model').lower()}",
                placeholder="Type variant from the vehicle documents",
            ).strip()
        elif selected_variant_option == "Not specified":
            variant = ""
        else:
            variant = selected_variant_option
    else:
        variant = st.text_input(
            "Vehicle Variant (manual entry)",
            key=f"ef_variant_manual_{category.lower()}_{_slug(model or 'model', 'model').lower()}",
            placeholder="Enter variant if shown in vehicle documents",
        ).strip()

    chassis_col, engine_col = st.columns(2)
    with chassis_col:
        chassis = st.text_input(
            "Chassis Number (optional)", key="ef_chassis", placeholder="Enter chassis number manually"
        )
    with engine_col:
        engine = st.text_input(
            "Engine Number (optional)", key="ef_engine", placeholder="Enter engine number manually"
        )

    _section_heading("3. Select Extra Fittings")
    all_fittings = MOTORCYCLE_FITTINGS if category == "Motorcycle" else SCOOTER_FITTINGS
    selected_fittings: list[str] = []
    left_col, right_col = st.columns(2, gap="medium")
    for idx, fitting in enumerate(all_fittings):
        target_col = left_col if idx % 2 == 0 else right_col
        with target_col:
            fit_key = f"ef_fit_{category.lower()}_{_slug(fitting, 'item').lower()}"
            is_selected = st.checkbox(fitting, key=fit_key)
            if is_selected:
                selected_fittings.append(fitting)

    st.caption(
        f"Selected: {len(selected_fittings)} of {len(all_fittings)} fittings. "
        "Only items checked here will be ticked in the PDF; all category-specific items remain visible."
    )

    _section_heading("4. Estimate Amount")
    amount_col, remarks_col = st.columns([1, 1.25])
    with amount_col:
        amount = st.number_input(
            "Estimated Extra Fittings Amount (₹)", min_value=0.0, value=0.0,
            step=100.0, format="%.2f", key="ef_estimate",
        )
        st.caption(f"Estimate preview: ₹{amount:,.2f} (not necessarily the final invoice amount).")
    with remarks_col:
        remarks = st.text_area(
            "Additional Remarks (optional)", key="ef_remarks", height=92,
            placeholder="Optional note for the customer or dealership record",
        )

    current_payload = _form_payload(
        customer_name, raw_phone, category, model, variant, chassis, engine,
        selected_date, amount, remarks, selected_fittings,
    )
    current_signature = _signature(current_payload)

    # Remove the previous customer's/stale PDF as soon as ANY current form value changes.
    saved_signature = st.session_state.get("ef_pdf_signature")
    if saved_signature and saved_signature != current_signature:
        for key in ("ef_pdf_bytes", "ef_pdf_filename", "ef_pdf_signature"):
            st.session_state.pop(key, None)

    button_col, reset_col = st.columns([1.3, 1])
    with button_col:
        generate_clicked = st.button(
            "Generate PDF", type="primary", use_container_width=True, key="ef_generate_pdf"
        )
    with reset_col:
        st.button(
            "Reset Form", use_container_width=True, key="ef_reset_button", on_click=_reset_form_state
        )

    if generate_clicked:
        errors = _validate_payload(current_payload)
        if errors:
            st.session_state.pop("ef_pdf_bytes", None)
            st.session_state.pop("ef_pdf_filename", None)
            st.session_state.pop("ef_pdf_signature", None)
            for error in errors:
                st.error(error)
        else:
            normalized = normalize_indian_mobile(current_payload["customer_phone"])
            current_payload["customer_phone"] = normalized or current_payload["customer_phone"]
            try:
                pdf_bytes = build_extra_fittings_pdf(current_payload)
                filename = build_pdf_filename(current_payload["customer_name"], current_payload["date"])
                st.session_state["ef_pdf_bytes"] = pdf_bytes
                st.session_state["ef_pdf_filename"] = filename
                st.session_state["ef_pdf_signature"] = current_signature
                st.success("Extra fittings PDF generated successfully. Review the filename and download below.")
            except Exception as exc:
                st.session_state.pop("ef_pdf_bytes", None)
                st.session_state.pop("ef_pdf_filename", None)
                st.session_state.pop("ef_pdf_signature", None)
                st.error(f"PDF generation failed: {exc}")

    saved_pdf = st.session_state.get("ef_pdf_bytes")
    saved_filename = st.session_state.get("ef_pdf_filename")
    if saved_pdf and st.session_state.get("ef_pdf_signature") == current_signature:
        st.markdown(
            f"<div style='border:1px solid #D7E0E8;background:#FFFFFF;padding:11px 13px;"
            f"border-radius:9px;margin:8px 0;color:#22252A;'><b>PDF ready:</b> {escape(str(saved_filename))}</div>",
            unsafe_allow_html=True,
        )
        st.download_button(
            "Download PDF",
            data=saved_pdf,
            file_name=saved_filename,
            mime="application/pdf",
            use_container_width=True,
            key="ef_download_pdf",
        )
    elif st.session_state.get("ef_pdf_signature"):
        st.info("The form changed after the last PDF was generated. Generate the PDF again to use the latest details.")
