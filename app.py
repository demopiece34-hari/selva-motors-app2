
import re
import uuid
import math
import time as time_module
import base64
from ui_modules.hero_bikes_catalog_en_th import page_hero_bikes
from ui_modules.hero_invoice_loader import show_hero_invoice_loader
from ui_modules.theme import apply_theme
from ui_modules.sidebar import render_sidebar
from ui_modules.ui_components import render_page_header, render_home_landing
from pathlib import Path
from datetime import datetime, time
from zoneinfo import ZoneInfo

import streamlit as st
import pandas as pd

from PIL import Image
import qrcode

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

try:
    import pdfplumber
except Exception:
    pdfplumber = None

try:
    import PyPDF2
except Exception:
    PyPDF2 = None

try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    from streamlit_js_eval import get_geolocation
except Exception:
    get_geolocation = None


# ============================================================
# SELVA MOTORS ERP — Google Sheets write-only workflow with on-demand reports.
# No local spreadsheet or database is used for business-data storage.
# ============================================================

st.set_page_config(
    page_title="Selva Motors | Hero Connect ERP",
    page_icon="🏍️",
    layout="wide"
)

APP_TITLE = "SELVA MOTORS • HERO CONNECT ERP"
VERSION_TEXT = "Google Sheets Write-Only / On-Demand Reports"

UPLOAD_DIR = Path("uploads")
PDF_DIR = Path("generated_reports")

UPLOAD_DIR.mkdir(exist_ok=True)
PDF_DIR.mkdir(exist_ok=True)


COMPANY_LAT = 10.759710
COMPANY_LON = 79.742772
ALLOWED_RADIUS_METER = 100

APP_TZ = ZoneInfo("Asia/Kolkata")


def app_now():
    """Return current India time. Streamlit Cloud UTC issue fix."""
    return datetime.now(APP_TZ)


# ============================================================
# STYLE
# ============================================================
apply_theme()  # Shared presentation layer; does not access Google Sheets.



def get_hero_logo_base64():
    """Load the one maintained Hero logo asset and detect its true image MIME type."""
    logo_path = Path(__file__).resolve().parent / "assets" / "hero_logo.png"
    try:
        if not logo_path.is_file():
            return ""
        with Image.open(logo_path) as image:
            image_format = (image.format or "PNG").upper()
        mime = "image/jpeg" if image_format in {"JPEG", "JPG"} else "image/png"
        encoded = base64.b64encode(logo_path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"
    except Exception:
        return ""


# ============================================================
# GOOGLE SHEETS WORKSHEET SCHEMAS
# ============================================================
SHEETS = {
    "employees": [
        "User ID", "Password", "Employee Name", "Role", "Status"
    ],
    "attendance": [
        "Date", "Time", "User ID", "Technician Name", "Role",
        "Attendance Status", "Latitude", "Longitude", "Distance Meter",
        "Selfie Saved"
    ],
    "invoices": [
        "Entry ID", "Date", "Technician Name", "User ID",
        "Invoice Number", "Job Card Number", "Registration Number", "Bike Model", "Service Type",
        "Labour Amount", "Spare Parts Count", "Spare Amount", "Oil Change Status",
        "Total Amount", "Entry Type", "Status"
    ],
    "delete_requests": [
        "Request ID", "Date", "Time", "Entry ID", "Technician Name",
        "User ID", "Reason", "Request Status", "Admin Action Date"
    ],
    "manual_invoices": [
        "Manual Bill ID", "Date", "Technician Name", "User ID",
        "Customer Name", "Registration Number", "Bike Model", "Service Type",
        "Labour Amount", "Spare Parts Count", "Oil Count",
        "Total Amount", "PDF File", "Status"
    ],
}

def today_str():
    return app_now().strftime("%d-%m-%Y")


def time_str():
    return app_now().strftime("%I:%M:%S %p")


def now_stamp():
    return app_now().strftime("%d-%m-%Y %I:%M:%S %p")


def role():
    return st.session_state.get("role", "")


def is_admin():
    return role() == "Admin"


def is_manager():
    return role() == "Manager"


def is_technician():
    return role() == "Technician"


def is_prathisha():
    return role() == "Prathisha / System Staff"


# ============================================================
# CLEANING
# ============================================================
def clean_customer_name(value):
    text = str(value or "").strip()
    text = re.sub(r"Invoice\s*(No|Number)?\s*[:\-]?\s*[A-Z0-9\-\/]+", "", text, flags=re.I)
    text = re.sub(r"Bill\s*(No|Number)?\s*[:\-]?\s*[A-Z0-9\-\/]+", "", text, flags=re.I)
    text = re.sub(r"\b[A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{3,4}\b", "", text, flags=re.I)
    text = re.sub(r"\b[6-9]\d{9}\b", "", text)
    text = re.sub(r"\s+", " ", text).strip(" :-|")
    return text


def clean_bike_model(value):
    text = str(value or "").strip()
    text = re.sub(r"\bVIN\s*[:\-]?\s*[A-Z0-9]{8,30}\b", "", text, flags=re.I)
    text = re.sub(r"\bMBL[A-Z0-9]{8,30}\b", "", text, flags=re.I)
    text = re.sub(r"\b[6-9]\d{9}\b", "", text)
    text = re.sub(r"\s+", " ", text).strip(" :-|")
    return text


def clean_reg_no(value):
    text = str(value or "").upper().replace(" ", "")
    text = re.sub(r"[^A-Z0-9]", "", text)
    return text


def to_float(value):
    text = str(value or "").replace(",", "")
    nums = re.findall(r"\d+(?:\.\d+)?", text)
    return float(nums[0]) if nums else 0.0


def find_one(patterns, text, default=""):
    for pat in patterns:
        m = re.search(pat, text, flags=re.I | re.M)
        if m:
            return str(m.group(1)).strip()
    return default


# ============================================================
# GPS
# ============================================================
def distance_meter(lat1, lon1, lat2, lon2):
    try:
        lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
    except Exception:
        return 999999.0

    radius = 6371000
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 2)



def bearing_to_company(user_lat, user_lon, company_lat=COMPANY_LAT, company_lon=COMPANY_LON):
    try:
        lat1 = math.radians(float(user_lat))
        lat2 = math.radians(float(company_lat))
        diff_lon = math.radians(float(company_lon) - float(user_lon))

        x = math.sin(diff_lon) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(diff_lon)
        bearing = (math.degrees(math.atan2(x, y)) + 360) % 360
        return bearing
    except Exception:
        return None


def compass_direction(bearing):
    if bearing is None:
        return "Unknown"
    dirs = [
        "North", "North-East", "East", "South-East",
        "South", "South-West", "West", "North-West"
    ]
    idx = round(bearing / 45) % 8
    return dirs[idx]


def direction_hint(direction):
    hints = {
        "North": "Move straight towards North side.",
        "North-East": "Move towards right-front / North-East side.",
        "East": "Move towards right side / East side.",
        "South-East": "Move towards right-back / South-East side.",
        "South": "Move towards South side.",
        "South-West": "Move towards left-back / South-West side.",
        "West": "Move towards left side / West side.",
        "North-West": "Move towards left-front / North-West side.",
        "Unknown": "Direction not detected."
    }
    return hints.get(direction, "Direction not detected.")



def format_distance_km(distance_m):
    try:
        distance_m = float(distance_m)
        km = distance_m / 1000.0
        if km < 1:
            return f"{distance_m:.0f} m ({km:.2f} km)"
        return f"{km:.2f} km"
    except Exception:
        return "Distance not available"


def google_maps_direction_url(user_lat=None, user_lon=None):
    try:
        if user_lat is not None and user_lon is not None:
            return (
                "https://www.google.com/maps/dir/"
                f"{float(user_lat)},{float(user_lon)}/"
                f"{COMPANY_LAT},{COMPANY_LON}"
            )
    except Exception:
        pass
    return f"https://www.google.com/maps/search/?api=1&query={COMPANY_LAT},{COMPANY_LON}"


def google_maps_embed_url(user_lat=None, user_lon=None):
    try:
        if user_lat is not None and user_lon is not None:
            return (
                "https://maps.google.com/maps"
                f"?saddr={float(user_lat)},{float(user_lon)}"
                f"&daddr={COMPANY_LAT},{COMPANY_LON}"
                "&output=embed"
            )
    except Exception:
        pass
    return f"https://maps.google.com/maps?q={COMPANY_LAT},{COMPANY_LON}&z=16&output=embed"


