
import re
import io
import uuid
import math
import zipfile
from pathlib import Path
from datetime import datetime

import streamlit as st
import pandas as pd
from PIL import Image
import qrcode

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
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
# SELVA MOTORS EXCEL STORAGE APP
# Excel only. No MySQL. No SQLAlchemy. No SQL database.
# ============================================================

st.set_page_config(
    page_title="Selva Motors Excel Storage App",
    page_icon="🏍️",
    layout="wide"
)

APP_TITLE = "SELVA MOTORS EXCEL STORAGE APP"
VERSION_TEXT = "Excel Storage Version"
SECRET_PASSWORD = "hari121"

DATA_DIR = Path("data")
UPLOAD_DIR = Path("uploads")
PDF_DIR = Path("generated_reports")
BACKUP_DIR = Path("backups")

DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)
PDF_DIR.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(exist_ok=True)

EXCEL_FILE = DATA_DIR / "selva_motors_excel_storage.xlsx"

COMPANY_LAT = 11.1271
COMPANY_LON = 78.6569
ALLOWED_RADIUS_METER = 300


# ============================================================
# STYLE
# ============================================================
st.markdown("""
<style>
.block-container { padding-top: 1rem; }
.app-title {
    font-size: 34px;
    font-weight: 900;
    color: #111827;
    margin-bottom: 4px;
}
.version-badge {
    display: inline-block;
    padding: 8px 14px;
    border-radius: 999px;
    background: #dcfce7;
    color: #166534;
    font-weight: 900;
    margin-bottom: 12px;
}
.card {
    background: white;
    border-radius: 16px;
    padding: 18px;
    box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08);
    margin-bottom: 14px;
}
.metric-card {
    background: linear-gradient(135deg, #111827, #374151);
    color: white;
    border-radius: 16px;
    padding: 18px;
    box-shadow: 0 6px 18px rgba(15, 23, 42, 0.16);
}
.metric-card p { margin: 0; color: #d1d5db; font-size: 14px; }
.metric-card h2 { margin: 0; font-size: 30px; }
.stButton>button { border-radius: 10px; font-weight: 700; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# EXCEL STORAGE STRUCTURE
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
        "Invoice Number", "Registration Number", "Bike Model",
        "Labour Amount", "Spare Parts Count", "Oil Count", "Oil Details",
        "Total Amount", "Entry Type", "Status"
    ],
    "delete_requests": [
        "Request ID", "Date", "Time", "Entry ID", "Technician Name",
        "User ID", "Reason", "Request Status", "Admin Action Date"
    ],
    "manual_invoices": [
        "Manual Bill ID", "Date", "Technician Name", "User ID",
        "Customer Name", "Registration Number", "Bike Model",
        "Labour Amount", "Spare Parts Count", "Oil Count",
        "Total Amount", "PDF File", "Status"
    ],
    "settings": [
        "Key", "Value"
    ],
}

DEFAULT_EMPLOYEES = [
    ["admin", "admin123", "Admin", "Admin", "Active"],
    ["manager", "manager123", "Manager", "Manager", "Active"],
    ["mohan", "mohan", "Mohan", "Technician", "Active"],
    ["ajay", "ajay", "Ajay", "Technician", "Active"],
    ["vengadesh", "vengadesh", "Vengadesh", "Technician", "Active"],
    ["prathisha", "prathisha", "Prathisha", "Prathisha / System Staff", "Active"],
]


def today_str():
    return datetime.now().strftime("%d-%m-%Y")


def time_str():
    return datetime.now().strftime("%I:%M:%S %p")


def now_stamp():
    return datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")


def create_excel_if_missing():
    if EXCEL_FILE.exists():
        return

    with pd.ExcelWriter(EXCEL_FILE, engine="openpyxl") as writer:
        for sheet, cols in SHEETS.items():
            df = pd.DataFrame(columns=cols)

            if sheet == "employees":
                df = pd.DataFrame(DEFAULT_EMPLOYEES, columns=cols)

            if sheet == "settings":
                df = pd.DataFrame([
                    ["Storage Type", "Excel Only"],
                    ["Version", VERSION_TEXT],
                    ["Excel File Path", str(EXCEL_FILE)],
                    ["Company Latitude", str(COMPANY_LAT)],
                    ["Company Longitude", str(COMPANY_LON)],
                    ["Allowed Radius Meter", str(ALLOWED_RADIUS_METER)],
                ], columns=cols)

            df.to_excel(writer, sheet_name=sheet, index=False)


def read_sheet(sheet_name):
    create_excel_if_missing()
    try:
        df = pd.read_excel(EXCEL_FILE, sheet_name=sheet_name, engine="openpyxl")
    except Exception:
        df = pd.DataFrame(columns=SHEETS[sheet_name])

    for col in SHEETS[sheet_name]:
        if col not in df.columns:
            df[col] = ""

    return df[SHEETS[sheet_name]].fillna("")


def write_sheet(sheet_name, df):
    create_excel_if_missing()

    all_sheets = {}
    for name in SHEETS:
        if name == sheet_name:
            temp = df.copy()
            for col in SHEETS[name]:
                if col not in temp.columns:
                    temp[col] = ""
            all_sheets[name] = temp[SHEETS[name]]
        else:
            all_sheets[name] = read_sheet(name)

    with pd.ExcelWriter(EXCEL_FILE, engine="openpyxl", mode="w") as writer:
        for name, data in all_sheets.items():
            data.to_excel(writer, sheet_name=name, index=False)


def append_row(sheet_name, row_dict):
    df = read_sheet(sheet_name)
    clean_row = {col: row_dict.get(col, "") for col in SHEETS[sheet_name]}
    df = pd.concat([df, pd.DataFrame([clean_row])], ignore_index=True)
    write_sheet(sheet_name, df)


create_excel_if_missing()


# ============================================================
# AUTH
# ============================================================
def login_user(user_id, password):
    users = read_sheet("employees")
    users["User ID"] = users["User ID"].astype(str)
    users["Password"] = users["Password"].astype(str)
    users["Status"] = users["Status"].astype(str)

    match = users[
        (users["User ID"].str.strip() == str(user_id).strip()) &
        (users["Password"].str.strip() == str(password).strip()) &
        (users["Status"].str.lower() == "active")
    ]

    if match.empty:
        return None

    return match.iloc[0].to_dict()


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


def save_uploaded_file(uploaded_file, folder=UPLOAD_DIR):
    if uploaded_file is None:
        return ""
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", uploaded_file.name)
    path = folder / f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{safe}"
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


def count_genuine_spare_items(text):
    section = get_section(
        text,
        ["Genuine Parts Details", "Genuine Part Details", "Spares Details", "Spare Details", "Parts Details"],
        ["Labour Details", "Other Labour Details", "Summary", "Tax", "Grand Total", "Total Invoice"]
    )

    if not section:
        return 0

    lines = [line.strip() for line in section.splitlines() if line.strip()]
    count = 0

    for line in lines:
        lower = line.lower()

        if any(word in lower for word in ["genuine parts", "spares details", "parts details", "part no", "description", "amount", "qty", "rate"]):
            continue

        has_spare_word = bool(re.search(
            r"oil|filter|plug|shoe|pad|cable|chain|lamp|bulb|bearing|gasket|lever|mirror|clutch|brake|tube|tyre|washer|nut|bolt|cover|seal",
            lower
        ))
        has_part_code = bool(re.search(r"\b[A-Z0-9]{4,}[-\/]?[A-Z0-9]*\b", line))
        has_amount_like = bool(re.search(r"\d+(?:\.\d+)?\s*$", line))

        if has_spare_word or (has_part_code and has_amount_like):
            count += 1

    return count


def detect_oil(text):
    oil_lines = []

    for line in text.splitlines():
        if re.search(r"Hero\s*4T\s*PLUS|engine\s*oil|\boil\b", line, flags=re.I):
            oil_lines.append(line.strip())

    if re.search(r"Hero\s*4T\s*PLUS", text, flags=re.I) and not oil_lines:
        oil_lines.append("Hero 4T PLUS")

    return len(oil_lines), "; ".join(oil_lines[:5])


def section_amount(section):
    if not section:
        return 0.0

    total_match = re.findall(
        r"(?:total|sub\s*total|amount)\D{0,25}(\d+(?:,\d+)*(?:\.\d+)?)",
        section,
        flags=re.I
    )
    if total_match:
        return to_float(total_match[-1])

    line_amounts = []
    for line in section.splitlines():
        nums = re.findall(r"\d+(?:,\d+)*(?:\.\d+)?", line)
        if nums:
            line_amounts.append(to_float(nums[-1]))

    return max(line_amounts) if line_amounts else 0.0


def extract_labour_total(text):
    labour_section = get_section(
        text,
        ["Labour Details", "Labor Details"],
        ["Other Labour Details", "Genuine Parts Details", "Spares Details", "Summary", "Grand Total", "Total Invoice"]
    )

    other_section = get_section(
        text,
        ["Other Labour Details", "Other Labor Details"],
        ["Genuine Parts Details", "Spares Details", "Summary", "Grand Total", "Total Invoice"]
    )

    labour_amount = section_amount(labour_section)
    other_amount = section_amount(other_section)

    if labour_amount == 0:
        labour_amount = to_float(find_one([
            r"Labou?r\s*Details\s*Amount\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
            r"Total\s*Labou?r\s*Amount\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
            r"Labou?r\s*Total\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)"
        ], text))

    if other_amount == 0:
        other_amount = to_float(find_one([
            r"Other\s*Labou?r\s*Details\s*Amount\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
            r"Other\s*Labou?r\s*Total\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)"
        ], text))

    return round(labour_amount + other_amount, 2)


def parse_invoice(text):
    flat = re.sub(r"\s+", " ", text)

    invoice_no = find_one([
        r"Invoice\s*(?:No|Number)?\s*[:\-]?\s*([A-Z0-9\-\/]+)",
        r"Bill\s*(?:No|Number)?\s*[:\-]?\s*([A-Z0-9\-\/]+)",
        r"Job\s*Card\s*(?:No|Number)?\s*[:\-]?\s*([A-Z0-9\-\/]+)",
        r"JC\s*(?:No)?\s*[:\-]?\s*([A-Z0-9\-\/]+)"
    ], flat)

    reg_no = find_one([
        r"Vehicle\s*(?:Reg|Registration)?\s*(?:No|Number)?\s*[:\-]?\s*([A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{3,4})",
        r"Reg\s*(?:No|Number)?\s*[:\-]?\s*([A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{3,4})",
        r"\b([A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{3,4})\b"
    ], flat)

    bike_model = find_one([
        r"Vehicle\s*Model\s*[:\-]?\s*([A-Za-z0-9 +._-]{3,45})",
        r"Model\s*[:\-]?\s*([A-Za-z0-9 +._-]{3,45})"
    ], flat)

    customer_name = find_one([
        r"Customer\s*Name\s*[:\-]?\s*([A-Za-z .]{3,45})",
        r"Name\s*[:\-]?\s*([A-Za-z .]{3,45})"
    ], flat)

    total_amount = to_float(find_one([
        r"Total\s*Invoice\s*Value\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
        r"Grand\s*Total\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
        r"Net\s*Amount\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
        r"Total\s*Amount\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)"
    ], flat))

    spare_count = count_genuine_spare_items(text)
    oil_count, oil_details = detect_oil(text)
    labour_amount = extract_labour_total(text)

    return {
        "Customer Name": clean_customer_name(customer_name),
        "Invoice Number": invoice_no,
        "Registration Number": clean_reg_no(reg_no),
        "Bike Model": clean_bike_model(bike_model),
        "Labour Amount": labour_amount,
        "Spare Parts Count": spare_count,
        "Oil Count": oil_count,
        "Oil Details": oil_details,
        "Total Amount": total_amount,
    }


def duplicate_exists(invoice_no, reg_no, total_amount):
    inv = read_sheet("invoices")
    if inv.empty:
        return False

    if invoice_no:
        same_invoice = inv["Invoice Number"].astype(str).str.upper() == str(invoice_no).upper()
        if same_invoice.any():
            return True

    if reg_no and float(total_amount or 0) > 0:
        amount_series = pd.to_numeric(inv["Total Amount"], errors="coerce").fillna(0)
        same_vehicle_amount = (
            (inv["Registration Number"].astype(str).str.upper() == str(reg_no).upper()) &
            (amount_series == float(total_amount))
        )
        if same_vehicle_amount.any():
            return True

    return False


# ============================================================
# REPORT PDF
# ============================================================
def generate_report_pdf(df, title, file_name):
    pdf_path = PDF_DIR / file_name
    doc = SimpleDocTemplate(str(pdf_path), pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [
        Paragraph(f"<b>{title}</b>", styles["Title"]),
        Spacer(1, 12)
    ]

    if df.empty:
        elements.append(Paragraph("No records found.", styles["BodyText"]))
    else:
        summary = df.groupby(["Technician Name", "Date"], dropna=False).size().reset_index(name="Number of Vehicle Entries")
        elements.append(Paragraph("<b>Summary</b>", styles["Heading2"]))

        s_table = Table([summary.columns.tolist()] + summary.astype(str).values.tolist(), repeatRows=1)
        s_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.black),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))
        elements.append(s_table)
        elements.append(Spacer(1, 14))

        detail_cols = [
            "Technician Name", "Date", "Registration Number",
            "Bike Model", "Labour Amount", "Total Amount", "Entry Type", "Status"
        ]
        show_cols = [c for c in detail_cols if c in df.columns]
        details = df[show_cols].copy().astype(str)

        elements.append(Paragraph("<b>Entry Details</b>", styles["Heading2"]))
        d_table = Table([details.columns.tolist()] + details.values.tolist(), repeatRows=1)
        d_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.black),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        elements.append(d_table)

    doc.build(elements)
    return str(pdf_path)


# ============================================================
# MANUAL BILL PDF
# ============================================================
def create_qr_image(text):
    qr = qrcode.make(text)
    path = PDF_DIR / f"qr_{uuid.uuid4().hex[:8]}.png"
    qr.save(path)
    return str(path)


def generate_manual_bill_pdf(customer_name, reg_no, bike_model, spare_rows, labour_amount):
    bill_id = "MB-" + datetime.now().strftime("%Y%m%d%H%M%S")
    pdf_path = PDF_DIR / f"{bill_id}.pdf"

    technician_name = st.session_state.get("employee_name", "")
    user_id = st.session_state.get("user_id", "")

    customer_name = clean_customer_name(customer_name)
    reg_no = clean_reg_no(reg_no)
    bike_model = clean_bike_model(bike_model)

    spare_total = sum(float(row["Amount"]) for row in spare_rows)
    labour_amount = float(labour_amount)
    total_amount = round(spare_total + labour_amount, 2)

    spare_count = len([row for row in spare_rows if str(row["Spare Name"]).strip()])
    oil_count = sum(1 for row in spare_rows if re.search(r"Hero\s*4T\s*PLUS|\boil\b", row["Spare Name"], flags=re.I))

    qr_path = create_qr_image(f"Manual Bill: {bill_id}, Reg: {reg_no}, Total: {total_amount}")

    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    w, h = A4

    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, h - 45, "Manual Bill")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, h - 65, "SELVA MOTORS - HERO SERVICE BILL STYLE")
    c.line(40, h - 78, w - 40, h - 78)

    c.setFont("Helvetica", 10)
    c.drawString(40, h - 105, f"Bill ID: {bill_id}")
    c.drawString(350, h - 105, f"Date: {today_str()}")
    c.drawString(40, h - 125, f"Technician Name: {technician_name}")
    c.drawString(350, h - 125, f"User ID: {user_id}")

    c.drawString(40, h - 155, f"Customer Name: {customer_name}")
    c.drawString(40, h - 175, f"Registration Number: {reg_no}")
    c.drawString(350, h - 175, f"Bike Model: {bike_model}")

    y = h - 215
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Spare Parts Details")
    y -= 18

    c.setFont("Helvetica-Bold", 9)
    headers = [("S.No", 45), ("Spare Name", 90), ("Qty", 300), ("Rate", 360), ("Amount", 440)]
    for label, x in headers:
        c.drawString(x, y, label)
    c.line(40, y - 5, w - 40, y - 5)

    c.setFont("Helvetica", 9)
    y -= 22
    for i, row in enumerate(spare_rows, start=1):
        if not str(row["Spare Name"]).strip():
            continue
        c.drawString(45, y, str(i))
        c.drawString(90, y, str(row["Spare Name"])[:28])
        c.drawString(300, y, str(row["Qty"]))
        c.drawString(360, y, f"Rs.{float(row['Rate']):.2f}")
        c.drawString(440, y, f"Rs.{float(row['Amount']):.2f}")
        y -= 18

    y -= 10
    c.line(320, y, w - 40, y)
    y -= 20
    c.setFont("Helvetica-Bold", 10)
    c.drawString(340, y, f"Spare Total: Rs.{spare_total:.2f}")
    y -= 18
    c.drawString(340, y, f"Labour Amount: Rs.{labour_amount:.2f}")
    y -= 22
    c.setFont("Helvetica-Bold", 13)
    c.drawString(340, y, f"Grand Total: Rs.{total_amount:.2f}")

    c.drawImage(qr_path, 45, 70, width=80, height=80)
    c.setFont("Helvetica", 8)
    c.drawString(45, 55, "QR Verification")
    c.drawString(350, 90, "Technician Signature")
    c.line(350, 75, 520, 75)

    c.save()

    append_row("manual_invoices", {
        "Manual Bill ID": bill_id,
        "Date": today_str(),
        "Technician Name": technician_name,
        "User ID": user_id,
        "Customer Name": customer_name,
        "Registration Number": reg_no,
        "Bike Model": bike_model,
        "Labour Amount": labour_amount,
        "Spare Parts Count": spare_count,
        "Oil Count": oil_count,
        "Total Amount": total_amount,
        "PDF File": str(pdf_path),
        "Status": "Generated"
    })

    return str(pdf_path)


# ============================================================
# LOGIN
# ============================================================
def page_login():
    st.markdown(f"<div class='app-title'>🏍️ SELVA MOTORS STAFF LOGIN</div>", unsafe_allow_html=True)

    st.subheader("🔐 Login")
    user_id = st.text_input("User ID")
    password = st.text_input("Password", type="password")

    if st.button("Login", use_container_width=True):
        user = login_user(user_id, password)
        if user:
            st.session_state["logged_in"] = True
            st.session_state["user_id"] = user["User ID"]
            st.session_state["employee_name"] = user["Employee Name"]
            st.session_state["role"] = user["Role"]
            st.success("Login success")
            st.rerun()
        else:
            st.error("Invalid login")


def menu_page():
    st.sidebar.title("🏍️ Selva Motors")
    st.sidebar.success(f"{st.session_state.get('employee_name')} | {st.session_state.get('role')}")

    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    if is_admin():
        pages = [
            "Dashboard", "Reports", "Search",
            "Customer Service History", "Manual Invoice Generator", "Admin Panel"
        ]
    elif is_manager():
        pages = [
            "Dashboard", "Attendance", "Upload Invoice", "Reports", "Search",
            "Customer Service History", "Manual Invoice Generator", "Manager Edit"
        ]
    elif is_technician():
        pages = [
            "Dashboard", "Attendance", "Upload Invoice",
            "Customer Service History", "Manual Invoice Generator",
            "Delete Invoice Request"
        ]
    elif is_prathisha():
        pages = ["Dashboard", "Attendance"]
    else:
        pages = ["Dashboard"]

    return st.sidebar.radio("Menu", pages)


def metric_card(title, value, caption=""):
    st.markdown(f"""
    <div class="metric-card">
        <p>{title}</p>
        <h2>{value}</h2>
        <p>{caption}</p>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# DASHBOARD
# ============================================================
def page_dashboard():
    st.markdown(f"<div class='app-title'>📊 Dashboard</div>", unsafe_allow_html=True)

    invoices = read_sheet("invoices")
    invoices["Total Amount"] = pd.to_numeric(invoices["Total Amount"], errors="coerce").fillna(0)
    invoices["Labour Amount"] = pd.to_numeric(invoices["Labour Amount"], errors="coerce").fillna(0)

    today = today_str()
    user_id = st.session_state.get("user_id", "")

    if is_technician():
        view_df = invoices[
            (invoices["User ID"].astype(str) == user_id) &
            (invoices["Date"].astype(str) == today)
        ]
        c1, c2, c3 = st.columns(3)
        with c1:
            metric_card("Today Revenue", f"₹{view_df['Total Amount'].sum():,.0f}", "Only your today entries")
        with c2:
            metric_card("Today Vehicle Entries", len(view_df), "Your entries")
        with c3:
            metric_card("Today Labour", f"₹{view_df['Labour Amount'].sum():,.0f}", "Your labour amount")

        st.subheader("Your Today Entry Details")
        st.dataframe(view_df, use_container_width=True)
        return

    if is_prathisha():
        attendance = read_sheet("attendance")
        today_att = attendance[attendance["Date"].astype(str) == today]
        c1, c2 = st.columns(2)
        with c1:
            metric_card("Today Attendance Count", len(today_att), "System staff view")
        with c2:
            metric_card("Excel Storage", "Active", "No technician work options")
        st.subheader("Today Attendance")
        st.dataframe(today_att, use_container_width=True)
        return

    if is_admin():
        month_key = datetime.now().strftime("%m-%Y")
        temp = invoices.copy()
        temp["Month"] = pd.to_datetime(temp["Date"], format="%d-%m-%Y", errors="coerce").dt.strftime("%m-%Y")
        month_df = temp[temp["Month"] == month_key]

        c1, c2, c3 = st.columns(3)
        with c1:
            metric_card("Monthly Revenue", f"₹{month_df['Total Amount'].sum():,.0f}", "Admin only")
        with c2:
            metric_card("Today Revenue", f"₹{invoices[invoices['Date'].astype(str) == today]['Total Amount'].sum():,.0f}", "All technicians")
        with c3:
            metric_card("Total Entries", len(invoices), "All invoice entries")

        st.subheader("Technician-wise Revenue")
        if not invoices.empty:
            tech = invoices.groupby("Technician Name", dropna=False)["Total Amount"].sum().reset_index()
            st.dataframe(tech, use_container_width=True)

        st.subheader("Recent Entries")
        st.dataframe(invoices.tail(20), use_container_width=True)
        return

    if is_manager():
        today_df = invoices[invoices["Date"].astype(str) == today]
        c1, c2 = st.columns(2)
        with c1:
            metric_card("Today Revenue", f"₹{today_df['Total Amount'].sum():,.0f}", "Manager view")
        with c2:
            metric_card("Today Entries", len(today_df), "All technician entries")
        st.subheader("Today Entries")
        st.dataframe(today_df, use_container_width=True)


# ============================================================
# ATTENDANCE
# ============================================================
def page_attendance():
    st.markdown("<div class='app-title'>📍 Attendance</div>", unsafe_allow_html=True)

    user_id = st.session_state["user_id"]
    name = st.session_state["employee_name"]
    user_role = st.session_state["role"]

    today = today_str()
    att = read_sheet("attendance")
    exists = att[
        (att["Date"].astype(str) == today) &
        (att["User ID"].astype(str) == user_id)
    ]

    if not exists.empty:
        st.warning("Today attendance already marked.")
        st.dataframe(exists, use_container_width=True)
        return

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("GPS Details")
        lat = st.text_input("Latitude")
        lon = st.text_input("Longitude")

        if get_geolocation:
            if st.button("Get Current GPS"):
                loc = get_geolocation()
                st.write(loc)
                st.info("If GPS values show here, copy latitude and longitude into the fields.")

        status = st.selectbox("Attendance Status", ["Present", "Half Day Leave", "Late Present"])

    with c2:
        st.subheader("Selfie")
        selfie = st.camera_input("Capture Selfie")

    dist = ""
    inside = False
    if lat and lon:
        dist = distance_meter(lat, lon, COMPANY_LAT, COMPANY_LON)
        if dist <= ALLOWED_RADIUS_METER:
            inside = True
            st.success(f"Inside company radius. Distance: {dist} meter")
        else:
            st.error(f"Outside company radius. Distance: {dist} meter")

    if st.button("Mark Attendance", use_container_width=True):
        if not lat or not lon:
            st.error("Latitude and Longitude required.")
            return

        if not inside:
            st.error("Attendance blocked outside company radius.")
            return

        selfie_saved = "No"
        if selfie:
            save_uploaded_file(selfie)
            selfie_saved = "Yes"

        append_row("attendance", {
            "Date": today,
            "Time": time_str(),
            "User ID": user_id,
            "Technician Name": name,
            "Role": user_role,
            "Attendance Status": status,
            "Latitude": lat,
            "Longitude": lon,
            "Distance Meter": dist,
            "Selfie Saved": selfie_saved
        })
        st.success("Attendance saved to Excel.")
        st.rerun()


# ============================================================
# UPLOAD INVOICE
# ============================================================
def page_upload_invoice():
    st.markdown("<div class='app-title'>📄 AI Invoice OCR Upload</div>", unsafe_allow_html=True)
    st.caption("OCR Preview is view-only. Values are cleaned before Excel save. Raw OCR text is not saved.")

    uploaded = st.file_uploader("Upload Invoice PDF / Image", type=["pdf", "jpg", "jpeg", "png", "webp"])

    if uploaded:
        file_path = save_uploaded_file(uploaded)
        text = extract_invoice_text(file_path)

        if not text.strip():
            st.error("OCR text not detected. For scanned PDF/image, install Tesseract OCR or upload clearer file.")
            return

        parsed = parse_invoice(text)
        st.session_state["ocr_preview"] = parsed

    if st.button("Use Sample Invoice Data"):
        st.session_state["ocr_preview"] = {
            "Customer Name": "",
            "Invoice Number": "67381-03-RJC-1225-1094",
            "Registration Number": "TN51AT6661",
            "Bike Model": "Splendor Plus",
            "Labour Amount": 1906.88,
            "Spare Parts Count": 5,
            "Oil Count": 1,
            "Oil Details": "Hero 4T PLUS",
            "Total Amount": 7811,
        }

    if "ocr_preview" not in st.session_state:
        return

    data = st.session_state["ocr_preview"]

    st.subheader("View Only OCR Preview")
    preview_df = pd.DataFrame([{
        "Invoice Number": data.get("Invoice Number", ""),
        "Registration Number": data.get("Registration Number", ""),
        "Bike Model": data.get("Bike Model", ""),
        "Labour Amount": data.get("Labour Amount", 0),
        "Spare Parts Count": data.get("Spare Parts Count", 0),
        "Oil Count": data.get("Oil Count", 0),
        "Oil Details": data.get("Oil Details", ""),
        "Total Amount": data.get("Total Amount", 0),
        "Entry Type": "OCR Upload",
        "Status": "Active"
    }])
    st.dataframe(preview_df, use_container_width=True)

    missing = []
    for col in ["Invoice Number", "Registration Number", "Bike Model"]:
        if not str(data.get(col, "")).strip():
            missing.append(col)

    if missing:
        st.warning("Missing detected values: " + ", ".join(missing))
        st.info("Preview is view-only as per requirement. Upload a clearer invoice if values are missing.")

    duplicate = duplicate_exists(
        data.get("Invoice Number", ""),
        data.get("Registration Number", ""),
        data.get("Total Amount", 0)
    )
    if duplicate:
        st.error("Duplicate invoice/vehicle amount detected.")

    if st.button("Click to Proceed the Entry", use_container_width=True):
        if missing:
            st.error("Required values missing. Cannot proceed.")
            return

        entry_id = "E-" + uuid.uuid4().hex[:8].upper()
        append_row("invoices", {
            "Entry ID": entry_id,
            "Date": today_str(),
            "Technician Name": st.session_state.get("employee_name", ""),
            "User ID": st.session_state.get("user_id", ""),
            "Invoice Number": data.get("Invoice Number", ""),
            "Registration Number": data.get("Registration Number", ""),
            "Bike Model": clean_bike_model(data.get("Bike Model", "")),
            "Labour Amount": data.get("Labour Amount", 0),
            "Spare Parts Count": data.get("Spare Parts Count", 0),
            "Oil Count": data.get("Oil Count", 0),
            "Oil Details": data.get("Oil Details", ""),
            "Total Amount": data.get("Total Amount", 0),
            "Entry Type": "OCR Upload",
            "Status": "Active"
        })

        del st.session_state["ocr_preview"]
        st.success("Entry saved to Excel.")
        st.rerun()


# ============================================================
# REPORTS
# ============================================================
def page_reports():
    st.markdown("<div class='app-title'>📑 Reports</div>", unsafe_allow_html=True)

    invoices = read_sheet("invoices")

    if invoices.empty:
        st.info("No invoice entries found.")
        return

    invoices["Total Amount"] = pd.to_numeric(invoices["Total Amount"], errors="coerce").fillna(0)
    invoices["Labour Amount"] = pd.to_numeric(invoices["Labour Amount"], errors="coerce").fillna(0)

    if is_technician():
        invoices = invoices[
            (invoices["User ID"].astype(str) == st.session_state.get("user_id", "")) &
            (invoices["Date"].astype(str) == today_str())
        ]
        st.info("Technician view: only today’s own entries are shown.")

    else:
        view_type = st.radio(
            "Report View Type",
            ["All Technicians", "Particular Technician"],
            horizontal=True
        )

        if view_type == "Particular Technician":
            tech_names = sorted([
                x for x in invoices["Technician Name"].astype(str).unique().tolist()
                if x.strip()
            ])
            selected_tech = st.selectbox("Select Technician", tech_names)
            invoices = invoices[invoices["Technician Name"].astype(str) == selected_tech]
        else:
            st.info("All technician entries are shown.")

        c1, c2 = st.columns(2)
        with c1:
            date_filter = st.text_input("Date Filter DD-MM-YYYY", value="")
        with c2:
            reg_filter = st.text_input("Registration Number Filter", value="")

        if date_filter.strip():
            invoices = invoices[invoices["Date"].astype(str) == date_filter.strip()]

        if reg_filter.strip():
            reg_clean = clean_reg_no(reg_filter)
            invoices = invoices[invoices["Registration Number"].astype(str).str.upper() == reg_clean]

    st.subheader("Report Preview")

    show_cols = [
        "Technician Name", "Date", "Registration Number",
        "Bike Model", "Labour Amount", "Total Amount", "Entry Type", "Status"
    ]

    preview = invoices[show_cols] if not invoices.empty else invoices
    st.dataframe(preview, use_container_width=True)

    total_entries = len(invoices)
    total_revenue = invoices["Total Amount"].sum() if "Total Amount" in invoices.columns else 0
    total_labour = invoices["Labour Amount"].sum() if "Labour Amount" in invoices.columns else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Vehicle Entries", total_entries)
    c2.metric("Total Revenue", f"₹{total_revenue:,.0f}")
    c3.metric("Labour Amount", f"₹{total_labour:,.0f}")

    st.divider()

    if st.button("Generate PDF Report", use_container_width=True):
        pdf = generate_report_pdf(
            invoices,
            "Selva Motors Service Report",
            "selva_motors_service_report.pdf"
        )
        st.session_state["generated_report_pdf"] = pdf
        st.success("PDF report generated. Click download below.")

    if st.session_state.get("generated_report_pdf"):
        pdf_path = st.session_state["generated_report_pdf"]
        if Path(pdf_path).exists():
            with open(pdf_path, "rb") as f:
                st.download_button(
                    "Download PDF Report",
                    f,
                    file_name=Path(pdf_path).name,
                    mime="application/pdf",
                    use_container_width=True
                )


# ============================================================
# SEARCH
# ============================================================
def page_search():
    st.markdown("<div class='app-title'>🔍 Search</div>", unsafe_allow_html=True)

    invoices = read_sheet("invoices")
    query = st.text_input("Search by Registration Number / Invoice Number / Technician Name")

    if query:
        q = query.lower()
        result = invoices[
            invoices.astype(str).apply(lambda row: row.str.lower().str.contains(q, na=False).any(), axis=1)
        ]
    else:
        result = invoices

    safe_cols = [
        "Entry ID", "Date", "Technician Name", "User ID", "Invoice Number",
        "Registration Number", "Bike Model", "Labour Amount",
        "Spare Parts Count", "Oil Count", "Oil Details", "Total Amount",
        "Entry Type", "Status"
    ]
    st.dataframe(result[safe_cols], use_container_width=True)


# ============================================================
# CUSTOMER SERVICE HISTORY
# ============================================================
def page_customer_service_history():
    st.markdown("<div class='app-title'>🧾 Customer Service History</div>", unsafe_allow_html=True)

    invoices = read_sheet("invoices")
    today = today_str()

    if is_technician():
        today_entries = invoices[
            (invoices["Date"].astype(str) == today) &
            (invoices["User ID"].astype(str) == st.session_state.get("user_id", ""))
        ]
        st.info("Technician view: your today entries only.")
    else:
        today_entries = invoices[invoices["Date"].astype(str) == today]
        st.info("Admin/Manager view: all today's service entries are shown.")

    st.subheader("Today’s Service Entry History")
    st.dataframe(today_entries, use_container_width=True)

    st.subheader("Registration Number Search")
    reg = st.text_input("Enter Registration Number", placeholder="TN51AT6661")
    if reg:
        reg_clean = clean_reg_no(reg)
        result = invoices[invoices["Registration Number"].astype(str).str.upper() == reg_clean]
        st.dataframe(result, use_container_width=True)


# ============================================================
# MANUAL INVOICE GENERATOR
# ============================================================
def page_manual_invoice():
    st.markdown("<div class='app-title'>🧾 Manual Bill</div>", unsafe_allow_html=True)
    st.caption("Hero-style manual bill PDF. Technician name is taken from current logged-in user.")

    c1, c2 = st.columns(2)
    customer_name = c1.text_input("Customer Name")
    reg_no = c2.text_input("Registration Number")
    bike_model = c1.text_input("Bike Model")

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

    if st.button("Generate Manual Bill PDF", use_container_width=True):
        if not reg_no or not bike_model:
            st.error("Registration Number and Bike Model required.")
            return

        pdf = generate_manual_bill_pdf(customer_name, reg_no, bike_model, spare_rows, labour_amount)
        st.success("Manual Bill PDF generated.")

        with open(pdf, "rb") as f:
            st.download_button("Download Manual Bill PDF", f, file_name=Path(pdf).name, mime="application/pdf")


# ============================================================
# DELETE INVOICE REQUEST
# ============================================================
def page_delete_invoice_request():
    st.markdown("<div class='app-title'>🗑️ Delete Invoice Request</div>", unsafe_allow_html=True)

    invoices = read_sheet("invoices")
    own = invoices[
        (invoices["User ID"].astype(str) == st.session_state.get("user_id", "")) &
        (invoices["Status"].astype(str).str.lower() == "active")
    ]

    st.info("Technician can only request delete. Direct delete is not allowed.")
    st.dataframe(own, use_container_width=True)

    if own.empty:
        return

    entry_id = st.selectbox("Select Entry ID", own["Entry ID"].astype(str).tolist())
    reason = st.text_area("Reason for delete request")

    if st.button("Submit Delete Request"):
        if not reason.strip():
            st.error("Reason required.")
            return

        existing = read_sheet("delete_requests")
        pending_exists = existing[
            (existing["Entry ID"].astype(str) == entry_id) &
            (existing["Request Status"].astype(str) == "Pending")
        ]

        if not pending_exists.empty:
            st.warning("Pending request already exists for this entry.")
            return

        row = own[own["Entry ID"].astype(str) == entry_id].iloc[0]

        append_row("delete_requests", {
            "Request ID": "DR-" + uuid.uuid4().hex[:8].upper(),
            "Date": today_str(),
            "Time": time_str(),
            "Entry ID": entry_id,
            "Technician Name": row["Technician Name"],
            "User ID": row["User ID"],
            "Reason": reason,
            "Request Status": "Pending",
            "Admin Action Date": ""
        })

        st.success("Delete request sent to Admin.")


# ============================================================
# ADMIN PANEL
# ============================================================
def page_admin_panel():
    st.markdown("<div class='app-title'>⚙️ Admin Panel</div>", unsafe_allow_html=True)

    invoices = read_sheet("invoices")
    invoices["Total Amount"] = pd.to_numeric(invoices["Total Amount"], errors="coerce").fillna(0)

    st.subheader("Admin Revenue View")
    month_key = datetime.now().strftime("%m-%Y")
    temp = invoices.copy()
    temp["Month"] = pd.to_datetime(temp["Date"], format="%d-%m-%Y", errors="coerce").dt.strftime("%m-%Y")
    month_df = temp[temp["Month"] == month_key]

    c1, c2 = st.columns(2)
    c1.metric("Monthly Revenue", f"₹{month_df['Total Amount'].sum():,.0f}")
    c2.metric("Total Active Entries", len(invoices[invoices["Status"].astype(str) == "Active"]))

    st.subheader("Technician-wise Revenue Details")
    if not invoices.empty:
        tech = invoices.groupby("Technician Name", dropna=False)["Total Amount"].sum().reset_index()
        st.dataframe(tech, use_container_width=True)

    st.divider()
    st.subheader("Employee Edit Options")
    employees = read_sheet("employees")
    st.dataframe(employees, use_container_width=True)

    with st.expander("Add / Edit Employee"):
        user_id = st.text_input("User ID")
        password = st.text_input("Password")
        emp_name = st.text_input("Employee Name")
        emp_role = st.selectbox("Role", ["Admin", "Manager", "Technician", "Prathisha / System Staff"])
        status = st.selectbox("Status", ["Active", "Inactive"])

        if st.button("Save Employee"):
            if not user_id or not password or not emp_name:
                st.error("All fields required.")
            else:
                df = read_sheet("employees")
                if (df["User ID"].astype(str) == user_id).any():
                    idx = df[df["User ID"].astype(str) == user_id].index[0]
                    df.loc[idx, "Password"] = password
                    df.loc[idx, "Employee Name"] = emp_name
                    df.loc[idx, "Role"] = emp_role
                    df.loc[idx, "Status"] = status
                    write_sheet("employees", df)
                    st.success("Employee updated.")
                else:
                    append_row("employees", {
                        "User ID": user_id,
                        "Password": password,
                        "Employee Name": emp_name,
                        "Role": emp_role,
                        "Status": status
                    })
                    st.success("Employee added.")
                st.rerun()

    st.divider()
    st.subheader("Technician Delete Invoice Requests")
    req = read_sheet("delete_requests")
    pending = req[req["Request Status"].astype(str) == "Pending"]

    if pending.empty:
        st.info("No pending delete requests.")
    else:
        for idx, row in pending.iterrows():
            with st.container():
                st.write(f"Request ID: **{row['Request ID']}** | Entry ID: **{row['Entry ID']}**")
                st.write(f"Technician: **{row['Technician Name']}** | Reason: {row['Reason']}")

                c1, c2 = st.columns(2)
                if c1.button("Approve Delete", key=f"approve_{idx}"):
                    inv = read_sheet("invoices")
                    inv_idx = inv[inv["Entry ID"].astype(str) == str(row["Entry ID"])].index
                    if len(inv_idx) > 0:
                        inv = inv.drop(inv_idx)
                        write_sheet("invoices", inv)

                    req.loc[idx, "Request Status"] = "Approved"
                    req.loc[idx, "Admin Action Date"] = now_stamp()
                    write_sheet("delete_requests", req)
                    st.success("Request approved and invoice deleted.")
                    st.rerun()

                if c2.button("Reject Request", key=f"reject_{idx}"):
                    req.loc[idx, "Request Status"] = "Rejected"
                    req.loc[idx, "Admin Action Date"] = now_stamp()
                    write_sheet("delete_requests", req)
                    st.warning("Request rejected.")
                    st.rerun()

    st.divider()
    st.subheader("Settings")
    settings = read_sheet("settings")
    st.dataframe(settings, use_container_width=True)

    st.subheader("Password Protected Excel Sheet Direct Link")
    pwd = st.text_input("Enter password to view Excel link", type="password")
    if pwd == SECRET_PASSWORD:
        st.success("Password correct.")
        st.write(f"Excel file path: `{EXCEL_FILE}`")
        if EXCEL_FILE.exists():
            with open(EXCEL_FILE, "rb") as f:
                st.download_button(
                    "Download / Visit Excel Sheet",
                    f,
                    file_name="selva_motors_excel_storage.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    elif pwd:
        st.error("Wrong password.")


# ============================================================
# MANAGER EDIT
# ============================================================
def page_manager_edit():
    st.markdown("<div class='app-title'>✏️ Manager Edit</div>", unsafe_allow_html=True)

    pwd = st.text_input("Enter edit password", type="password")
    if pwd != SECRET_PASSWORD:
        if pwd:
            st.error("Wrong password.")
        st.info("Manager edit requires password.")
        return

    st.success("Edit access granted.")

    invoices = read_sheet("invoices")
    st.dataframe(invoices, use_container_width=True)

    if invoices.empty:
        return

    entry_id = st.selectbox("Select Entry ID to edit status", invoices["Entry ID"].astype(str).tolist())
    new_status = st.selectbox("New Status", ["Active", "Hold", "Completed", "Cancelled"])

    if st.button("Update Status"):
        idx = invoices[invoices["Entry ID"].astype(str) == entry_id].index
        if len(idx) > 0:
            invoices.loc[idx[0], "Status"] = new_status
            write_sheet("invoices", invoices)
            st.success("Status updated.")
            st.rerun()


# ============================================================
# BACKUP OPTIONAL
# ============================================================
def make_backup_zip():
    name = f"selva_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    path = BACKUP_DIR / name

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        if EXCEL_FILE.exists():
            z.write(EXCEL_FILE, EXCEL_FILE.name)
        for pdf in PDF_DIR.glob("*.pdf"):
            z.write(pdf, f"generated_reports/{pdf.name}")

    return path


# ============================================================
# MAIN
# ============================================================
def main():
    if not st.session_state.get("logged_in"):
        page_login()
        return

    page = menu_page()

    if page == "Dashboard":
        page_dashboard()
    elif page == "Attendance":
        page_attendance()
    elif page == "Upload Invoice":
        page_upload_invoice()
    elif page == "Reports":
        page_reports()
    elif page == "Search":
        page_search()
    elif page == "Customer Service History":
        page_customer_service_history()
    elif page == "Manual Invoice Generator":
        page_manual_invoice()
    elif page == "Delete Invoice Request":
        page_delete_invoice_request()
    elif page == "Admin Panel":
        if is_admin():
            page_admin_panel()
        else:
            st.error("Admin access only.")
    elif page == "Manager Edit":
        if is_manager():
            page_manager_edit()
        else:
            st.error("Manager access only.")


if __name__ == "__main__":
    main()
