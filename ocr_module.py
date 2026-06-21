from __future__ import annotations

import io
import re

from PIL import Image


def _clean_text(text: str) -> str:
    return re.sub(r"[ \t]+", " ", (text or "")).strip()


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    text_parts: list[str] = []
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text_parts.append(page.extract_text() or "")
        text = "\n".join(text_parts).strip()
        if text:
            return text
    except Exception:
        pass

    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            text_parts.append(page.extract_text() or "")
        return "\n".join(text_parts).strip()
    except Exception:
        return ""


def extract_text_from_image_bytes(image_bytes: bytes) -> str:
    try:
        import pytesseract
        image = Image.open(io.BytesIO(image_bytes))
        return pytesseract.image_to_string(image)
    except Exception:
        return ""


def extract_text_from_upload(uploaded_file) -> str:
    if uploaded_file is None:
        return ""
    name = (getattr(uploaded_file, "name", "") or "").lower()
    data = uploaded_file.getvalue()
    if name.endswith(".pdf"):
        return extract_text_from_pdf_bytes(data)
    return extract_text_from_image_bytes(data)


def _label_value(patterns: list[str], source: str) -> str:
    for pat in patterns:
        m = re.search(pat, source, flags=re.IGNORECASE | re.MULTILINE)
        if m:
            val = m.group(1).strip()
            val = re.sub(r"\s{2,}.*$", "", val).strip()
            return val
    return ""


def parse_invoice_text(text: str) -> dict[str, str]:
    text = _clean_text(text)
    if not text:
        return {}

    out: dict[str, str] = {}
    out["invoice_number"] = _label_value([
        r"invoice\s*(?:no|number|#)\s*[:\-]?\s*([A-Z0-9\-/]+)",
        r"bill\s*(?:no|number|#)\s*[:\-]?\s*([A-Z0-9\-/]+)",
    ], text)
    out["job_card_number"] = _label_value([
        r"job\s*card\s*(?:no|number|#)\s*[:\-]?\s*([A-Z0-9\-/]+)",
    ], text)
    out["customer_name"] = _label_value([
        r"customer\s*name\s*[:\-]?\s*([A-Za-z .]+?)(?:\s+(?:mobile|phone|contact|reg(?:istration)?|vehicle|bike|model|invoice|bill|total|amount)\b|$)",
        r"billed\s*to\s*[:\-]?\s*([A-Za-z .]+?)(?:\s+(?:mobile|phone|contact|reg(?:istration)?|vehicle|bike|model|invoice|bill|total|amount)\b|$)",
    ], text)
    out["mobile_number"] = _label_value([
        r"(?:mobile|phone|contact)\s*[:\-]?\s*([6-9]\d{9})",
    ], text)
    out["registration_number"] = _label_value([
        r"(?:reg(?:istration)?\s*(?:no|number)?|vehicle\s*no)\s*[:\-]?\s*([A-Z0-9\-/ ]+?)(?:\s+(?:bike|model|invoice|bill|total|amount|customer|mobile|phone|contact)\b|$)",
    ], text)
    out["bike_model"] = _label_value([
        r"(?:bike\s*model|model)\s*[:\-]?\s*([A-Za-z0-9 .\-]+?)(?:\s+(?:invoice|bill|total|amount|customer|mobile|phone|contact)\b|$)",
    ], text)
    out["spare_amount"] = _label_value([
        r"(?:spares?|parts?)\s*[:\-]?\s*₹?\s*([0-9,]+(?:\.\d+)?)",
    ], text)
    out["oil_amount"] = _label_value([
        r"oil\s*[:\-]?\s*₹?\s*([0-9,]+(?:\.\d+)?)",
    ], text)
    out["labour_amount"] = _label_value([
        r"labou?r\s*[:\-]?\s*₹?\s*([0-9,]+(?:\.\d+)?)",
    ], text)
    out["grand_total"] = _label_value([
        r"(?:grand\s*total|total\s*amount|amount)\s*[:\-]?\s*₹?\s*([0-9,]+(?:\.\d+)?)",
    ], text)

    if not out["customer_name"]:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for line in lines[:12]:
            if len(line.split()) <= 4 and not re.search(r"\d{6,}", line):
                out["customer_name"] = line
                break

    return {k: v for k, v in out.items() if v}


def load_and_parse(uploaded_file) -> tuple[str, dict[str, str]]:
    text = extract_text_from_upload(uploaded_file)
    return text, parse_invoice_text(text)