def attendance_map_card(user_lat, user_lon, dist, direction, hint, show_embed=True):
    dist_text = format_distance_km(dist)
    maps_url = google_maps_direction_url(user_lat, user_lon)
    location_url = f"https://www.google.com/maps/search/?api=1&query={COMPANY_LAT},{COMPANY_LON}"
    embed_url = google_maps_embed_url(user_lat, user_lon)

    st.markdown(f"""
    <div class="att-map-card">
        <h3>🗺️ Selva Motors Direction Map</h3>
        <p>
            Selva Motors location-ku poganum na below direction use pannunga.
            Distance mismatch / outside radius irundha map helpful-aa irukkum.
        </p>
        <div class="att-distance-chip">Distance: {dist_text}</div>
        <p><b>Direction:</b> {direction} — {hint}</p>
        <div class="att-map-actions">
            <a class="att-map-btn" href="{maps_url}" target="_blank">Open Google Maps Direction</a>
            <a class="att-map-btn secondary" href="{location_url}" target="_blank">Open Selva Motors Location</a>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if show_embed:
        st.components.v1.iframe(embed_url, height=310, scrolling=False)



def extract_gps_from_browser_location(loc):
    try:
        if not loc:
            return None, None, None

        coords = loc.get("coords", loc)
        lat = coords.get("latitude")
        lon = coords.get("longitude")
        accuracy = coords.get("accuracy", "")

        if lat is None or lon is None:
            return None, None, None

        return float(lat), float(lon), accuracy
    except Exception:
        return None, None, None




def save_uploaded_file(uploaded_file, folder=UPLOAD_DIR):
    if uploaded_file is None:
        return ""
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", uploaded_file.name)
    path = folder / f"{app_now().strftime('%Y%m%d%H%M%S')}_{safe}"
    with open(path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return str(path)


# ============================================================
# OCR
# ============================================================
def extract_text_from_pdf(file_path):
    text = ""

    if pdfplumber is not None:
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text += (page.extract_text() or "") + "\n"
        except Exception:
            pass

    if not text.strip() and PyPDF2 is not None:
        try:
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += (page.extract_text() or "") + "\n"
        except Exception:
            pass

    return text.strip()


def extract_text_from_image(file_path):
    if pytesseract is None:
        return ""
    try:
        image = Image.open(file_path)
        return pytesseract.image_to_string(image).strip()
    except Exception:
        return ""


def extract_invoice_text(file_path):
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    if ext in [".jpg", ".jpeg", ".png", ".webp"]:
        return extract_text_from_image(file_path)
    return ""


def get_section(text, start_keywords, end_keywords):
    if not text:
        return ""

    lower_text = text.lower()
    start = -1

    for key in start_keywords:
        pos = lower_text.find(key.lower())
        if pos != -1:
            start = pos
            break

    if start == -1:
        return ""

    end = len(text)
    for key in end_keywords:
        pos = lower_text.find(key.lower(), start + 5)
        if pos != -1:
            end = min(end, pos)

    return text[start:end]


def clean_part_description(line):
    line = str(line or "").strip()
    line = re.sub(r"^\d+\s+", "", line)
    line = re.sub(r"\b[A-Z0-9]{6,}[-_]", "", line)
    line = re.sub(r"\b\d{8}\b", "", line)
    line = re.sub(r"\s+", " ", line).strip()
    return line


def is_total_or_header_line(line):
    lower = str(line or "").lower().strip()
    if not lower:
        return True

    blocked_words = [
        "genuine parts details", "other parts details", "labour details",
        "other labour details", "description of goods", "hsn code",
        "billing", "taxable", "cgst", "sgst", "discount", "rate amount",
        "total value", "uom", "qty", "s.no"
    ]

    if lower == "total":
        return True

    if any(word in lower for word in blocked_words):
        return True

    if re.fullmatch(r"total\s+[\d.,\s]+", lower):
        return True

    return False


def count_genuine_spare_items(text):
    """
    Count actual spare rows only from Genuine Parts Details / Spares Details.
    Algorithm:
    - Take Genuine Parts section only.
    - Count rows starting with serial number: 1, 2, 3...
    - Ignore totals, taxes, mobile, VIN, job card, footer numbers.
    Works for multi-line descriptions like Hero 4T PLUS split into next line.
    """
    section = get_section(
        text,
        ["Genuine Parts Details", "Genuine Part Details", "Spares Details", "Spare Details", "Parts Details"],
        ["Other Parts Details", "Labour Details", "Other Labour Details", "CGST", "SGST", "IGST", "Net Amount", "Round Off", "Invoice Amount", "Total Invoice"]
    )

    if not section:
        return 0

    count = 0
    for line in section.splitlines():
        line = str(line or "").strip()
        if not line or is_total_or_header_line(line):
            continue

        # Real item row starts with serial number.
        # Example:
        # "1"
        # "2 SPDMCYL02SS-HERO 4T ..."
        # Avoid continuation like "10W30..." because digit+letter has no word boundary.
        if re.match(r"^\d+\b", line) and not re.match(r"^\d{4,}", line):
            count += 1

    return count



def extract_genuine_spare_details(text):
    """
    Extract spare item descriptions from Genuine Parts section for preview/debug only.
    Not saved as a separate Google Sheets field; the normalized invoice row stores only the approved summary values.
    """
    section = get_section(
        text,
        ["Genuine Parts Details", "Genuine Part Details", "Spares Details", "Spare Details", "Parts Details"],
        ["Other Parts Details", "Labour Details", "Other Labour Details", "CGST", "SGST", "IGST", "Net Amount", "Round Off", "Invoice Amount", "Total Invoice"]
    )

    if not section:
        return []

    items = []
    current = ""
    for line in section.splitlines():
        line = str(line or "").strip()
        if not line or is_total_or_header_line(line):
            continue

        if re.match(r"^\d+\b", line) and not re.match(r"^\d{4,}", line):
            if current:
                items.append(clean_part_description(current))
            current = re.sub(r"^\d+\s*", "", line).strip()
        else:
            if current and not re.match(r"^Total\b", line, flags=re.I):
                current += " " + line

    if current:
        items.append(clean_part_description(current))

    return items[:20]


def detect_oil(text):
    """
    Detect Hero engine oil internally.
    Supports:

    SPDMCYL02SS-HERO 4T PLUS 10W30 SL MA2 (900 ML)
    SPDMCYL09SS-HERO 4T PLUS 10W30 SL MA2 (1000 ML)
    SPDSCOT01SS-HERO 4T PLUS 10W30 SL MB (800 ML)

    Returns:
        (1, "-") if oil found
        (0, "-") if oil not found
    """

    if not text:
        return 0, "-"

    flat = re.sub(r"\s+", " ", str(text)).upper()

    oil_patterns = [

        # Exact Hero Oil Part Numbers
        r"SPDMCYL02SS",
        r"SPDMCYL09SS",
        r"SPDSCOT01SS",

        # Full Oil Descriptions
        r"HERO\s*4T\s*PLUS\s*10W30\s*ML\s*MA2",
        r"HERO\s*4T\s*PLUS\s*10W30\s*SL\s*MA2",
        r"HERO\s*4T\s*PLUS\s*10W30\s*SL\s*MB",

        # Generic Keywords
        r"HERO\s*4T\s*PLUS",
        r"10W30\s*SL\s*MA2",
        r"10W30\s*SL\s*MB",
        r"ENGINE\s*OIL"
    ]

    for pat in oil_patterns:
        if re.search(pat, flat, flags=re.I):
            return 1, "-"

    return 0, "-"


def section_total_amount(section):
    """
    Extract dark final amount from section Total row.
    For Hero invoice tables this is the last number in the Total row:
    Genuine Parts Total -> Spare Amount
    Labour Details Total -> Labour Amount
    Other Labour Details Total -> Other Labour Amount
    """
    if not section:
        return 0.0

    lines = [str(x or "").strip() for x in section.splitlines() if str(x or "").strip()]
    total_lines = [line for line in lines if re.match(r"^Total\b", line, flags=re.I)]

    if total_lines:
        # Use the last Total line inside that section.
        line = total_lines[-1]
        nums = re.findall(r"\d+(?:,\d+)*(?:\.\d+)?", line)
        if nums:
            return to_float(nums[-1])

    return 0.0


def section_amount(section):
    # Backward-compatible wrapper
    return section_total_amount(section)


def extract_spare_total(text):
    section = get_section(
        text,
        ["Genuine Parts Details", "Genuine Part Details", "Spares Details", "Spare Details", "Parts Details"],
        ["Other Parts Details", "Labour Details", "Other Labour Details", "CGST", "SGST", "IGST", "Net Amount", "Round Off", "Invoice Amount", "Total Invoice"]
    )
    return round(section_total_amount(section), 2)


def extract_labour_total(text):
    """
    Labour Amount = Labour Details final dark Total Amount + Other Labour Details final dark Total Amount.
    Supports CGST/SGST and IGST invoices.
    """
    labour_section = get_section(
        text,
        ["Labour Details", "Labor Details"],
        ["Other Labour Details", "Other Labor Details", "CGST", "SGST", "IGST", "Net Amount", "Round Off", "Invoice Amount", "Total Invoice"]
    )

    other_section = get_section(
        text,
        ["Other Labour Details", "Other Labor Details"],
        ["CGST", "SGST", "IGST", "Net Amount", "Round Off", "Invoice Amount", "Total Invoice"]
    )

    return round(section_total_amount(labour_section) + section_total_amount(other_section), 2)


def extract_invoice_amount(text):
    """
    Extract invoice payable / total invoice value.
    Supports comma values like 2,599.00.
    """
    flat = re.sub(r"\s+", " ", str(text or ""))

    return to_float(find_one([
        r"Total\s*Invoice\s*Value\s*\(In figure\)\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
        r"Total\s*Invoice\s*Value\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
        r"Invoice\s*Amount\s*Payable\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
        r"Invoice\s*Amt\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
        r"Net\s*Amount\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
        r"Grand\s*Total\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)"
    ], flat))




def parse_invoice(text):
    """
    Hero invoice parser.
    Saves only clean business fields.
    Does not save raw OCR, source file, confidence, GST, mobile, VIN, jobcard last 8.
    """
    flat = re.sub(r"\s+", " ", text)

    invoice_no = find_one([
        r"Invoice\s*(?:No|Number)?\s*[:\-]?\s*([A-Z0-9\-\/]+)",
        r"Bill\s*(?:No|Number)?\s*[:\-]?\s*([A-Z0-9\-\/]+)"
    ], flat)

    job_card_no = find_one([
        r"Job\s*Card\s*(?:No|Number)?\s*[:\-]?\s*([A-Z0-9\-\/]+)",
        r"JC\s*(?:No)?\s*[:\-]?\s*([A-Z0-9\-\/]+)"
    ], flat)

    reg_no = find_one([
        r"Vehicle\s*(?:Reg|Registration)?\s*(?:No|Number)?\s*[:\-]?\s*([A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{3,4})",
        r"Reg\s*(?:No|Number)?\s*[:\-]?\s*([A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{3,4})",
        r"\b([A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{3,4})\b"
    ], flat)

    reg_no = str(reg_no or "").strip()

    if not reg_no:
        reg_no = "FR"

    bike_model = find_one([
        r"Model\s*[:\-]?\s*([A-Za-z0-9 +._-]{2,45})\s+VIN\b",
        r"Vehicle\s*Model\s*[:\-]?\s*([A-Za-z0-9 +._-]{2,45})",
        r"Model\s*[:\-]?\s*([A-Za-z0-9 +._-]{2,45})"
    ], flat)

    customer_name = find_one([
        r"Customer\s*Name\s*[:\-]?\s*([A-Za-z .]{2,45})\s+Invoice\s*No",
        r"Customer\s*Name\s*[:\-]?\s*([A-Za-z .]{2,45})",
        r"Name\s*[:\-]?\s*([A-Za-z .]{2,45})"
    ], flat)

    oil_count, _oil_details = detect_oil(text)
    oil_status = "Yes" if oil_count > 0 else "No"

    strong_job = strong_extract_jobcard(text)
    strong_reg = strong_extract_reg_no(text)
    if strong_job and not str(job_card_no or "").strip():
        job_card_no = strong_job
    if strong_reg and not str(reg_no or "").strip():
        reg_no = strong_reg

    return {
        "Customer Name": clean_customer_name(customer_name),
        "Invoice Number": str(invoice_no or "").strip().upper().replace(" ", ""),
        "Job Card Number": str(job_card_no or "").strip().upper().replace(" ", ""),
        "Registration Number": clean_reg_no(reg_no),
        "Bike Model": clean_bike_model(bike_model),
        "Labour Amount": extract_labour_total(text),
        "Spare Parts Count": count_genuine_spare_items(text),
        "Spare Amount": extract_spare_total(text),
        "Oil Change Status": oil_status,
        "Total Amount": extract_invoice_amount(text),
    }



def normalize_invoice_jobcard_no(value):
    """
    Strict Job Card duplicate compare normalizer.
    Only real full job card numbers are returned.
    Blank, nan, none, '-', invoice-only values are ignored.
    """
    text = str(value or "").strip().upper()
    text = text.replace("\u00a0", "")
    text = re.sub(r"\s+", "", text)
    text = text.strip(":-_/|., ")

    if text in ["", "-", "NAN", "NONE", "NULL", "0"]:
        return ""

    return text


def save_invoice_entry_from_data(data, entry_type="OCR Upload"):
    entry_id = "E-" + uuid.uuid4().hex[:8].upper()
    saved = append_row("invoices", {
        "Entry ID": entry_id,
        "Date": today_str(),
        "Technician Name": st.session_state.get("employee_name", data.get("Technician Name", "")),
        "User ID": st.session_state.get("user_id", data.get("User ID", "")),
        "Invoice Number": data.get("Invoice Number", ""),
        "Job Card Number": data.get("Job Card Number", ""),
        "Registration Number": data.get("Registration Number", ""),
        "Bike Model": clean_bike_model(data.get("Bike Model", "")),
        "Service Type": data.get("Service Type", strong_detect_service_type(str(data))),
        "Labour Amount": data.get("Labour Amount", 0),
        "Spare Parts Count": data.get("Spare Parts Count", 0),
        "Spare Amount": data.get("Spare Amount", 0),
        "Oil Change Status": data.get("Oil Change Status", "No"),
        "Total Amount": data.get("Total Amount", 0),
        "Entry Type": entry_type,
        "Status": "Active"
    })
    return entry_id if saved else None



def processing_wait_3s(message="Processing entry"):
    box = st.empty()
    box.info(f"{message}... Please wait")
    return box



def require_hero_show(page_key, button_text, loading_text="Loading..."):
    session_key = f"hero_show_unlocked_{page_key}"
    if not st.session_state.get(session_key, False):
        st.markdown("""
        <div class="cloud-view-panel">
            <h3>HERO SHOW</h3>
            <p>🅲🅻🅸🅲🅺 🅷🅴🆁🅴 
                      🔻 </p>
        </div>
        """, unsafe_allow_html=True)
        if st.button(button_text, use_container_width=True, key=f"{page_key}_hero_show_button"):
            st.session_state[session_key] = True
            st.rerun()
        return False
    st.info(loading_text)
    return True


def hero_loading_overlay(message="Loading...", wait_text="Please wait"):
    st.markdown(f"""
    <style>
    .hero-fullscreen-wait {{
        position: fixed !important;
        inset: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
        z-index: 2147483647 !important;
        display:flex !important;
        align-items:center !important;
        justify-content:center !important;
        background: linear-gradient(135deg, rgba(255,255,255,.98), rgba(255,241,242,.98)) !important;
        backdrop-filter: blur(10px) !important;
    }}
    .hero-wait-card {{
        width:min(460px,92vw);
        padding:36px 30px;
        border-radius:34px;
        background:#fff;
        border:2px solid #fecaca;
        box-shadow:0 32px 95px rgba(127,29,29,.28);
        text-align:center;
        font-family:Arial,sans-serif;
    }}
    .hero-wait-logo {{
        color:#e31837;
        font-size:56px;
        font-weight:1000;
        letter-spacing:3px;
        margin-bottom:18px;
        animation:heroPulse 1.1s infinite ease-in-out;
    }}
    .hero-wait-spinner {{
        width:72px;
        height:72px;
        border:7px solid #fee2e2;
        border-top:7px solid #e31837;
        border-radius:999px;
        margin:0 auto 20px auto;
        animation:heroSpin .75s linear infinite;
    }}
    .hero-wait-title {{
        font-size:20px;
        font-weight:900;
        color:#111827;
    }}
    .hero-wait-sub {{
        color:#4b5563;
        font-size:14px;
        margin-top:10px;
        font-weight:650;
    }}
    .hero-wait-time {{
        display:inline-block;
        margin-top:16px;
        padding:9px 14px;
        border-radius:999px;
        background:#fff1f2;
        color:#991b1b;
        border:1px solid #fecdd3;
        font-weight:900;
        font-size:14px;
    }}
    @keyframes heroSpin {{ from {{ transform: rotate(0deg); }} to {{ transform: rotate(360deg); }} }}
    @keyframes heroPulse {{ 0%,100% {{ transform: scale(1); opacity:1; }} 50% {{ transform: scale(1.08); opacity:.76; }} }}
    </style>
    <div class="hero-fullscreen-wait">
      <div class="hero-wait-card">
        <div class="hero-wait-logo">HERO</div>
        <div class="hero-wait-spinner"></div>
        <div class="hero-wait-title">{message}</div>
        <div class="hero-wait-sub">{wait_text}</div>
        <div class="hero-wait-time">Expected waiting time: 2 - 10 seconds</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


    st.markdown(f"""
    <style>
    .hero-fullscreen-wait {{
        position: fixed !important;
        inset: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
        z-index: 2147483647 !important;
        display:flex !important;
        align-items:center !important;
        justify-content:center !important;
        background: linear-gradient(135deg, rgba(255,255,255,.98), rgba(255,241,242,.98)) !important;
        backdrop-filter: blur(10px) !important;
    }}
    .hero-wait-card {{
        width:min(460px,92vw);
        padding:36px 30px;
        border-radius:34px;
        background:#fff;
        border:2px solid #fecaca;
        box-shadow:0 32px 95px rgba(127,29,29,.28);
        text-align:center;
        font-family:Arial,sans-serif;
    }}
    .hero-wait-logo {{ color:#e31837; font-size:56px; font-weight:1000; letter-spacing:3px; margin-bottom:18px; animation:heroPulse 1.1s infinite ease-in-out; }}
    .hero-wait-spinner {{ width:72px; height:72px; border:7px solid #fee2e2; border-top:7px solid #e31837; border-radius:999px; margin:0 auto 20px auto; animation:heroSpin .75s linear infinite; }}
    .hero-wait-title {{ font-size:20px; font-weight:900; color:#111827; }}
    .hero-wait-sub {{ color:#4b5563; font-size:14px; margin-top:10px; font-weight:650; }}
    .hero-wait-time {{ display:inline-block; margin-top:16px; padding:9px 14px; border-radius:999px; background:#fff1f2; color:#991b1b; border:1px solid #fecdd3; font-weight:900; font-size:14px; }}
    @keyframes heroSpin {{ from {{ transform: rotate(0deg); }} to {{ transform: rotate(360deg); }} }}
    @keyframes heroPulse {{ 0%,100% {{ transform: scale(1); opacity:1; }} 50% {{ transform: scale(1.08); opacity:.76; }} }}
    </style>
    <div class="hero-fullscreen-wait">
      <div class="hero-wait-card">
        <div class="hero-wait-logo">HERO</div>
        <div class="hero-wait-spinner"></div>
        <div class="hero-wait-title">{message}</div>
        <div class="hero-wait-sub">{wait_text}</div>
        <div class="hero-wait-time">Expected waiting time: 2 - 10 seconds</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


def hero_waiting_loader(message="Saving to Google Sheet", seconds=0):
    hero_loading_overlay(message, "Please wait")



def create_qr_image(text):
    qr = qrcode.make(text)
    path = PDF_DIR / f"qr_{uuid.uuid4().hex[:8]}.png"
    qr.save(path)
    return str(path)


def generate_manual_bill_pdf(customer_name, reg_no, bike_model, spare_rows, labour_amount, service_type):
    bill_id = "MB-" + app_now().strftime("%Y%m%d%I%M%S%p")
    pdf_path = PDF_DIR / f"{bill_id}.pdf"

    technician_name = st.session_state.get("employee_name", "")

    customer_name = clean_customer_name(customer_name)
    reg_no = clean_reg_no(reg_no)
    bike_model = clean_bike_model(bike_model)

    spare_total = sum(float(row["Amount"]) for row in spare_rows)
    labour_amount = float(labour_amount)
    total_amount = round(spare_total + labour_amount, 2)

    spare_count = len([row for row in spare_rows if str(row["Spare Name"]).strip()])
    oil_count = sum(
        1 for row in spare_rows
        if re.search(r"Hero\s*4T\s*PLUS|\boil\b", str(row["Spare Name"]), flags=re.I)
    )

    qr_path = create_qr_image(f"Manual Bill: {bill_id}, Reg: {reg_no}, Service Type: {service_type}, Total: {total_amount}")

    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    w, h = A4
    page_no = 1

    draw_pdf_header(
        c, w, h,
        title="Manual Bill",
        subtitle="Authorised Service Bill",
        right_line1=f"Bill ID: {bill_id}",
        right_line2=f"Date: {today_str()}"
    )

    y = h - 145

    # Top info boxes
    pdf_label_value_box(c, 38, y, 165, "Customer Name", customer_name)
    pdf_label_value_box(c, 218, y, 145, "Registration No", reg_no)
    pdf_label_value_box(c, 378, y, 175, "Service Type", service_type, "#FFF1F2")

    y -= 62
    pdf_label_value_box(c, 38, y, 165, "Technician", technician_name)
    pdf_label_value_box(c, 218, y, 145, "Bike Model", bike_model)
    pdf_label_value_box(c, 378, y, 175, "Document", "Manual Service Bill", "#F8FAFC")

    y -= 72

    # Section title
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(38, y, "Spare Parts Details")
    y -= 20

    # Table header
    table_x = 38
    table_w = w - 76
    c.setFillColor(colors.HexColor("#111827"))
    c.roundRect(table_x, y - 6, table_w, 22, 7, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 8)

    col_x = [48, 92, 330, 390, 465]
    headers = ["S.No", "Spare Name", "Qty", "Rate", "Amount"]
    for head, x in zip(headers, col_x):
        c.drawString(x, y, head)

    y -= 24
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.black)

    serial = 1
    for row in spare_rows:
        if not str(row["Spare Name"]).strip():
            continue

        if y < 150:
            draw_pdf_footer(c, w, page_no)
            c.showPage()
            page_no += 1
            draw_pdf_header(c, w, h, "Manual Bill", "Authorised Service Bill", f"Bill ID: {bill_id}", f"Date: {today_str()}")
            y = h - 150

        if serial % 2 == 1:
            c.setFillColor(colors.HexColor("#F8FAFC"))
            c.roundRect(table_x, y - 6, table_w, 17, 4, fill=True, stroke=False)
            c.setFillColor(colors.black)

        c.drawString(50, y, str(serial))
        c.drawString(92, y, str(row["Spare Name"])[:38])
        c.drawString(330, y, str(row["Qty"]))
        c.drawString(390, y, f"Rs.{float(row['Rate']):.2f}")
        c.drawString(465, y, f"Rs.{float(row['Amount']):.2f}")
        y -= 18
        serial += 1

    # Amount summary
    y -= 16
    summary_y = max(y, 205)
    summary_x = 330
    c.setFillColor(colors.HexColor("#FFF1F2"))
    c.roundRect(summary_x, summary_y - 92, 225, 96, 12, fill=True, stroke=False)

    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(summary_x + 14, summary_y - 20, f"Spare Amount: Rs.{spare_total:.2f}")
    c.drawString(summary_x + 14, summary_y - 42, f"Labour Amount: Rs.{labour_amount:.2f}")

    c.setFillColor(colors.HexColor("#E31837"))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(summary_x + 14, summary_y - 70, f"Total Amount: Rs.{total_amount:.2f}")

    # QR
    try:
        c.drawImage(qr_path, 45, 85, width=70, height=70)
        c.setFillColor(colors.HexColor("#64748B"))
        c.setFont("Helvetica", 7)
        c.drawString(45, 74, "QR Verification")
    except Exception:
        pass


    # Customer signature section
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(160, 105, "Customer Signature")
    c.setStrokeColor(colors.HexColor("#111827"))
    c.line(145, 88, 305, 88)
    c.setFillColor(colors.HexColor("#64748B"))
    c.setFont("Helvetica", 8)
    c.drawString(170, 73, "Customer Acknowledgement")

    # Signature
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(385, 105, "For SELVA MOTORS")
    c.setStrokeColor(colors.HexColor("#111827"))
    c.line(365, 88, 525, 88)
    c.setFillColor(colors.HexColor("#64748B"))
    c.setFont("Helvetica", 8)
    c.drawString(392, 73, "Authorised Signatory")

    draw_pdf_footer(c, w, page_no)
    c.save()

    saved_to_sheets = append_row("manual_invoices", {
        "Manual Bill ID": bill_id,
        "Date": today_str(),
        "Technician Name": technician_name,
        "User ID": "",
        "Customer Name": customer_name,
        "Registration Number": reg_no,
        "Bike Model": bike_model,
        "Service Type": service_type,
        "Labour Amount": labour_amount,
        "Spare Parts Count": spare_count,
        "Oil Count": oil_count,
        "Total Amount": total_amount,
        "PDF File": str(pdf_path),
        "Status": "Generated"
    })
    if not saved_to_sheets:
        raise RuntimeError("Google Sheets did not confirm the manual_invoices record append.")

    return str(pdf_path)


# ============================================================
# LOGIN
# ============================================================
def page_login():
    logo_b64 = get_hero_logo_base64()
    logo_html = f'<img class="hero-login-logo-img" src="{logo_b64}" />' if logo_b64 else '<div style="font-size:42px;text-align:center;font-weight:900;color:#e31837;">HERO</div>'

    st.markdown(f"""
    <div class="login-wrap">
        <div class="login-hero">
            <div class="hero-login-panel">
                {logo_html}
                <div class="hero-connect-title">Hero Connect</div>
                <div class="hero-login-status-badge">SELVA MOTORS ERP • SECURE ACCESS</div>
                <div class="feature-strip" style="justify-content:center;margin-bottom:18px;">
                    <div class="feature-pill">Google Sheet Only</div>
                    <div class="feature-pill">Service ERP</div>
                    <div class="feature-pill">Selva Motors</div>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 1.05, 1])
    with c2:
        user_id = st.text_input("User ID", value=st.session_state.get("remembered_user_id", ""), placeholder="Enter user id")
        password = st.text_input("Password", type="password", placeholder="Enter password")
        remember = st.checkbox("Remember my User ID", value=False)

        if st.button("Login", use_container_width=True):
            user = login_user(user_id, password)
            if user:
                if remember:
                    st.session_state["remembered_user_id"] = user_id
                else:
                    st.session_state.pop("remembered_user_id", None)
                st.session_state["logged_in"] = True
                st.session_state["user_id"] = user["User ID"]
                st.session_state["employee_name"] = user["Employee Name"]
                st.session_state["role"] = user["Role"]
                st.success("Login success")
                st.rerun()
            else:
                st.error("Invalid login")

        st.markdown("<div class='hero-login-note'>HTML5 Browser Compatibility ✓ &nbsp; | &nbsp; Professional Hero Portal UI • Animated Experience</div>", unsafe_allow_html=True)






