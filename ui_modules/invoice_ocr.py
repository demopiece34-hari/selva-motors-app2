"""Invoice OCR and parsing helpers for Selva Motors ERP.

This module has no Google Sheets access and does not save invoices. It extracts
invoice text, item rows, classifications and totals for a Streamlit review step.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, ImageEnhance, ImageFilter

try:
    import pdfplumber
except Exception:  # pragma: no cover - optional deployment dependency
    pdfplumber = None

try:
    import PyPDF2
except Exception:  # pragma: no cover
    PyPDF2 = None

try:
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None

try:
    from pdf2image import convert_from_path
except Exception:  # pragma: no cover
    convert_from_path = None


SPECIAL_PART_NUMBERS = ("SPDMCYL02SS", "SPDSCOT01SS")
_UOM = {"PC", "PCS", "NOS", "NO", "SET", "PAIR", "ML", "L", "LTR", "KG"}
_SECTION_HEADERS = (
    "Genuine Parts Details",
    "Other Parts Details",
    "Labour Details",
    "Other Labour Details",
)


def _money(value: Any) -> float:
    if value is None:
        return 0.0
    raw = str(value).strip().replace(",", "")
    raw = raw.replace("₹", "").replace("Rs.", "").replace("RS.", "")
    match = re.search(r"-?\d+(?:\.\d+)?", raw)
    return round(float(match.group(0)), 2) if match else 0.0


def _first(patterns: list[str], text: str, default: str = "") -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I | re.M)
        if match:
            return str(match.group(1)).strip()
    return default


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip(" :-|,\t")


def _part_number(description: str) -> tuple[str, str, bool]:
    """Return part number, detection status and manual-review flag.

    Only the two configured special codes receive OCR character correction.
    Corrections are confined to a part-number token, never applied globally.
    """
    candidates = re.findall(r"(?<![A-Z0-9])[A-Z0-9]{8,18}(?![A-Z0-9])", description.upper())
    if not candidates:
        return "", "Not detected", False

    confusion_groups = ({"O", "0"}, {"I", "1"}, {"S", "5"})

    def equivalent(a: str, b: str) -> bool:
        if a == b:
            return True
        return any(a in group and b in group for group in confusion_groups)

    for candidate in candidates:
        for canonical in SPECIAL_PART_NUMBERS:
            if candidate == canonical:
                return canonical, "Exact", False
            if len(candidate) == len(canonical) and all(equivalent(a, b) for a, b in zip(candidate, canonical)):
                return canonical, f"OCR corrected from {candidate}", False

    # Keep near-matches unchanged and flag them. Never silently invent the exact code.
    for candidate in candidates:
        for canonical in SPECIAL_PART_NUMBERS:
            ratio = SequenceMatcher(None, candidate, canonical).ratio()
            if candidate.startswith("SPD") and ratio >= 0.84:
                return candidate, f"Needs manual verification (possible {canonical})", True

    # First alphanumeric item code is the part number for ordinary parts.
    return candidates[0], "Detected", False


def _is_oil_item(description: str, part_number: str, hsn: str) -> bool:
    text = re.sub(r"\s+", " ", f"{description} {part_number}").upper()
    if part_number in SPECIAL_PART_NUMBERS:
        return True
    if re.search(r"\b(OIL\s+SEAL|OIL\s+FILTER|OIL\s+PUMP)\b", text):
        return False
    if hsn == "27101972":
        return True
    if re.search(r"\b(ENGINE|GEAR|FORK|TRANSMISSION|2T|4T)\s+OIL\b", text):
        return True
    if re.search(r"\b(LUBRICANT|LUBRICATION OIL)\b", text):
        return True
    if re.search(r"\b(10W[- ]?30|10W[- ]?40|5W[- ]?30|20W[- ]?40)\b", text) and re.search(r"\b(OIL|4T|HERO)\b", text):
        return True
    if re.search(r"\bHERO\s*4T\s*PLUS\b", text):
        return True
    return False


def _section_text(lines: list[str], header: str, stop_headers: tuple[str, ...]) -> list[str]:
    start = None
    for index, line in enumerate(lines):
        if header.casefold() in line.casefold():
            start = index + 1
            break
    if start is None:
        return []
    end = len(lines)
    for index in range(start, len(lines)):
        lowered = lines[index].casefold()
        if any(stop.casefold() in lowered for stop in stop_headers):
            end = index
            break
    return lines[start:end]


def _parse_item_row(row_lines: list[str], section_name: str) -> dict[str, Any] | None:
    # Hero invoices can wrap the serial number, part code and HSN across lines.
    first_index = None
    hsn_match = None
    for index, line in enumerate(row_lines):
        matches = list(re.finditer(r"\b(\d{6,8})\b(?=\s*[=:|]?\s+(?:Paid|FSC|Free|Warranty)\b)", line, flags=re.I))
        if matches:
            first_index = index
            hsn_match = matches[-1]
            break
    if first_index is None or hsn_match is None:
        return None

    first_line = row_lines[first_index]
    hsn = hsn_match.group(1)
    prefix_parts = []
    for line in row_lines[:first_index]:
        candidate = _clean(line)
        if candidate and not re.fullmatch(r"\d+", candidate):
            prefix_parts.append(candidate)
    inline_prefix = first_line[:hsn_match.start()].strip()
    inline_prefix = re.sub(r"^\s*\d+\s+", "", inline_prefix)
    if inline_prefix:
        prefix_parts.append(inline_prefix)
    prefix = _clean(" ".join(prefix_parts))
    prefix = re.sub(r"^\s*\d+\s+", "", prefix).strip()

    continuation = []
    for line in row_lines[first_index + 1:]:
        candidate = _clean(line)
        candidate = re.sub(r"^\d+\s+", "", candidate)
        if candidate and not re.match(r"^(Total|CGST|SGST|IGST)\b", candidate, re.I):
            continuation.append(candidate)
    description = _clean(" ".join([prefix] + continuation))

    table_tail = re.sub(r"^[\s:=|]+", "", first_line[hsn_match.end():])
    tokens = [token.strip(",;|:}[]()") for token in re.findall(r"\S+", table_tail)]
    tokens = [token for token in tokens if token and token not in {"=", ":", ";", "|"}]
    if len(tokens) < 6:
        return None
    qty = _money(tokens[1]) if len(tokens) > 1 else 0.0
    offset = 3 if len(tokens) > 2 and tokens[2].upper().rstrip(".") in _UOM else 2
    rate = _money(tokens[offset]) if len(tokens) > offset else 0.0
    gross_value = _money(tokens[offset + 1]) if len(tokens) > offset + 1 else 0.0
    discount = _money(tokens[offset + 2]) if len(tokens) > offset + 2 else 0.0
    taxable = _money(tokens[offset + 3]) if len(tokens) > offset + 3 else 0.0

    cgst = 0.0
    sgst = 0.0
    tax_positions = [i for i, token in enumerate(tokens) if re.fullmatch(r"\d+(?:\.\d+)?%", token)]
    if len(tax_positions) >= 2:
        if tax_positions[0] + 1 < len(tokens):
            cgst = _money(tokens[tax_positions[0] + 1])
        if tax_positions[1] + 1 < len(tokens):
            sgst = _money(tokens[tax_positions[1] + 1])
    numeric_after_hsn = [_money(token) for token in tokens if re.search(r"\d", token)]
    line_total = numeric_after_hsn[-1] if numeric_after_hsn else 0.0

    if section_name in {"Genuine Parts Details", "Other Parts Details"} or (section_name == "OCR Detected Parts" and hsn != "998729"):
        part_number, part_status, needs_review = _part_number(description)
        if not part_number:
            part_status = "Part number not detected - verify invoice"
            needs_review = True
    else:
        part_number, part_status, needs_review = "", "Not applicable", False
    if section_name == "Labour Details":
        classification = "Labour"
    elif section_name == "Other Labour Details":
        classification = "Other"
    elif section_name == "OCR Detected Parts" and hsn == "998729":
        classification = "Other" if re.search(r"ADDITIONAL|REPAIR CHARGES", description, re.I) else "Labour"
    elif _is_oil_item(description, part_number, hsn):
        classification = "Oil"
    else:
        classification = "Spare Part"

    return {
        "Description": description,
        "Part Number": part_number,
        "Part Number Status": part_status,
        "Needs Review": bool(needs_review),
        "Quantity": qty,
        "Unit Price": rate,
        "Line Total": line_total,
        "Gross Value": gross_value,
        "Discount": discount,
        "Taxable Value": taxable,
        "CGST": cgst,
        "SGST": sgst,
        "Classification": classification,
        "Section": section_name,
        "HSN": hsn,
    }


def extract_invoice_items(text: str) -> list[dict[str, Any]]:
    lines = str(text or "").splitlines()
    items: list[dict[str, Any]] = []
    ordered = [
        ("Genuine Parts Details", ("Other Parts Details", "Labour Details", "Other Labour Details", "CGST", "SGST", "IGST", "Net Amount", "Invoice Amount")),
        ("Other Parts Details", ("Labour Details", "Other Labour Details", "CGST", "SGST", "IGST", "Net Amount", "Invoice Amount")),
        ("Labour Details", ("Other Labour Details", "CGST", "SGST", "IGST", "Net Amount", "Invoice Amount")),
        ("Other Labour Details", ("CGST", "SGST", "IGST", "Net Amount", "Invoice Amount")),
    ]
    for section_name, stops in ordered:
        section_lines = _section_text(lines, section_name, stops)
        pending_prefix: list[str] = []
        current: list[str] = []
        for line in section_lines:
            if re.match(r"^\s*Total\b", line, re.I):
                if current:
                    parsed = _parse_item_row(current, section_name)
                    if parsed:
                        items.append(parsed)
                    current = []
                pending_prefix = []
                continue
            is_item_start = bool(re.search(r"\b\d{6,8}\b(?=\s*[=:|]?\s+(?:Paid|FSC|Free|Warranty)\b)", line, re.I))
            if is_item_start:
                if current:
                    parsed = _parse_item_row(current, section_name)
                    if parsed:
                        items.append(parsed)
                current = pending_prefix + [line]
                pending_prefix = []
            elif current:
                if line.strip():
                    current.append(line)
            elif line.strip() and not re.search(r"\b(?:Description|HSN|Billing|Qty|UOM)\b", line, re.I):
                pending_prefix.append(line)
        if current:
            parsed = _parse_item_row(current, section_name)
            if parsed:
                items.append(parsed)

    # OCR may miss a section heading or wrap a table differently. If named
    # sections yielded no rows, recover one-line entries from HSN + billing
    # marker patterns. Do not attach arbitrary following OCR text: it can include
    # page footers, phone numbers or summary rows. Missing wrapped codes are
    # flagged for manual review rather than guessed.
    if not items:
        for line in lines:
            if re.search(
                r"\b\d{6,8}\b(?=\s*[=:|]?\s+(?:Paid|FSC|Free|Warranty)\b)",
                line,
                re.I,
            ):
                parsed = _parse_item_row([line], "OCR Detected Parts")
                if parsed:
                    items.append(parsed)
                continue
            # If OCR lost the HSN/table columns but still captured a part code,
            # preserve the detected part row with zero numeric values and require
            # manual completion instead of guessing the amount or quantity.
            part_match = re.search(r"\b([A-Z0-9]{8,18})-[A-Z]{2,}\b", line, re.I)
            if part_match and re.search(r"\bPaid\b", line, re.I):
                description = re.sub(r"^\s*\d+\s+", "", _clean(line))
                items.append({
                    "Description": description,
                    "Part Number": part_match.group(1).upper(),
                    "Part Number Status": "Detected; row amounts require manual review",
                    "Needs Review": True,
                    "Quantity": 0.0,
                    "Unit Price": 0.0,
                    "Line Total": 0.0,
                    "Gross Value": 0.0,
                    "Discount": 0.0,
                    "Taxable Value": 0.0,
                    "CGST": 0.0,
                    "SGST": 0.0,
                    "Classification": "Spare Part",
                    "Section": "OCR Detected Parts",
                    "HSN": "",
                })
    return items


def _extract_header_values(text: str) -> dict[str, str]:
    flat = re.sub(r"\s+", " ", str(text or ""))
    invoice_no = _first([
        r"Invoice\s*(?:No|Number)\s*[:\-]?\s*([A-Z0-9\-\/]+)",
        r"Bill\s*(?:No|Number)\s*[:\-]?\s*([A-Z0-9\-\/]+)",
    ], flat)
    job_card = _first([r"Job\s*Card\s*(?:No|Number)?\s*[:\-]?\s*([A-Z0-9\-\/]+)"], flat)
    invoice_date = _first([
        r"Invoice\s*Date\s*[:\-]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4}(?:\s+\d{1,2}:\d{2}:\d{2})?)"
    ], flat)
    mobile = _first([r"Mobile\s*No\s*[:\-]?\s*([6-9]\d{9})"], flat)
    reg_no = _first([
        r"Vehicle\s*(?:Reg|Registration)\s*(?:No|Number)?\s*[:\-]?\s*([A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{3,4})",
        r"Reg\s*(?:No|Number)?\s*[:\-]?\s*([A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{3,4})",
    ], flat)
    model = _first([
        r"Model\s*[:\-]?\s*([A-Za-z0-9 +._-]{2,45})\s+VIN\b"
    ], flat)
    name = _first([
        r"Customer\s*Name\s*[:\-]?\s*([A-Za-z .]{2,45})\s+Invoice\s*No"
    ], flat)
    return {
        "Invoice Number": re.sub(r"\s+", "", invoice_no).upper(),
        "Invoice Date": invoice_date,
        "Customer Name": _clean(name),
        "Customer Phone": mobile,
        "Registration Number": re.sub(r"[^A-Z0-9]", "", reg_no.upper()),
        "Job Card Number": re.sub(r"\s+", "", job_card).upper(),
        "Bike Model": _clean(model),
    }


def parse_invoice(text: str) -> dict[str, Any]:
    items = extract_invoice_items(text)
    header = _extract_header_values(text)

    def sum_classification(name: str) -> float:
        return round(sum(_money(item.get("Line Total")) for item in items if item.get("Classification") == name), 2)

    oil_amount = sum_classification("Oil")
    spare_amount = sum_classification("Spare Part")
    labour_amount = sum_classification("Labour")
    other_charges = sum_classification("Other")
    discount = round(sum(_money(item.get("Discount")) for item in items), 2)
    gst = round(sum(_money(item.get("CGST")) + _money(item.get("SGST")) for item in items), 2)
    round_off = _money(_first([r"Round\s*Off\s*[:\-]?\s*(-?[\d,]+(?:\.\d+)?)"], text))
    grand_total = _money(_first([
        r"Total\s*Invoice\s*Value\s*\(In\s*figure\)\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
        r"Invoice\s*Amount\s*Payable\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
        r"Invoice\s*Amt\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
        r"Grand\s*Total\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
    ], re.sub(r"\s+", " ", text)))

    item_sum = round(oil_amount + spare_amount + labour_amount + other_charges, 2)
    validation_difference = round(grand_total - item_sum - round_off, 2) if grand_total else None
    warnings = []
    if not items:
        warnings.append("No invoice line items could be parsed. Review the source invoice manually.")
    if not header.get("Invoice Number"):
        warnings.append("Invoice number was not detected.")
    if not header.get("Invoice Date"):
        warnings.append("Invoice date was not detected.")
    if any(item.get("Needs Review") for item in items):
        warnings.append("One or more part numbers need manual verification or were not detected by OCR.")
    if validation_difference is not None and abs(validation_difference) > 0.05:
        warnings.append(f"Item totals differ from invoice grand total by ₹{validation_difference:.2f} after round-off.")

    special_found = {part for part in ("SPDMCYL02SS", "SPDSCOT01SS") if any(item.get("Part Number") == part for item in items)}
    spare_count = sum(1 for item in items if item.get("Classification") == "Spare Part")
    return {
        **header,
        "Items": items,
        "Oil Change Status": "Yes" if oil_amount > 0 else "No",
        "Oil Amount": oil_amount,
        "Spare Parts Count": spare_count,
        "Spare Amount": spare_amount,
        "Labour Amount": labour_amount,
        "Other Charges": other_charges,
        "Discount": discount,
        "GST / Tax": gst,
        "Round Off": round_off,
        "Total Amount": grand_total,
        "Validation Difference": validation_difference,
        "Warnings": warnings,
        "Detected Special Part Numbers": sorted(special_found),
    }


def _ocr_image(image: Image.Image) -> str:
    if pytesseract is None:
        raise RuntimeError("Image OCR requires the pytesseract Python package and Tesseract OCR engine.")
    image = ImageOps.exif_transpose(image).convert("RGB")
    try:
        osd = pytesseract.image_to_osd(image)
        rotation = int(re.search(r"Rotate:\s+(\d+)", osd).group(1))
        if rotation:
            image = image.rotate(-rotation, expand=True)
    except Exception:
        pass
    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray)
    if gray.width < 1800:
        scale = max(2, min(3, int(1800 / max(gray.width, 1))))
        gray = gray.resize((gray.width * scale, gray.height * scale), Image.Resampling.LANCZOS)
    gray = ImageEnhance.Contrast(gray).enhance(1.35)
    gray = gray.filter(ImageFilter.SHARPEN)
    try:
        result = pytesseract.image_to_string(gray, config="--oem 3 --psm 6")
        if len(result.strip()) < 20:
            result = pytesseract.image_to_string(gray, config="--oem 3 --psm 11")
        return result.strip()
    except Exception as exc:
        raise RuntimeError(f"Tesseract image OCR failed: {type(exc).__name__}: {exc}") from exc


def extract_text_from_image(file_path: str) -> str:
    try:
        with Image.open(file_path) as image:
            return _ocr_image(image.copy())
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Unable to open/process invoice image: {type(exc).__name__}: {exc}") from exc


def extract_text_from_pdf(file_path: str) -> str:
    page_texts: list[str] = []
    page_count = 0
    if pdfplumber is not None:
        try:
            with pdfplumber.open(file_path) as pdf:
                page_count = len(pdf.pages)
                for page in pdf.pages:
                    try:
                        page_texts.append((page.extract_text(layout=False) or "").strip())
                    except Exception:
                        page_texts.append("")
        except Exception as exc:
            page_texts = []
            page_count = 0
            pdf_error = exc
        else:
            pdf_error = None
    else:
        pdf_error = None

    if not page_texts and PyPDF2 is not None:
        try:
            with open(file_path, "rb") as file_handle:
                reader = PyPDF2.PdfReader(file_handle)
                page_count = len(reader.pages)
                page_texts = [(page.extract_text() or "").strip() for page in reader.pages]
        except Exception as exc:
            pdf_error = exc

    if not page_texts:
        raise RuntimeError(f"Unable to read PDF pages: {type(pdf_error).__name__ if pdf_error else 'PDFReaderError'}: {pdf_error or 'No PDF text reader available'}")

    # Keep well-extracted digital pages unchanged. For sparse/partially scanned
    # pages, OCR as a second pass and prefer it only when it yields more text.
    for index, page_text in enumerate(page_texts):
        existing_text = page_text.strip()
        if len(existing_text) >= 120:
            continue
        if convert_from_path is None or pytesseract is None:
            if len(existing_text) < 20:
                raise RuntimeError(
                    f"PDF page {index + 1} has no selectable text. Scanned PDF OCR requires pdf2image, Tesseract, and Poppler (packages.txt)."
                )
            continue
        try:
            images = convert_from_path(file_path, dpi=250, first_page=index + 1, last_page=index + 1)
            if images:
                ocr_text = _ocr_image(images[0])
                if len(ocr_text) > len(existing_text) * 1.05:
                    page_texts[index] = ocr_text
        except Exception as exc:
            if len(existing_text) < 20:
                raise RuntimeError(f"Scanned PDF OCR failed on page {index + 1}: {type(exc).__name__}: {exc}") from exc

    combined = "\n\n".join(page_text for page_text in page_texts if page_text.strip()).strip()
    if not combined:
        raise RuntimeError("No text could be extracted from the PDF. The file may be blank, encrypted, or unreadable.")
    return combined


def extract_invoice_text(file_path: str) -> str:
    extension = Path(file_path).suffix.lower()
    if extension == ".pdf":
        return extract_text_from_pdf(file_path)
    if extension in {".jpg", ".jpeg", ".png"}:
        return extract_text_from_image(file_path)
    raise ValueError("Unsupported invoice file. Upload one PDF, JPG, JPEG, or PNG file.")


__all__ = [
    "SPECIAL_PART_NUMBERS", "extract_invoice_items", "extract_text_from_pdf",
    "extract_text_from_image", "extract_invoice_text", "parse_invoice",
]