@st.cache_data(ttl=20, show_spinner=False)
# ============================================================
# HERO EXTREME UI HELPERS
# ============================================================
def hero_badge(text):
    return f"<span class='status-chip'>⚡ {text}</span>" if text else ""


def page_hero(title, subtitle, chip=""):
    """Compatibility wrapper for the shared Hero page-header component."""
    render_page_header(title, subtitle, chip)


def quick_card(title, body, icon="✨"):
    st.markdown(f"""
    <div class="quick-card">
        <h3>{icon} {title}</h3>
        <p>{body}</p>
    </div>
    """, unsafe_allow_html=True)


def preview_item(label, value):
    st.markdown(f"""
    <div class="preview-item">
        <b>{label}</b>
        <span>{value}</span>
    </div>
    """, unsafe_allow_html=True)



def ultra_card(label, value, note="", icon=""):
    st.markdown(f"""
    <div class="ultra-card">
        <div class="label">{icon} {label}</div>
        <div class="value">{value}</div>
        <div class="note">{note}</div>
    </div>
    """, unsafe_allow_html=True)


def ultra_status(title, body):
    st.markdown(f"""
    <div class="ultra-status">
        <h3>{title}</h3>
        <p>{body}</p>
    </div>
    """, unsafe_allow_html=True)


def status_badge(text, kind="green"):
    cls = {
        "green": "badge-green",
        "red": "badge-red",
        "yellow": "badge-yellow",
        "blue": "badge-blue"
    }.get(kind, "badge-green")
    return f"<span class='{cls}'>{text}</span>"



def erp_card(label, value, note="", icon=""):
    st.markdown(f"""
    <div class="erp-card">
        <small>{icon} {label}</small>
        <h3>{value}</h3>
        <span>{note}</span>
    </div>
    """, unsafe_allow_html=True)


def premium_panel(title, subtitle=""):
    st.markdown(f"""
    <div class="premium-title-card">
        <h2>{title}</h2>
        <p>{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)


def status_pill(text, kind="ok"):
    cls = {
        "ok": "status-ok",
        "warn": "status-warn",
        "danger": "status-danger",
        "info": "status-info"
    }.get(kind, "status-ok")
    return f"<span class='status-pill {cls}'>{text}</span>"



def pro_alert_bar(items):
    html = "<div class='pro-alert-bar'>"
    for title, value in items:
        html += f"<div class='pro-alert'><b>{title}</b><span>{value}</span></div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def quick_action_grid(items):
    html = "<div class='quick-action-grid'>"
    for title, body, icon in items:
        html += f"<div class='quick-action'><h3>{icon} {title}</h3><p>{body}</p></div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def service_timeline():
    st.markdown("""
    <div class="timeline">
        <span>Received</span>
        <span>Work Started</span>
        <span>Billing Done</span>
        <span>Delivered</span>
    </div>
    """, unsafe_allow_html=True)


def ocr_stepper(active="Ready"):
    steps = ["Upload", "Reading", "Extracting", "Preview", "Save"]
    html = "<div class='stepper'>"
    for s in steps:
        cls = "step active" if s == active else "step"
        html += f"<span class='{cls}'>{s}</span>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)



def draw_hero_logo_on_pdf(c, x, y, width=110, height=38):
    """
    Draw Hero logo image in ReportLab PDF if available.
    Uses embedded/base64 logo helper through a temp file fallback.
    """
    try:
        logo_b64 = get_hero_logo_base64()
        if not logo_b64:
            return False
        temp_logo = PDF_DIR / "hero_pdf_logo_temp.jpg"
        if not temp_logo.exists():
            import base64 as _b64
            temp_logo.write_bytes(_b64.b64decode(logo_b64))
        c.drawImage(str(temp_logo), x, y, width=width, height=height, preserveAspectRatio=True, mask='auto')
        return True
    except Exception:
        return False


def optimal_v4_note(title, body):
    st.markdown(f"""
    <div class="optimal-v4-note">
        <b>{title}</b><br>{body}
    </div>
    """, unsafe_allow_html=True)


def mobile_action_card(title, body, icon="⚡"):
    st.markdown(f"""
    <div class="mobile-action-card">
        <h3>{icon} {title}</h3>
        <p>{body}</p>
    </div>
    """, unsafe_allow_html=True)


def strong_extract_reg_no(text):
    flat = re.sub(r"\\s+", " ", str(text or "").upper())
    patterns = [
        r"\\b(TN\\s?\\d{1,2}\\s?[A-Z]{1,3}\\s?\\d{3,4})\\b",
        r"\\b([A-Z]{2}\\s?\\d{1,2}\\s?[A-Z]{1,3}\\s?\\d{3,4})\\b"
    ]
    for p in patterns:
        m = re.search(p, flat)
        if m:
            return clean_reg_no(m.group(1))
    return ""


def strong_extract_jobcard(text):
    flat = re.sub(r"\\s+", " ", str(text or "").upper())
    patterns = [
        r"JOB\\s*CARD\\s*(?:NO|NUMBER)?\\s*[:\\-]?\\s*([0-9]{4,8}\\-[0-9]{2}\\-[A-Z]{2,4}\\-[0-9]{3,6}\\-[0-9]{2,6})",
        r"\\b([0-9]{4,8}\\-[0-9]{2}\\-[A-Z]{2,4}\\-[0-9]{3,6}\\-[0-9]{2,6})\\b"
    ]
    for p in patterns:
        m = re.search(p, flat)
        if m:
            return m.group(1).strip()
    return ""


def strong_detect_service_type(text):
    flat = re.sub(r"\\s+", " ", str(text or "").upper())
    if "JOY" in flat or "JOYRIDE" in flat:
        return "Joyride"
    if "ACCIDENT" in flat or "INSURANCE" in flat:
        return "Accident"
    if re.search(r"\\bFSC\\b|FREE\\s*SERVICE", flat):
        return "FSC"
    if "GENERAL" in flat:
        return "General"
    return "Paid Service"



def make_circle_hero_logo_for_pdf(size=230):
    """
    Creates a zoomed circular Hero logo PNG for professional PDF headers.
    The logo is slightly zoomed/cropped so it is clearly visible inside the circle.
    Cached file is reused for faster PDF generation.
    """
    out_path = PDF_DIR / "hero_circle_logo_pdf_zoom.png"
    try:
        if out_path.exists() and out_path.stat().st_size > 0:
            return str(out_path)
    except Exception:
        pass

    try:
        logo_b64 = get_hero_logo_base64()
        if not logo_b64:
            return ""

        import base64 as _b64
        import io as _io
        from PIL import Image as _Image, ImageOps as _ImageOps, ImageDraw as _ImageDraw

        raw = _b64.b64decode(logo_b64)
        img = _Image.open(_io.BytesIO(raw)).convert("RGBA")

        # Remove transparent/empty border if any
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)

        # White round canvas
        canvas_img = _Image.new("RGBA", (size, size), (255, 255, 255, 255))

        # Zoom factor: larger than circle inner area so logo fills circle better
        logo_target = int(size * 1.08)
        logo_fit = _ImageOps.contain(img, (logo_target, logo_target))

        # Center crop if fitted logo exceeds canvas
        x = (size - logo_fit.width) // 2
        y = (size - logo_fit.height) // 2
        canvas_img.alpha_composite(logo_fit, (x, y))

        # Circular mask
        mask = _Image.new("L", (size, size), 0)
        draw = _ImageDraw.Draw(mask)
        draw.ellipse((2, 2, size - 2, size - 2), fill=255)

        circle = _Image.new("RGBA", (size, size), (255, 255, 255, 0))
        circle.paste(canvas_img, (0, 0), mask)

        # Red outer border + soft inner border
        border = _ImageDraw.Draw(circle)
        border.ellipse((3, 3, size - 3, size - 3), outline=(227, 24, 55, 255), width=9)
        border.ellipse((13, 13, size - 13, size - 13), outline=(255, 228, 232, 255), width=3)

        circle.save(out_path)
        return str(out_path)
    except Exception:
        return ""

        
def draw_pdf_header(c, w, h, title, subtitle="", right_line1="", right_line2=""):
    """
    White background and Pure Black Text header for clear printouts.
    """
    # 1. Background-a White aakidrom
    c.setFillColor(colors.white)
    c.rect(0, h - 112, w, 112, fill=True, stroke=False)
    
    # Left side-la oru chinna red design line
    c.setFillColor(colors.HexColor("#E31837"))
    c.rect(0, h - 112, 14, 112, fill=True, stroke=False)

    # Circle logo
    logo_path = make_circle_hero_logo_for_pdf()
    if logo_path:
        c.drawImage(logo_path, 32, h - 98, width=68, height=68, mask="auto")
    else:
        c.setFillColor(colors.black)
        c.circle(66, h - 64, 34, fill=True, stroke=False)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(66, h - 69, "HERO")

    # 2. Company Name & Details - Pure Black Text
    c.setFillColor(colors.black) # PURE BLACK COLOR
    c.setFont("Helvetica-Bold", 18)
    c.drawString(115, h - 45, "SELVA MOTORS")

    c.setFont("Helvetica", 8)
    c.drawString(115, h - 61, "KATCHANAM MAIN ROAD, KILVELUR")
    c.drawString(115, h - 76, subtitle or "Authorised Hero Service Document")

    # 3. Right side Title & Date - Pure Black Text
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 15)
    c.drawRightString(w - 36, h - 42, title)
    
    c.setFont("Helvetica", 8)
    if right_line1:
        c.drawRightString(w - 36, h - 60, right_line1)
    if right_line2:
        c.drawRightString(w - 36, h - 76, right_line2)

    # Bottom Divider line
    c.setStrokeColor(colors.HexColor("#E31837"))
    c.setLineWidth(2)
    c.line(34, h - 116, w - 34, h - 116)

def pdf_label_value_box(c, x, y, width, label, value, accent="#F8FAFC"):
    c.setFillColor(colors.HexColor(accent))
    c.roundRect(x, y - 44, width, 44, 10, fill=True, stroke=False)
    c.setFillColor(colors.HexColor("#64748B"))
    c.setFont("Helvetica-Bold", 7)
    c.drawString(x + 10, y - 15, str(label).upper())
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x + 10, y - 32, str(value)[:30])


def draw_pdf_footer(c, w, page_no=None):
    c.setStrokeColor(colors.HexColor("#E5E7EB"))
    c.setLineWidth(1)
    c.line(34, 48, w - 34, 48)

    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(38, 32, "For SELVA MOTORS")

    c.setFillColor(colors.HexColor("#64748B"))
    c.setFont("Helvetica", 8)
    footer_text = "Generated by Selva Motors ERP"
    if page_no is not None:
        footer_text += f"  |  Page {page_no}"
    c.drawRightString(w - 38, 32, footer_text)




def clear_pdf_logo_cache():
    try:
        (PDF_DIR / "hero_circle_logo_pdf_zoom.png").unlink(missing_ok=True)
        (PDF_DIR / "hero_circle_logo_pdf.png").unlink(missing_ok=True)
        (PDF_DIR / "hero_pdf_logo_temp.jpg").unlink(missing_ok=True)
        return True
    except Exception:
        return False


# ============================================================
# DASHBOARD
# ============================================================


def gps_refresh_box():
    st.markdown("""
    <div class="gps-refresh-card">
        <b>📍 GPS Location Not Detected</b><br>
        <span style="color:#64748b;font-size:13px;">Browser location permission ON pannitu Refresh Location click pannunga.</span>
    </div>
    """, unsafe_allow_html=True)
    if st.button("🔄 Refresh Location", use_container_width=False, key="gps_refresh_small_btn"):
        st.rerun()


# ============================================================
# ATTENDANCE
# ============================================================

# ============================================================
# UPLOAD INVOICE
# ============================================================
def page_upload_invoice():
    page_hero("AI Invoice OCR Upload", "Upload invoice, verify clean view-only preview, then proceed the entry.", "OCR")
    ocr_stepper("Upload")
    st.caption("OCR Preview is view-only. This page does not read existing invoice records.")

    st.markdown("<div class='service-type-panel'><b>Service Type Required</b><br><span style='color:#64748b;font-size:13px;'>Select the service type before saving. The entry is written directly to Google Sheets.</span></div>", unsafe_allow_html=True)
    upload_service_type = st.selectbox("Service Type", ["FSC", "Paid Service", "General", "Joyride", "Accident"], key="upload_service_type")

    uploaded = st.file_uploader("Upload Invoice PDF / Image", type=["pdf", "jpg", "jpeg", "png", "webp"], key="invoice_uploader")

    if uploaded:
        file_path = None
        try:
            # The loader covers the existing upload + OCR extraction stage only.
            # OCR parsing itself is unchanged; the loader is cleared on every exit.
            with show_hero_invoice_loader():
                file_path = save_uploaded_file(uploaded)
                text = extract_invoice_text(file_path)
        except Exception:
            st.error("Invoice processing failed. Please check the file and try uploading it again.")
            return
        finally:
            # Preserve the existing temporary-file cleanup, including error paths.
            if file_path:
                try:
                    Path(file_path).unlink(missing_ok=True)
                except Exception:
                    pass

        if not text.strip():
            st.error("OCR text not detected. For scanned PDF/image, install Tesseract OCR or upload clearer file.")
            return

        parsed = parse_invoice(text)
        parsed["Service Type"] = upload_service_type
        st.session_state["ocr_preview"] = parsed

    if "ocr_preview" not in st.session_state:
        return

    data = st.session_state["ocr_preview"]
    data["Service Type"] = upload_service_type
    st.session_state["ocr_preview"] = data

    ocr_stepper("Preview")
    st.markdown("<div class='section-title'>View Only OCR Preview</div>", unsafe_allow_html=True)

    dup_badge = status_badge("Ready to save", "green")
    st.markdown(f"""
    <div class="invoice-preview-pro">
        <div class="invoice-preview-head">
            <h2>OCR Entry Preview {dup_badge}</h2>
            <p>View-only clean data. Spare item names and oil item names are hidden. Saving writes a new row directly to Google Sheets.</p>
        </div>
        <div class="invoice-preview-body">
            <div class="invoice-field"><b>Invoice / Job Card No</b><span>{data.get("Invoice Number", "")}</span></div>
            <div class="invoice-field"><b>Registration Number</b><span>{data.get("Registration Number", "")}</span></div>
            <div class="invoice-field"><b>Bike Model</b><span>{data.get("Bike Model", "")}</span></div>
            <div class="invoice-field"><b>Service Type</b><span>{data.get("Service Type", "")}</span></div>
            <div class="invoice-field"><b>Total Amount</b><span>₹{data.get("Total Amount", 0)}</span></div>
            <div class="invoice-field"><b>Labour Amount</b><span>₹{data.get("Labour Amount", 0)}</span></div>
            <div class="invoice-field"><b>Spare Parts Count</b><span>{data.get("Spare Parts Count", 0)}</span></div>
            <div class="invoice-field"><b>Spare Amount</b><span>₹{data.get("Spare Amount", 0)}</span></div>
            <div class="invoice-field"><b>Oil Change Status</b><span>{data.get("Oil Change Status", "No")}</span></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    preview_df = pd.DataFrame([{
        "Invoice Number": data.get("Invoice Number", ""),
        "Job Card Number": data.get("Job Card Number", ""),
        "Registration Number": data.get("Registration Number", ""),
        "Bike Model": data.get("Bike Model", ""),
        "Service Type": data.get("Service Type", strong_detect_service_type(str(data))),
        "Labour Amount": data.get("Labour Amount", 0),
        "Spare Parts Count": data.get("Spare Parts Count", 0),
        "Spare Amount": data.get("Spare Amount", 0),
        "Oil Change Status": data.get("Oil Change Status", "No"),
        "Total Amount": data.get("Total Amount", 0),
        "Entry Type": "OCR Upload",
        "Status": "Active"
    }])
    st.dataframe(preview_df, use_container_width=True)

    missing = []
    for col in ["Job Card Number", "Registration Number", "Bike Model"]:
        if not str(data.get(col, "")).strip():
            missing.append(col)

    if missing:
        st.warning("Missing detected values: " + ", ".join(missing))
        st.info("Preview is view-only as per requirement. Upload a clearer invoice if values are missing.")

    st.caption(
        "Write-only mode does not check other users' invoice rows. Verify the Job Card Number against the controlled register before saving; cross-device duplicate detection is intentionally unavailable without a Sheets read."
    )

    if st.button("Click to Proceed the Entry", use_container_width=True):
        if missing:
            st.error("Required values missing. Cannot proceed.")
            return

        with st.spinner("Saving invoice directly to Google Sheets. Do not submit again."):
            final_job_card_no = normalize_invoice_jobcard_no(data.get("Job Card Number", ""))
            duplicate_key_value = final_job_card_no or normalize_invoice_jobcard_no(data.get("Invoice Number", ""))
            duplicate_key = f"invoice_jobcard_saved_{st.session_state.get('user_id', '')}_{duplicate_key_value}"
            if duplicate_key_value and st.session_state.get(duplicate_key):
                st.warning("This Job Card / Invoice was already submitted in this signed-in session.")
                return

            saved_entry_id = save_invoice_entry_from_data(data, entry_type="OCR Upload")
            if saved_entry_id:
                if duplicate_key_value:
                    st.session_state[duplicate_key] = saved_entry_id
                st.session_state.pop("ocr_preview", None)
                st.success(f"Invoice entry saved. Entry ID: {saved_entry_id}")
                st.rerun()
            else:
                st.error("Invoice could not be saved. The preview remains available so you can retry after checking the connection.")
                       
# ============================================================
# REPORTS
# ============================================================
# ============================================================
# SEARCH
# ============================================================

# ============================================================
# CUSTOMER SERVICE HISTORY
# ============================================================

# ============================================================
# MANUAL INVOICE GENERATOR
# ============================================================
def page_manual_invoice():
    page_hero("Manual Bill", "Generate professional manual service bill PDF with serial numbered spare rows.", "PDF Bill")
    st.caption("Professional manual bill PDF. Technician name is taken from current logged-in user.")

    c1, c2 = st.columns(2)
    customer_name = c1.text_input("Customer Name")
    reg_no = c2.text_input("Registration Number")
    bike_model = c1.text_input("Bike Model")
    service_type = c2.selectbox("Service Type", ["FSC", "Paid Service", "General", "Joyride", "Accident"])

    st.subheader("Spare Parts Rows")
    row_count = st.number_input("Number of Spare Part Rows", min_value=1, max_value=15, value=3)

    spare_rows = []
    for i in range(int(row_count)):
        c1, c2, c3, c4, c5 = st.columns([1, 3, 1, 1, 1])
        c1.text_input("S.No", value=str(i + 1), key=f"sno_{i}", disabled=True)
        name = c2.text_input(f"Spare Name {i+1}", key=f"spare_name_{i}")
        qty = c3.number_input(f"Qty {i+1}", min_value=0, value=1, key=f"qty_{i}")
        rate = c4.number_input(f"Rate {i+1}", min_value=0.0, value=0.0, key=f"rate_{i}")
        amount = qty * rate
        c5.metric("Amount", f"₹{amount:.2f}")

        spare_rows.append({
            "S.No": i + 1,
            "Spare Name": name,
            "Qty": qty,
            "Rate": rate,
            "Amount": amount
        })

    labour_amount = st.number_input("Labour Amount", min_value=0.0, value=0.0)

    st.markdown("""
    <div class="bill-preview">
        <h2>Live Manual Bill Preview</h2>
        <div class="subtle">PDF will show title as Manual Bill, service type, serial rows, labour amount and logged-in technician name. Total amount will not show in PDF.</div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("Generate Manual Bill PDF", use_container_width=True):
        if not reg_no or not bike_model:
            st.error("Registration Number and Bike Model required.")
            return

        try:
            pdf = generate_manual_bill_pdf(customer_name, reg_no, bike_model, spare_rows, labour_amount, service_type)
        except Exception as exc:
            st.error(f"Manual Bill PDF was created but its Google Sheets record could not be saved: {exc}")
            return
        st.success("Manual Bill PDF generated and its record saved to the Google Sheets manual_invoices worksheet.")

        with open(pdf, "rb") as f:
            st.download_button("Download Manual Bill PDF", f, file_name=Path(pdf).name, mime="application/pdf")


# ============================================================
# DELETE INVOICE REQUEST
# ============================================================


# ============================================================
# CENTRAL GOOGLE SHEETS ACCESS POLICY + APP ROUTING
# ============================================================
import hashlib
import hmac
import secrets

from google_sheet import (
    append_row as sheets_append_row,
    approve_delete_request as sheets_approve_delete_request,
    configure_default_gateway,
    delete_row as sheets_delete_row,
    get_api_call_audit_summary,
    read_sheet as sheets_read_sheet,
    reset_api_call_audit,
    update_range as sheets_update_range,
)
from report_center import render_report_center


def _ensure_sheets_gateway():
    sheet_id = str(st.secrets.get("SHEET_ID", "")).strip()
    configured_id = st.session_state.get("_sheets_gateway_id")
    if configured_id != sheet_id:
        configure_default_gateway(sheet_id, SHEETS)
        st.session_state["_sheets_gateway_id"] = sheet_id


def ensure_local_work_dirs():
    """Create temporary-upload and generated-PDF folders; no business data is stored here."""
    UPLOAD_DIR.mkdir(exist_ok=True)
    PDF_DIR.mkdir(exist_ok=True)


def clear_storage_cache(sheet_name=None):
    """Invalidate only this Streamlit session's report cache after a successful write."""
    cache = st.session_state.get("_report_read_cache", {})
    if sheet_name:
        for key in list(cache):
            if key == sheet_name or key.startswith(f"{sheet_name}|"):
                cache.pop(key, None)
    else:
        cache.clear()
    st.session_state["_report_read_cache"] = cache
    if sheet_name == "invoices":
        for key in ("_report_result_service", "_report_result_daily"):
            st.session_state.pop(key, None)
    elif sheet_name == "attendance":
        st.session_state.pop("_report_result_attendance", None)


def read_sheet(sheet_name):
    """Backend deny-by-default. Normal application pages cannot read business data."""
    _ensure_sheets_gateway()
    return sheets_read_sheet(sheet_name, purpose=None, columns=SHEETS.get(sheet_name, []))


def read_auth_sheet():
    """The sole normal-workflow read: the five employee authentication columns."""
    _ensure_sheets_gateway()
    return sheets_read_sheet("employees", purpose="auth", columns=SHEETS["employees"])


def read_report_sheet(sheet_name, force_refresh=False, columns=None):
    """Read an approved sheet/column set only after an explicit Generate action."""
    if sheet_name not in {"invoices", "attendance"}:
        raise PermissionError("Reports may read only invoices or attendance.")
    if not columns:
        raise PermissionError("Reports must request explicit columns; full-worksheet report reads are blocked.")
    approved_columns = list(columns)
    if any(column not in SHEETS[sheet_name] for column in approved_columns):
        raise PermissionError("This report requested an unapproved worksheet column.")
    _ensure_sheets_gateway()
    cache = st.session_state.setdefault("_report_read_cache", {})
    cache_key = f"{sheet_name}|{'|'.join(approved_columns)}"
    cached = cache.get(cache_key)
    now_ts = time_module.time()
    if not force_refresh and cached and now_ts - cached["cached_at"] <= 45:
        result = cached["frame"].copy()
        result.attrs["sheets_fetched_at"] = cached["fetched_at"]
        result.attrs["sheets_cache_reused"] = True
        return result
    # Remove the expired copy before fetching: a failed fresh read is never shown as fresh.
    cache.pop(cache_key, None)
    frame = sheets_read_sheet(sheet_name, purpose="report", columns=approved_columns)
    fetched_at = app_now().strftime("%d-%m-%Y %I:%M:%S %p IST")
    frame.attrs["sheets_fetched_at"] = fetched_at
    frame.attrs["sheets_cache_reused"] = False
    cache[cache_key] = {"frame": frame.copy(), "cached_at": now_ts, "fetched_at": fetched_at}
    st.session_state["_report_read_cache"] = cache
    return frame.copy()


def append_row(sheet_name, row_dict):
    """Direct append: never read the sheet, concatenate in memory, or clear/rewrite."""
    if sheet_name not in SHEETS:
        st.error(f"Unknown Google Sheet worksheet: {sheet_name}")
        return False
    _ensure_sheets_gateway()
    ok, message = sheets_append_row(sheet_name, row_dict, columns=SHEETS[sheet_name])
    if ok:
        clear_storage_cache(sheet_name)
        st.success("Saved directly to Google Sheets.")
        return True
    st.error(f"Google Sheets save failed: {message}")
    return False


def update_sheet_range(sheet_name, range_name, values):
    _ensure_sheets_gateway()
    ok, message = sheets_update_range(sheet_name, range_name, values)
    if ok:
        clear_storage_cache(sheet_name)
    else:
        st.error(f"Google Sheets update failed: {message}")
    return ok


def delete_sheet_row(sheet_name, row_number):
    _ensure_sheets_gateway()
    ok, message = sheets_delete_row(sheet_name, int(row_number))
    if ok:
        clear_storage_cache(sheet_name)
    else:
        st.error(f"Google Sheets delete failed: {message}")
    return ok


def approve_delete_request(invoice_row, request_row):
    """Atomically delete an invoice and mark its delete-request row approved."""
    _ensure_sheets_gateway()
    ok, message = sheets_approve_delete_request(int(invoice_row), int(request_row), now_stamp())
    if ok:
        clear_storage_cache("invoices")
    else:
        st.error(f"Delete approval failed: {message}")
    return ok


def google_append_row(sheet_name, row_dict):
    # Keep compatibility callers on the same cache-invalidating write path.
    return append_row(sheet_name, row_dict)


def google_write_sheet(*args, **kwargs):
    raise PermissionError(
        "Full-sheet clear/rewrite is disabled. Use append_row() or a narrowly scoped explicit row/range update."
    )


def write_sheet(*args, **kwargs):
    raise PermissionError(
        "Full-sheet replacement is disabled to prevent data loss and unnecessary Google Sheets API calls."
    )


def _password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    iterations = 260_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations, salt.hex(), digest.hex()
    )


def _password_matches(stored: str, supplied: str) -> bool:
    stored = str(stored or "")
    supplied = str(supplied or "")
    if stored.startswith("pbkdf2_sha256$"):
        try:
            _, rounds, salt_hex, digest_hex = stored.split("$", 3)
            actual = hashlib.pbkdf2_hmac(
                "sha256", supplied.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds)
            ).hex()
            return hmac.compare_digest(actual, digest_hex)
        except Exception:
            return False
    # Existing deployed employee rows may still contain legacy plain-text passwords.
    return hmac.compare_digest(stored.encode("utf-8"), supplied.encode("utf-8"))


def login_user(user_id, password):
    """Read employee auth fields once on explicit login; never cache or expose passwords."""
    try:
        users = read_auth_sheet()
    except Exception:
        return None
    required = ["User ID", "Password", "Employee Name", "Role", "Status"]
    for column in required:
        if column not in users.columns:
            users[column] = ""
    requested_id = str(user_id or "").strip().casefold()
    for _, row in users.iterrows():
        current_id = str(row.get("User ID", "")).strip()
        if current_id.casefold() != requested_id:
            continue
        if str(row.get("Status", "")).strip().casefold() != "active":
            return None
        if not _password_matches(row.get("Password", ""), password):
            return None
        # Password is deliberately excluded from the authenticated session object.
        return {
            "User ID": current_id,
            "Employee Name": str(row.get("Employee Name", "")).strip(),
            "Role": str(row.get("Role", "")).strip(),
        }
    return None


def page_dashboard():
    """Static Home screen. Intentionally contains no KPI or business-data reads."""
    render_home_landing(
        st.session_state.get("employee_name", ""),
        st.session_state.get("role", ""),
    )


def page_search():
    st.error("Search is disabled to prevent normal-page Google Sheets reads.")


def page_customer_service_history():
    st.error("Customer service history is disabled. Use the authorized on-demand Reports workflow.")


def page_cloud_excel_view_only():
    st.error("Google Sheet / Excel view-only pages are disabled.")


def page_duplicate_upload_finder():
    st.error("Duplicate upload finder is disabled because it requires a normal business-data read.")


def page_reports():
    render_report_center(
        read_report_sheet=read_report_sheet,
        today_str=today_str,
        pdf_dir=PDF_DIR,
        is_admin=is_admin(),
        is_manager=is_manager(),
        is_technician=is_technician(),
        is_prathisha=is_prathisha(),
        user_id=st.session_state.get("user_id", ""),
        employee_name=st.session_state.get("employee_name", ""),
    )


def page_attendance():
    if not require_hero_show("attendance", "📍 SHOW ATTENDANCE", "GPS attendance is ready"):
        return
    page_hero(
        "Smart Attendance",
        "GPS attendance save only. Existing attendance rows are not read by this page.",
        "Write Only",
    )
    st.caption("Attendance time: India Time • 12-hour AM/PM format")
    user_id = st.session_state.get("user_id", "")
    today = today_str()
    saved_key = f"attendance_saved_{today}_{user_id}"
    if st.session_state.get(saved_key):
        st.success("Attendance was already saved in this signed-in session today.")
        return
    if get_geolocation is None:
        st.error("GPS component is not installed. Install streamlit-js-eval.")
        return
    st.info("Allow browser location. Attendance is saved only when the GPS distance is within the configured company radius.")
    location = get_geolocation()
    if not location:
        gps_refresh_box()
        return
    lat, lon, accuracy = extract_gps_from_browser_location(location)
    if lat is None or lon is None:
        st.warning("Browser location was not available. Allow location permission and retry.")
        gps_refresh_box()
        return
    distance = distance_meter(lat, lon, COMPANY_LAT, COMPANY_LON)
    c1, c2, c3 = st.columns(3)
    c1.metric("Distance", format_distance_km(distance))
    c2.metric("GPS Accuracy", f"{accuracy} m" if accuracy else "Not reported")
    c3.metric("Allowed Radius", f"{ALLOWED_RADIUS_METER} m")
    if distance <= ALLOWED_RADIUS_METER:
        ok, saved_distance = auto_save_attendance_from_gps(lat, lon)
        if ok:
            st.success(f"Attendance saved automatically. Distance: {format_distance_km(saved_distance)}")
        elif st.session_state.get(saved_key):
            st.success("Attendance was already saved in this signed-in session today.")
        else:
            st.error("Attendance could not be saved. Please retry or contact Admin.")
    else:
        st.error("You are outside the allowed company radius. Attendance was not saved.")
        bearing = bearing_to_company(lat, lon)
        direction = compass_direction(bearing)
        attendance_map_card(lat, lon, distance, direction, direction_hint(direction), show_embed=True)


def auto_save_attendance_from_gps(lat, lon):
    user_id = st.session_state.get("user_id", "")
    name = st.session_state.get("employee_name", "")
    user_role = st.session_state.get("role", "")
    today = today_str()
    saved_key = f"attendance_saved_{today}_{user_id}"
    if st.session_state.get(saved_key):
        return False, 0
    distance = distance_meter(lat, lon, COMPANY_LAT, COMPANY_LON)
    if distance > ALLOWED_RADIUS_METER:
        return False, distance
    ok = append_row("attendance", {
        "Date": today,
        "Time": time_str(),
        "User ID": user_id,
        "Technician Name": name,
        "Role": user_role,
        "Attendance Status": "Present",
        "Latitude": lat,
        "Longitude": lon,
        "Distance Meter": distance,
        "Selfie Saved": "No",
    })
    if ok:
        st.session_state[saved_key] = True
        return True, distance
    return False, distance


def page_delete_invoice_request():
    page_hero("Delete Invoice Request", "Submit a deletion request without downloading invoice or request records.", "Write Only")
    st.info("To avoid reading existing invoice records, enter the exact Entry ID and invoice details from your own saved confirmation.")
    entry_id = st.text_input("Invoice Entry ID")
    registration = st.text_input("Registration Number")
    job_card = st.text_input("Job Card Number")
    reason = st.text_area("Reason for delete request")
    if st.button("SUBMIT DELETE REQUEST", type="primary", use_container_width=True):
        if not all([entry_id.strip(), reason.strip()]):
            st.error("Entry ID and reason are required.")
            return
        session_key = f"delete_request_sent_{entry_id.strip()}"
        if st.session_state.get(session_key):
            st.warning("A request for this Entry ID was already submitted in this signed-in session.")
            return
        ok = append_row("delete_requests", {
            "Request ID": "DR-" + uuid.uuid4().hex[:8].upper(),
            "Date": today_str(),
            "Time": time_str(),
            "Entry ID": entry_id.strip(),
            "Technician Name": st.session_state.get("employee_name", ""),
            "User ID": st.session_state.get("user_id", ""),
            "Reason": reason.strip() + (f" | Registration: {registration.strip()}" if registration.strip() else "") + (f" | Job Card: {job_card.strip()}" if job_card.strip() else ""),
            "Request Status": "Pending",
            "Admin Action Date": "",
        })
        if ok:
            st.session_state[session_key] = True
            st.success("Delete request submitted to Admin.")


def page_admin_panel():
    if not is_admin():
        st.error("Admin access only.")
        return
    page_hero("Admin Panel", "Employee writes, manual approval actions and local API-call audit. No business records are fetched.", "Admin")
    employee_tab, approval_tab, audit_tab = st.tabs(["Employee Management", "Request Approval", "API Call Audit"])

    with employee_tab:
        st.subheader("Create Employee")
        with st.form("create_employee_write_only"):
            new_user_id = st.text_input("User ID")
            new_password = st.text_input("Password", type="password")
            new_name = st.text_input("Employee Name")
            new_role = st.selectbox("Role", ["Admin", "Manager", "Technician", "Prathisha / System Staff"])
            new_status = st.selectbox("Status", ["Active", "Inactive"])
            confirmed_unique = st.checkbox("I verified this User ID is unique in the employee register.")
            create_submitted = st.form_submit_button("CREATE EMPLOYEE", type="primary", use_container_width=True)
        if create_submitted:
            if not all([new_user_id.strip(), new_password, new_name.strip()]):
                st.error("User ID, password and employee name are required.")
            elif not confirmed_unique:
                st.error("Verify that the User ID is unique before appending the employee row.")
            else:
                ok = append_row("employees", {
                    "User ID": new_user_id.strip(),
                    "Password": _password_hash(new_password),
                    "Employee Name": new_name.strip(),
                    "Role": new_role,
                    "Status": new_status,
                })
                if ok:
                    st.success("Employee row created. Password is stored as a salted PBKDF2 hash.")

        st.divider()
        st.subheader("Update Employee / Reset Password")
        st.caption("Write-only mode does not fetch the employee register. Enter the exact Google Sheet row number (row 1 is the header).")
        with st.form("update_employee_write_only"):
            employee_row = st.number_input("Employee worksheet row number", min_value=2, step=1, value=2)
            update_user_id = st.text_input("Confirm User ID for this row")
            update_name = st.text_input("Employee Name")
            update_role = st.selectbox("Updated Role", ["Admin", "Manager", "Technician", "Prathisha / System Staff"], key="update_employee_role")
            update_status = st.selectbox("Updated Status", ["Active", "Inactive"], key="update_employee_status")
            updated_password = st.text_input("New Password (leave blank to keep unchanged)", type="password")
            update_confirmed = st.checkbox("I verified the row number and User ID against the employee register.")
            update_submitted = st.form_submit_button("UPDATE EMPLOYEE", use_container_width=True)
        if update_submitted:
            if not update_user_id.strip() or not update_confirmed:
                st.error("Confirm the User ID and exact row number before updating.")
            else:
                if updated_password:
                    values = [[_password_hash(updated_password), update_name.strip(), update_role, update_status]]
                    if update_sheet_range("employees", f"B{int(employee_row)}:E{int(employee_row)}", values):
                        st.success("Employee details and password updated.")
                else:
                    values = [[update_name.strip(), update_role, update_status]]
                    if update_sheet_range("employees", f"C{int(employee_row)}:E{int(employee_row)}", values):
                        st.success("Employee details updated; the existing password was left unchanged.")

    with approval_tab:
        st.subheader("Approve / Reject Delete Request")
        st.caption("The request and invoice registers are not downloaded. Admin must provide the exact row numbers checked in the secure Google Sheet register.")
        request_row = st.number_input("Delete request row number", min_value=2, step=1, value=2, key="approval_request_row")
        invoice_row = st.number_input("Invoice row number (approve only)", min_value=2, step=1, value=2, key="approval_invoice_row")
        approval_note = st.text_input("Admin note (optional)", key="approval_note")
        confirm_approval = st.checkbox("I verified both worksheet row numbers and the request details.", key="confirm_delete_approval")
        confirm_rejection = st.checkbox("I verified the delete request row before rejecting it.", key="confirm_delete_rejection")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("APPROVE & DELETE INVOICE", type="primary", use_container_width=True):
                if not confirm_approval:
                    st.error("Confirm the request and invoice row numbers before deletion.")
                    return
                if approve_delete_request(int(invoice_row), int(request_row)):
                    st.success("Invoice row deleted and request marked Approved atomically.")
        with c2:
            if st.button("REJECT REQUEST", use_container_width=True):
                if not confirm_rejection:
                    st.error("Confirm the request row before rejecting it.")
                    return
                if update_sheet_range("delete_requests", f"H{int(request_row)}:I{int(request_row)}", [["Rejected", now_stamp()]]):
                    st.success("Request marked Rejected.")
        if approval_note.strip():
            st.caption("Admin note entered: " + approval_note.strip())

    with audit_tab:
        st.subheader("Google Sheets API Activity — this server session")
        summary = get_api_call_audit_summary()
        if summary:
            st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)
        else:
            st.info("No Google Sheets API activity has been recorded in this server session yet.")
        audit_col1, audit_col2 = st.columns(2)
        with audit_col1:
            if st.button("Refresh Audit View", use_container_width=True):
                st.rerun()
        with audit_col2:
            if st.button("Reset Audit Counters", use_container_width=True):
                reset_api_call_audit()
                st.rerun()


def menu_page():
    return render_sidebar(
        is_admin=is_admin(),
        is_manager=is_manager(),
        is_technician=is_technician(),
        is_prathisha=is_prathisha(),
        employee_name=st.session_state.get("employee_name", ""),
        user_role=st.session_state.get("role", ""),
    )


def main():
    ensure_local_work_dirs()
    if not st.session_state.get("logged_in"):
        page_login()
        return
    selected_page = menu_page()
    if selected_page == "Home":
        page_dashboard()
    elif selected_page == "Attendance":
        page_attendance()
    elif selected_page == "Upload Invoice":
        page_upload_invoice()
    elif selected_page in {"Reports", "Daily Service Report"}:
        page_reports()
    elif selected_page == "Hero Bikes":
        page_hero_bikes()
    elif selected_page == "Manual Invoice Generator":
        page_manual_invoice()
    elif selected_page == "Delete Invoice Request":
        page_delete_invoice_request()
    elif selected_page == "Admin Panel":
        page_admin_panel()
    elif selected_page == "Extra Fittings":
        try:
            from extra_fittings import render_extra_fittings_page
            render_extra_fittings_page()
        except Exception as exc:
            st.error("Extra Fittings page could not be loaded.")
            st.caption(str(exc))
    elif selected_page == "LETTER PAD":
        from ui_modules.letter_pad import render_letter_pad_page
        render_letter_pad_page()
    else:
        st.error("This page is not available in the write-only ERP workflow.")


if __name__ == "__main__":
    main()
