import os
import re
import io
import json
import uuid
import math
import base64
import shutil
import zipfile
from datetime import datetime, date
from pathlib import Path

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

from PIL import Image
import qrcode

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
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
    import cv2
except Exception:
    cv2 = None

try:
    from streamlit_js_eval import get_geolocation
except Exception:
    get_geolocation = None


# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="Selva Motors Smart ERP",
    page_icon="🏍️",
    layout="wide"
)

# =========================================================
# CONSTANTS
# =========================================================
APP_NAME = "SELVA MOTORS SMART ERP"
DATA_DIR = Path("data")
BACKUP_DIR = Path("backups")
PDF_DIR = Path("generated_pdfs")
UPLOAD_DIR = Path("uploads")
EXCEL_FILE = DATA_DIR / "selva_motors_erp_data.xlsx"

COMPANY_LAT = 11.1271       # change your showroom latitude
COMPANY_LON = 78.6569       # change your showroom longitude
ALLOWED_RADIUS_METERS = 300 # change radius
OFFICE_WIFI = "SELVA_MOTORS_WIFI"

DATA_DIR.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(exist_ok=True)
PDF_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

# =========================================================
# CSS
# =========================================================
st.markdown("""
<style>
.main { background: #f5f7fb; }
.block-container { padding-top: 1.2rem; }
.hero-title {
    font-size: 34px;
    font-weight: 900;
    color: #0f172a;
    padding: 10px 0;
}
.small-muted { color:#64748b; font-size:14px; }
.card {
    padding: 18px;
    border-radius: 16px;
    background: white;
    box-shadow: 0 6px 20px rgba(15, 23, 42, 0.08);
    margin-bottom: 16px;
}
.metric-card {
    padding: 18px;
    border-radius: 18px;
    background: linear-gradient(135deg,#111827,#334155);
    color: white;
    box-shadow: 0 8px 20px rgba(0,0,0,0.15);
}
.metric-card h2 { margin:0; font-size:28px; }
.metric-card p { margin:0; color:#cbd5e1; }
.stButton>button {
    border-radius: 10px;
    font-weight: 700;
}
.warning-box {
    border-left: 5px solid #f59e0b;
    padding: 12px;
    background: #fffbeb;
    border-radius: 10px;
}
.success-box {
    border-left: 5px solid #22c55e;
    padding: 12px;
    background: #f0fdf4;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)


# =========================================================
# EXCEL DATABASE LAYER - NO MYSQL, NO SQLALCHEMY
# =========================================================
SHEETS = {
    "employees": [
        "employee_id", "password", "name", "role", "branch", "mobile",
        "device_id", "face_image_path", "status", "created_at"
    ],
    "attendance": [
        "attendance_id", "date", "time", "employee_id", "employee_name",
        "role", "branch", "status", "latitude", "longitude", "distance_m",
        "wifi_ssid", "gps_accuracy", "selfie_path", "face_verified",
        "remarks", "created_at"
    ],
    "invoices": [
        "invoice_id", "upload_date", "employee_id", "employee_name", "branch",
        "invoice_date", "job_card_no", "job_card_last8", "vehicle_reg_no",
        "spare_count", "total_spare_amount", "oil_change_status",
        "total_labour_amount", "gst_amount", "total_invoice_value",
        "customer_name", "vehicle_model", "mobile_number", "ocr_confidence",
        "duplicate_status", "source_file", "raw_text", "created_at"
    ],
    "inventory": [
        "spare_id", "spare_name", "part_no", "category", "supplier",
        "stock_qty", "min_stock", "unit_price", "last_updated"
    ],
    "customers": [
        "customer_id", "customer_name", "mobile_number", "vehicle_reg_no",
        "vehicle_model", "warranty_history", "insurance_expiry",
        "service_due_date", "created_at"
    ],
    "notifications": [
        "notification_id", "date", "time", "type", "message", "status", "created_at"
    ],
    "manual_invoices": [
        "manual_invoice_id", "date", "customer_name", "mobile_number",
        "vehicle_reg_no", "vehicle_model", "spare_total", "labour_total",
        "gst_amount", "discount", "grand_total", "pdf_path", "created_at"
    ],
    "settings": [
        "key", "value", "updated_at"
    ]
}

DEFAULT_EMPLOYEES = [
    ["superadmin", "admin123", "Super Admin", "Super Admin", "Main Branch", "9999999999", "", "", "Active", ""],
    ["mohan", "mohan", "Mohan", "Employee", "Main Branch", "9000000001", "", "", "Active", ""],
    ["ajay", "ajay", "Ajay", "Employee", "Main Branch", "9000000002", "", "", "Active", ""],
    ["prathisha", "prathisha", "Prathisha", "Branch Admin", "Main Branch", "9000000003", "", "", "Active", ""],
    ["manager", "manager123", "Manager", "Manager", "Main Branch", "9000000004", "", "", "Active", ""],
]

DEFAULT_INVENTORY = [
    ["SP001", "Engine Oil", "OIL-10W30", "Oil", "Hero Supplier", 20, 5, 450, ""],
    ["SP002", "Air Filter", "AF-HERO", "Spare", "Hero Supplier", 12, 5, 180, ""],
    ["SP003", "Brake Shoe", "BS-HERO", "Spare", "Hero Supplier", 8, 4, 350, ""],
    ["SP004", "Spark Plug", "PLUG-HERO", "Spare", "Hero Supplier", 15, 5, 120, ""],
]


def now_dt():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_str():
    return datetime.now().strftime("%d-%m-%Y")


def time_str():
    return datetime.now().strftime("%I:%M:%S %p")


def create_excel_if_missing():
    if EXCEL_FILE.exists():
        return

    with pd.ExcelWriter(EXCEL_FILE, engine="openpyxl") as writer:
        for sheet, cols in SHEETS.items():
            df = pd.DataFrame(columns=cols)
            if sheet == "employees":
                df = pd.DataFrame(DEFAULT_EMPLOYEES, columns=cols)
                df["created_at"] = now_dt()
            if sheet == "inventory":
                df = pd.DataFrame(DEFAULT_INVENTORY, columns=cols)
                df["last_updated"] = now_dt()
            if sheet == "settings":
                df = pd.DataFrame([
                    ["company_lat", str(COMPANY_LAT), now_dt()],
                    ["company_lon", str(COMPANY_LON), now_dt()],
                    ["allowed_radius_m", str(ALLOWED_RADIUS_METERS), now_dt()],
                    ["office_wifi", OFFICE_WIFI, now_dt()],
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
        for name, sheet_df in all_sheets.items():
            sheet_df.to_excel(writer, sheet_name=name, index=False)


def append_row(sheet_name, row_dict):
    df = read_sheet(sheet_name)
    for col in SHEETS[sheet_name]:
        if col not in row_dict:
            row_dict[col] = ""
    new_row = pd.DataFrame([row_dict])[SHEETS[sheet_name]]
    df = pd.concat([df, new_row], ignore_index=True)
    write_sheet(sheet_name, df)


def add_notification(n_type, message):
    append_row("notifications", {
        "notification_id": str(uuid.uuid4())[:8],
        "date": today_str(),
        "time": time_str(),
        "type": n_type,
        "message": message,
        "status": "Unread",
        "created_at": now_dt()
    })


create_excel_if_missing()


# =========================================================
# AUTH
# =========================================================
def login_user(employee_id, password):
    emp = read_sheet("employees")
    emp["employee_id"] = emp["employee_id"].astype(str)
    emp["password"] = emp["password"].astype(str)
    row = emp[(emp["employee_id"] == str(employee_id)) & (emp["password"] == str(password))]
    if row.empty:
        return None
    data = row.iloc[0].to_dict()
    if str(data.get("status", "")).lower() != "active":
        return None
    return data


def require_login():
    if not st.session_state.get("logged_in"):
        st.warning("Please login first.")
        st.stop()


def is_admin():
    return st.session_state.get("role") in ["Super Admin", "Branch Admin", "Manager"]


# =========================================================
# GPS / ATTENDANCE HELPERS
# =========================================================
def haversine_distance(lat1, lon1, lat2, lon2):
    try:
        lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
    except Exception:
        return 999999

    radius = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(radius * c, 2)


def save_uploaded_file(uploaded_file, folder=UPLOAD_DIR):
    if uploaded_file is None:
        return ""
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", uploaded_file.name)
    file_path = folder / f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{safe_name}"
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return str(file_path)


# =========================================================
# OCR HELPERS
# =========================================================
def extract_text_from_pdf(file_path):
    text = ""

    if pdfplumber is not None:
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    text += page_text + "\n"
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
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception:
        return ""


def extract_invoice_text(file_path):
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        text = extract_text_from_pdf(file_path)
        if text.strip():
            return text, 85
        return "", 20

    if ext in [".jpg", ".jpeg", ".png", ".webp"]:
        text = extract_text_from_image(file_path)
        confidence = 75 if text.strip() else 20
        return text, confidence

    return "", 0


def money_to_float(value):
    if value is None:
        return 0.0
    txt = str(value)
    txt = txt.replace(",", "")
    found = re.findall(r"\d+(?:\.\d+)?", txt)
    if not found:
        return 0.0
    return float(found[0])


def regex_find(patterns, text, default=""):
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I | re.M)
        if match:
            return match.group(1).strip()
    return default


def parse_invoice_fields(text, confidence):
    clean = text.replace("\n", " ")
    job_card = regex_find([
        r"Job\s*Card\s*(?:No|Number)?\s*[:\-]?\s*([A-Z0-9\-\/]+)",
        r"JC\s*(?:No)?\s*[:\-]?\s*([A-Z0-9\-\/]+)",
        r"(\d{5,}-\d{2}-[A-Z]+-\d{4}-\d+)"
    ], clean)

    vehicle_no = regex_find([
        r"Vehicle\s*(?:Reg|Registration)?\s*(?:No|Number)?\s*[:\-]?\s*([A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{3,4})",
        r"Reg\s*(?:No|Number)?\s*[:\-]?\s*([A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{3,4})",
        r"\b([A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{3,4})\b"
    ], clean)

    invoice_date = regex_find([
        r"Invoice\s*Date\s*[:\-]?\s*(\d{1,2}[-\/]\d{1,2}[-\/]\d{2,4})",
        r"Date\s*[:\-]?\s*(\d{1,2}[-\/]\d{1,2}[-\/]\d{2,4})"
    ], clean)

    customer = regex_find([
        r"Customer\s*Name\s*[:\-]?\s*([A-Za-z .]{3,40})",
        r"Name\s*[:\-]?\s*([A-Za-z .]{3,40})"
    ], clean)

    model = regex_find([
        r"Vehicle\s*Model\s*[:\-]?\s*([A-Za-z0-9 +.-]{3,40})",
        r"Model\s*[:\-]?\s*([A-Za-z0-9 +.-]{3,40})"
    ], clean)

    mobile = regex_find([
        r"Mobile\s*(?:No|Number)?\s*[:\-]?\s*([6-9]\d{9})",
        r"Phone\s*[:\-]?\s*([6-9]\d{9})",
        r"\b([6-9]\d{9})\b"
    ], clean)

    spare_amount = regex_find([
        r"Total\s*Spare\s*Amount\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
        r"Spare\s*Total\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
    ], clean)

    labour_amount = regex_find([
        r"Total\s*Labou?r\s*Amount\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
        r"Labou?r\s*Total\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
    ], clean)

    gst_amount = regex_find([
        r"GST\s*Amount\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
        r"GST\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
    ], clean)

    invoice_value = regex_find([
        r"Total\s*Invoice\s*Value\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
        r"Grand\s*Total\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
        r"Net\s*Amount\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
    ], clean)

    oil_status = "Yes" if re.search(r"\boil\b|engine\s*oil", clean, flags=re.I) else "No"

    spare_count = len(re.findall(r"\b(part|spare|filter|oil|plug|shoe|cable|chain)\b", clean, flags=re.I))
    if spare_count == 0:
        spare_count = ""

    return {
        "invoice_date": invoice_date,
        "job_card_no": job_card,
        "job_card_last8": job_card[-8:] if job_card else "",
        "vehicle_reg_no": vehicle_no.replace(" ", "").upper() if vehicle_no else "",
        "spare_count": spare_count,
        "total_spare_amount": money_to_float(spare_amount),
        "oil_change_status": oil_status,
        "total_labour_amount": money_to_float(labour_amount),
        "gst_amount": money_to_float(gst_amount),
        "total_invoice_value": money_to_float(invoice_value),
        "customer_name": customer,
        "vehicle_model": model,
        "mobile_number": mobile,
        "ocr_confidence": confidence,
        "raw_text": text[:5000]
    }


def duplicate_check(job_card, vehicle_no, invoice_value):
    inv = read_sheet("invoices")
    duplicate_reasons = []

    if job_card and (inv["job_card_no"].astype(str).str.upper() == str(job_card).upper()).any():
        duplicate_reasons.append("Duplicate Job Card")

    if vehicle_no and invoice_value:
        same_vehicle = inv[
            (inv["vehicle_reg_no"].astype(str).str.upper() == str(vehicle_no).upper()) &
            (pd.to_numeric(inv["total_invoice_value"], errors="coerce").fillna(0) == float(invoice_value))
        ]
        if not same_vehicle.empty:
            duplicate_reasons.append("Same Vehicle + Same Amount")

    return ", ".join(duplicate_reasons) if duplicate_reasons else "No Duplicate"


# =========================================================
# PDF GENERATION
# =========================================================
def generate_table_pdf(df, title, filename):
    pdf_path = PDF_DIR / filename
    doc = SimpleDocTemplate(str(pdf_path), pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [Paragraph(f"<b>{title}</b>", styles["Title"]), Spacer(1, 15)]

    if df.empty:
        elements.append(Paragraph("No records found", styles["BodyText"]))
    else:
        temp = df.copy()
        temp = temp.astype(str)
        table_data = [temp.columns.tolist()] + temp.values.tolist()
        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.black),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        elements.append(table)

    doc.build(elements)
    return str(pdf_path)


def create_qr_image(data_text):
    qr = qrcode.QRCode(box_size=4, border=2)
    qr.add_data(data_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    qr_path = PDF_DIR / f"qr_{uuid.uuid4().hex[:8]}.png"
    img.save(qr_path)
    return str(qr_path)


def generate_hero_invoice_pdf(customer, mobile, vehicle, model, spare_rows, labour_rows, discount):
    invoice_id = "HERO-" + datetime.now().strftime("%Y%m%d%H%M%S")
    pdf_path = PDF_DIR / f"{invoice_id}.pdf"

    spare_total = sum(float(r["amount"]) for r in spare_rows)
    labour_total = sum(float(r["amount"]) for r in labour_rows)
    taxable = spare_total + labour_total
    gst_amount = round(taxable * 0.18, 2)
    grand_total = round(taxable + gst_amount - float(discount), 2)

    qr_text = json.dumps({
        "invoice_id": invoice_id,
        "customer": customer,
        "vehicle": vehicle,
        "grand_total": grand_total
    })
    qr_path = create_qr_image(qr_text)

    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    w, h = A4

    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, h - 45, "HERO MOTOCORP SERVICE INVOICE")
    c.setFont("Helvetica", 10)
    c.drawString(40, h - 65, "Selva Motors | Authorized Service Style Invoice")
    c.line(40, h - 78, w - 40, h - 78)

    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, h - 105, f"Invoice ID: {invoice_id}")
    c.drawString(350, h - 105, f"Date: {today_str()}")

    c.setFont("Helvetica", 10)
    c.drawString(40, h - 130, f"Customer Name: {customer}")
    c.drawString(40, h - 148, f"Mobile: {mobile}")
    c.drawString(350, h - 130, f"Vehicle No: {vehicle}")
    c.drawString(350, h - 148, f"Vehicle Model: {model}")

    y = h - 190
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Spare Parts")
    y -= 20
    c.setFont("Helvetica-Bold", 9)
    c.drawString(45, y, "S.No")
    c.drawString(90, y, "Spare Name")
    c.drawString(280, y, "Qty")
    c.drawString(340, y, "Rate")
    c.drawString(430, y, "Amount")
    c.line(40, y - 5, w - 40, y - 5)

    c.setFont("Helvetica", 9)
    y -= 22
    for i, r in enumerate(spare_rows, start=1):
        c.drawString(45, y, str(i))
        c.drawString(90, y, str(r["name"])[:25])
        c.drawString(280, y, str(r["qty"]))
        c.drawString(340, y, f"Rs.{float(r['rate']):.2f}")
        c.drawString(430, y, f"Rs.{float(r['amount']):.2f}")
        y -= 18

    y -= 10
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Labour Charges")
    y -= 20
    c.setFont("Helvetica-Bold", 9)
    c.drawString(45, y, "S.No")
    c.drawString(90, y, "Labour Work")
    c.drawString(430, y, "Amount")
    c.line(40, y - 5, w - 40, y - 5)

    c.setFont("Helvetica", 9)
    y -= 22
    for i, r in enumerate(labour_rows, start=1):
        c.drawString(45, y, str(i))
        c.drawString(90, y, str(r["name"])[:35])
        c.drawString(430, y, f"Rs.{float(r['amount']):.2f}")
        y -= 18

    y -= 15
    c.line(320, y, w - 40, y)
    y -= 18
    c.setFont("Helvetica-Bold", 10)
    c.drawString(340, y, f"Spare Total: Rs.{spare_total:.2f}")
    y -= 16
    c.drawString(340, y, f"Labour Total: Rs.{labour_total:.2f}")
    y -= 16
    c.drawString(340, y, f"GST 18%: Rs.{gst_amount:.2f}")
    y -= 16
    c.drawString(340, y, f"Discount: Rs.{float(discount):.2f}")
    y -= 20
    c.setFont("Helvetica-Bold", 13)
    c.drawString(340, y, f"Grand Total: Rs.{grand_total:.2f}")

    c.drawImage(qr_path, 50, 70, width=80, height=80)
    c.setFont("Helvetica", 8)
    c.drawString(45, 55, "Scan QR to verify invoice")
    c.drawString(350, 90, "Digital Signature")
    c.line(350, 75, 520, 75)

    c.showPage()
    c.save()

    append_row("manual_invoices", {
        "manual_invoice_id": invoice_id,
        "date": today_str(),
        "customer_name": customer,
        "mobile_number": mobile,
        "vehicle_reg_no": vehicle,
        "vehicle_model": model,
        "spare_total": spare_total,
        "labour_total": labour_total,
        "gst_amount": gst_amount,
        "discount": discount,
        "grand_total": grand_total,
        "pdf_path": str(pdf_path),
        "created_at": now_dt()
    })

    return str(pdf_path), grand_total


# =========================================================
# SIDEBAR LOGIN
# =========================================================
def login_page():
    st.markdown('<div class="hero-title">🏍️ SELVA MOTORS SMART ERP</div>', unsafe_allow_html=True)
    st.caption("Excel storage version | No MySQL | No SQLAlchemy")

    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("🔐 Login")
        employee_id = st.text_input("User ID")
        password = st.text_input("Password", type="password")

        if st.button("Login", use_container_width=True):
            user = login_user(employee_id, password)
            if user:
                st.session_state["logged_in"] = True
                st.session_state["employee_id"] = user["employee_id"]
                st.session_state["employee_name"] = user["name"]
                st.session_state["role"] = user["role"]
                st.session_state["branch"] = user["branch"]
                st.success("Login success")
                st.rerun()
            else:
                st.error("Invalid login")

    with c2:
        st.info("""
        Demo Login:

        Super Admin: superadmin / admin123  
        Employee: mohan / mohan  
        Employee: ajay / ajay  
        Branch Admin: prathisha / prathisha  
        Manager: manager / manager123
        """)


def sidebar_menu():
    st.sidebar.title("🏍️ Selva ERP")
    st.sidebar.success(f"{st.session_state.get('employee_name')} | {st.session_state.get('role')}")

    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    role = st.session_state.get("role")

    pages = ["Dashboard", "Attendance", "Upload Invoice", "Reports", "Search", "Customer History", "Manual Invoice Generator"]

    if role in ["Super Admin", "Branch Admin", "Manager"]:
        pages += ["Analytics", "Inventory", "Admin Panel", "Notifications", "Backup"]

    return st.sidebar.radio("Menu", pages)


# =========================================================
# DASHBOARD
# =========================================================
def show_metric(title, value, caption=""):
    st.markdown(f"""
    <div class="metric-card">
        <p>{title}</p>
        <h2>{value}</h2>
        <p>{caption}</p>
    </div>
    """, unsafe_allow_html=True)


def page_dashboard():
    st.markdown('<div class="hero-title">📊 Dashboard</div>', unsafe_allow_html=True)

    inv = read_sheet("invoices")
    att = read_sheet("attendance")
    inv["total_invoice_value"] = pd.to_numeric(inv["total_invoice_value"], errors="coerce").fillna(0)
    inv["total_labour_amount"] = pd.to_numeric(inv["total_labour_amount"], errors="coerce").fillna(0)

    today = today_str()
    today_inv = inv[inv["upload_date"].astype(str) == today]
    today_att = att[att["date"].astype(str) == today]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        show_metric("Today Revenue", f"₹{today_inv['total_invoice_value'].sum():,.0f}", "Invoice value")
    with c2:
        show_metric("Monthly Revenue", f"₹{inv['total_invoice_value'].sum():,.0f}", "All saved invoices")
    with c3:
        show_metric("Today Uploads", len(today_inv), "Invoice count")
    with c4:
        show_metric("Attendance Today", len(today_att), "Staff count")

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Recent Invoices")
        if inv.empty:
            st.info("No invoices")
        else:
            st.dataframe(inv.tail(10), use_container_width=True)

    with col2:
        st.subheader("Spare vs Labour")
        spare = pd.to_numeric(inv["total_spare_amount"], errors="coerce").fillna(0).sum()
        labour = pd.to_numeric(inv["total_labour_amount"], errors="coerce").fillna(0).sum()
        chart_df = pd.DataFrame({"Type": ["Spare", "Labour"], "Amount": [spare, labour]})
        fig = px.pie(chart_df, names="Type", values="Amount", hole=0.35)
        st.plotly_chart(fig, use_container_width=True)


# =========================================================
# ATTENDANCE
# =========================================================
def page_attendance():
    st.markdown('<div class="hero-title">📍 Smart GPS Attendance</div>', unsafe_allow_html=True)

    st.info("Company GPS radius check + selfie + WiFi field. Streamlit Cloud la browser permission allow pannunga.")

    emp_id = st.session_state["employee_id"]
    emp_name = st.session_state["employee_name"]
    role = st.session_state["role"]
    branch = st.session_state["branch"]
    today = today_str()

    att = read_sheet("attendance")
    already = att[
        (att["date"].astype(str) == today) &
        (att["employee_id"].astype(str) == emp_id)
    ]

    if not already.empty:
        st.warning("Today attendance already marked.")
        st.dataframe(already, use_container_width=True)
        return

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Location")
        latitude = st.text_input("Latitude", value="")
        longitude = st.text_input("Longitude", value="")
        gps_accuracy = st.number_input("GPS Accuracy Meter", min_value=0.0, value=20.0)

        if get_geolocation is not None:
            if st.button("📍 Get Current GPS"):
                loc = get_geolocation()
                st.write(loc)
                st.info("GPS values display aana, copy panni Latitude/Longitude fields la paste pannunga.")
        else:
            st.caption("streamlit-js-eval install pannina GPS button work aagum.")

        wifi_ssid = st.text_input("Office WiFi SSID", value="")
        status = st.selectbox("Attendance Status", ["Present", "Half Day Leave"])

    with col2:
        st.subheader("Selfie")
        selfie = st.camera_input("Capture Selfie")

    distance = ""
    allow = False

    if latitude and longitude:
        distance = haversine_distance(latitude, longitude, COMPANY_LAT, COMPANY_LON)
        if distance <= ALLOWED_RADIUS_METERS:
            allow = True
            st.success(f"Inside location radius ✅ Distance: {distance} meter")
        else:
            st.error(f"Outside company radius ❌ Distance: {distance} meter")

    if gps_accuracy > 100:
        st.warning("Fake GPS / low accuracy warning: GPS accuracy is high.")

    if wifi_ssid and wifi_ssid != OFFICE_WIFI:
        st.warning("Office WiFi mismatch warning.")

    if st.button("📥 Mark Attendance", use_container_width=True):
        if not latitude or not longitude:
            st.error("Latitude and Longitude required.")
            return
        if not allow:
            add_notification("Attendance Outside Location", f"{emp_name} tried attendance outside radius.")
            st.error("Attendance blocked. You are outside company location.")
            return

        selfie_path = ""
        if selfie:
            selfie_path = save_uploaded_file(selfie, UPLOAD_DIR)

        face_verified = "Not Enabled"

        append_row("attendance", {
            "attendance_id": str(uuid.uuid4())[:8],
            "date": today,
            "time": time_str(),
            "employee_id": emp_id,
            "employee_name": emp_name,
            "role": role,
            "branch": branch,
            "status": status,
            "latitude": latitude,
            "longitude": longitude,
            "distance_m": distance,
            "wifi_ssid": wifi_ssid,
            "gps_accuracy": gps_accuracy,
            "selfie_path": selfie_path,
            "face_verified": face_verified,
            "remarks": "Excel saved",
            "created_at": now_dt()
        })
        st.success("Attendance saved in Excel.")
        st.rerun()


# =========================================================
# UPLOAD INVOICE
# =========================================================
def page_upload_invoice():
    st.markdown('<div class="hero-title">📄 AI Invoice OCR Upload</div>', unsafe_allow_html=True)

    uploaded = st.file_uploader("Upload PDF / Image / Camera Photo", type=["pdf", "png", "jpg", "jpeg", "webp"])
    emp_id = st.session_state["employee_id"]
    emp_name = st.session_state["employee_name"]
    branch = st.session_state["branch"]

    st.caption("Supported: PDF, scanned image, camera photo, multi-page text PDF. Scanned PDF OCR needs Tesseract setup.")

    sample = {
        "invoice_date": "07-01-2026",
        "job_card_no": "67381-03-RJC-1225-1094",
        "job_card_last8": "1225-1094",
        "vehicle_reg_no": "TN51AT6661",
        "spare_count": 5,
        "total_spare_amount": 5904,
        "oil_change_status": "Yes",
        "total_labour_amount": 1906.88,
        "gst_amount": 0,
        "total_invoice_value": 7811,
        "customer_name": "",
        "vehicle_model": "",
        "mobile_number": "",
        "ocr_confidence": 90,
        "raw_text": "Sample invoice reference"
    }

    if st.button("Use Sample Data"):
        st.session_state["ocr_data"] = sample
        st.session_state["source_file"] = "sample"
        st.rerun()

    if uploaded:
        file_path = save_uploaded_file(uploaded)
        text, confidence = extract_invoice_text(file_path)
        data = parse_invoice_fields(text, confidence)
        st.session_state["ocr_data"] = data
        st.session_state["source_file"] = file_path
        add_notification("New Invoice Upload", f"{emp_name} uploaded invoice file.")
        st.success("OCR extraction completed. Please verify preview below.")

    if "ocr_data" not in st.session_state:
        return

    data = st.session_state["ocr_data"]
    st.subheader("Editable OCR Preview")

    c1, c2, c3 = st.columns(3)
    with c1:
        invoice_date = st.text_input("Invoice Date", value=str(data.get("invoice_date", "")))
        job_card_no = st.text_input("Job Card Number", value=str(data.get("job_card_no", "")))
        vehicle_reg_no = st.text_input("Vehicle Registration Number", value=str(data.get("vehicle_reg_no", "")))
        spare_count = st.number_input("Number of Spare Parts", min_value=0, value=int(data.get("spare_count") or 0))
    with c2:
        spare_amount = st.number_input("Total Spare Amount", min_value=0.0, value=float(data.get("total_spare_amount") or 0.0))
        oil_status = st.selectbox("Oil Change Status", ["Yes", "No"], index=0 if data.get("oil_change_status") == "Yes" else 1)
        labour_amount = st.number_input("Total Labour Amount", min_value=0.0, value=float(data.get("total_labour_amount") or 0.0))
        gst_amount = st.number_input("GST Amount", min_value=0.0, value=float(data.get("gst_amount") or 0.0))
    with c3:
        invoice_value = st.number_input("Total Invoice Value", min_value=0.0, value=float(data.get("total_invoice_value") or 0.0))
        customer_name = st.text_input("Customer Name", value=str(data.get("customer_name", "")))
        vehicle_model = st.text_input("Vehicle Model", value=str(data.get("vehicle_model", "")))
        mobile_number = st.text_input("Mobile Number", value=str(data.get("mobile_number", "")))

    confidence = int(data.get("ocr_confidence") or 0)
    st.progress(min(confidence, 100))
    st.caption(f"OCR Confidence Score: {confidence}%")

    missing = []
    for label, value in {
        "Invoice Date": invoice_date,
        "Job Card Number": job_card_no,
        "Vehicle Number": vehicle_reg_no,
        "Total Invoice Value": invoice_value
    }.items():
        if not value:
            missing.append(label)

    if missing:
        st.warning("Missing fields: " + ", ".join(missing))

    duplicate_status = duplicate_check(job_card_no, vehicle_reg_no, invoice_value)
    if duplicate_status != "No Duplicate":
        st.error("Duplicate Warning: " + duplicate_status)
    else:
        st.success("No duplicate found.")

    with st.expander("Raw OCR Text"):
        st.text_area("OCR Text", value=str(data.get("raw_text", "")), height=180)

    if st.button("💾 Save Invoice to Excel", use_container_width=True):
        if missing:
            st.error("Please fill missing required fields before save.")
            return

        invoice_id = str(uuid.uuid4())[:8]
        append_row("invoices", {
            "invoice_id": invoice_id,
            "upload_date": today_str(),
            "employee_id": emp_id,
            "employee_name": emp_name,
            "branch": branch,
            "invoice_date": invoice_date,
            "job_card_no": job_card_no,
            "job_card_last8": job_card_no[-8:] if job_card_no else "",
            "vehicle_reg_no": vehicle_reg_no.replace(" ", "").upper(),
            "spare_count": spare_count,
            "total_spare_amount": spare_amount,
            "oil_change_status": oil_status,
            "total_labour_amount": labour_amount,
            "gst_amount": gst_amount,
            "total_invoice_value": invoice_value,
            "customer_name": customer_name,
            "vehicle_model": vehicle_model,
            "mobile_number": mobile_number,
            "ocr_confidence": confidence,
            "duplicate_status": duplicate_status,
            "source_file": st.session_state.get("source_file", ""),
            "raw_text": str(data.get("raw_text", ""))[:5000],
            "created_at": now_dt()
        })

        if duplicate_status != "No Duplicate":
            add_notification("Duplicate Invoice Detection", f"{duplicate_status}: {job_card_no}")

        if customer_name or mobile_number or vehicle_reg_no:
            append_row("customers", {
                "customer_id": str(uuid.uuid4())[:8],
                "customer_name": customer_name,
                "mobile_number": mobile_number,
                "vehicle_reg_no": vehicle_reg_no.replace(" ", "").upper(),
                "vehicle_model": vehicle_model,
                "warranty_history": "",
                "insurance_expiry": "",
                "service_due_date": "",
                "created_at": now_dt()
            })

        st.success("Invoice saved in Excel successfully.")
        del st.session_state["ocr_data"]
        st.rerun()


# =========================================================
# REPORTS
# =========================================================
def page_reports():
    st.markdown('<div class="hero-title">📑 Reports Export</div>', unsafe_allow_html=True)

    report_type = st.selectbox("Report Type", ["Invoices", "Attendance", "Inventory", "Customers"])
    sheet_map = {
        "Invoices": "invoices",
        "Attendance": "attendance",
        "Inventory": "inventory",
        "Customers": "customers"
    }

    df = read_sheet(sheet_map[report_type])

    col1, col2, col3 = st.columns(3)
    with col1:
        employee_filter = st.text_input("Employee ID Filter")
    with col2:
        vehicle_filter = st.text_input("Vehicle Number Filter")
    with col3:
        date_filter = st.text_input("Date Filter DD-MM-YYYY")

    filtered = df.copy()

    if employee_filter and "employee_id" in filtered.columns:
        filtered = filtered[filtered["employee_id"].astype(str).str.contains(employee_filter, case=False, na=False)]
    if vehicle_filter and "vehicle_reg_no" in filtered.columns:
        filtered = filtered[filtered["vehicle_reg_no"].astype(str).str.contains(vehicle_filter, case=False, na=False)]
    if date_filter:
        date_cols = [c for c in ["date", "upload_date", "invoice_date"] if c in filtered.columns]
        if date_cols:
            filtered = filtered[filtered[date_cols[0]].astype(str).str.contains(date_filter, case=False, na=False)]

    st.dataframe(filtered, use_container_width=True)

    csv_data = filtered.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", csv_data, file_name=f"{report_type.lower()}_report.csv", mime="text/csv")

    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        filtered.to_excel(writer, sheet_name=report_type, index=False)
    st.download_button(
        "Download Excel",
        excel_buffer.getvalue(),
        file_name=f"{report_type.lower()}_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    if st.button("Generate PDF Report"):
        pdf_path = generate_table_pdf(filtered.head(40), f"{APP_NAME} - {report_type} Report", f"{report_type.lower()}_report.pdf")
        with open(pdf_path, "rb") as f:
            st.download_button("Download PDF", f, file_name=Path(pdf_path).name, mime="application/pdf")


# =========================================================
# ANALYTICS
# =========================================================
def page_analytics():
    st.markdown('<div class="hero-title">📈 Advanced Analytics</div>', unsafe_allow_html=True)

    inv = read_sheet("invoices")
    if inv.empty:
        st.info("No invoice data for analytics.")
        return

    inv["total_invoice_value"] = pd.to_numeric(inv["total_invoice_value"], errors="coerce").fillna(0)
    inv["total_spare_amount"] = pd.to_numeric(inv["total_spare_amount"], errors="coerce").fillna(0)
    inv["total_labour_amount"] = pd.to_numeric(inv["total_labour_amount"], errors="coerce").fillna(0)

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Invoice Count", len(inv))
    c2.metric("Total Revenue", f"₹{inv['total_invoice_value'].sum():,.0f}")
    c3.metric("Oil Change Count", len(inv[inv["oil_change_status"].astype(str).str.lower() == "yes"]))

    st.subheader("Employee-wise Uploads")
    emp_chart = inv.groupby("employee_name").size().reset_index(name="uploads")
    st.plotly_chart(px.bar(emp_chart, x="employee_name", y="uploads"), use_container_width=True)

    st.subheader("Branch-wise Performance")
    branch_chart = inv.groupby("branch")["total_invoice_value"].sum().reset_index()
    st.plotly_chart(px.bar(branch_chart, x="branch", y="total_invoice_value"), use_container_width=True)

    st.subheader("Most Repaired Vehicles")
    vehicle_chart = inv.groupby("vehicle_model").size().reset_index(name="count").sort_values("count", ascending=False).head(10)
    st.plotly_chart(px.bar(vehicle_chart, x="vehicle_model", y="count"), use_container_width=True)

    st.subheader("Revenue Trend")
    trend = inv.groupby("upload_date")["total_invoice_value"].sum().reset_index()
    st.plotly_chart(px.line(trend, x="upload_date", y="total_invoice_value", markers=True), use_container_width=True)


# =========================================================
# INVENTORY
# =========================================================
def page_inventory():
    st.markdown('<div class="hero-title">📦 Inventory Management</div>', unsafe_allow_html=True)

    inv = read_sheet("inventory")
    inv["stock_qty"] = pd.to_numeric(inv["stock_qty"], errors="coerce").fillna(0)
    inv["min_stock"] = pd.to_numeric(inv["min_stock"], errors="coerce").fillna(0)
    inv["unit_price"] = pd.to_numeric(inv["unit_price"], errors="coerce").fillna(0)

    low_stock = inv[inv["stock_qty"] <= inv["min_stock"]]
    if not low_stock.empty:
        st.error(f"Low Stock Alert: {len(low_stock)} items")
        st.dataframe(low_stock, use_container_width=True)

    with st.expander("Add / Purchase Spare Entry"):
        c1, c2, c3 = st.columns(3)
        spare_id = c1.text_input("Spare ID", value="SP" + str(len(inv) + 1).zfill(3))
        spare_name = c2.text_input("Spare Name")
        part_no = c3.text_input("Part Number")
        category = c1.text_input("Category", value="Spare")
        supplier = c2.text_input("Supplier", value="Hero Supplier")
        stock_qty = c3.number_input("Stock Qty", min_value=0, value=1)
        min_stock = c1.number_input("Min Stock", min_value=0, value=5)
        unit_price = c2.number_input("Unit Price", min_value=0.0, value=0.0)

        if st.button("Save Spare"):
            if not spare_name:
                st.error("Spare name required")
            else:
                append_row("inventory", {
                    "spare_id": spare_id,
                    "spare_name": spare_name,
                    "part_no": part_no,
                    "category": category,
                    "supplier": supplier,
                    "stock_qty": stock_qty,
                    "min_stock": min_stock,
                    "unit_price": unit_price,
                    "last_updated": now_dt()
                })
                st.success("Inventory saved in Excel")
                st.rerun()

    st.dataframe(inv, use_container_width=True)


# =========================================================
# SEARCH
# =========================================================
def page_search():
    st.markdown('<div class="hero-title">🔍 Smart Search & Filter</div>', unsafe_allow_html=True)

    inv = read_sheet("invoices")
    query = st.text_input("Search vehicle number / job card / employee ID / customer / mobile")

    if query:
        q = query.lower()
        result = inv[
            inv.astype(str).apply(lambda row: row.str.lower().str.contains(q, na=False).any(), axis=1)
        ]
    else:
        result = inv

    st.dataframe(result, use_container_width=True)


# =========================================================
# CUSTOMER HISTORY
# =========================================================
def page_customer_history():
    st.markdown('<div class="hero-title">🧾 Customer Service History</div>', unsafe_allow_html=True)

    vehicle = st.text_input("Enter Vehicle Number", placeholder="TN51AT6661")
    inv = read_sheet("invoices")
    cust = read_sheet("customers")

    if vehicle:
        vehicle_clean = vehicle.replace(" ", "").upper()
        service_history = inv[inv["vehicle_reg_no"].astype(str).str.upper() == vehicle_clean]
        customer_history = cust[cust["vehicle_reg_no"].astype(str).str.upper() == vehicle_clean]

        st.subheader("Previous Services / Invoices")
        st.dataframe(service_history, use_container_width=True)

        st.subheader("Warranty / Insurance / Due Details")
        st.dataframe(customer_history, use_container_width=True)


# =========================================================
# MANUAL INVOICE GENERATOR
# =========================================================
def page_manual_invoice():
    st.markdown('<div class="hero-title">🧾 Manual Hero Style Invoice Generator</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    customer = c1.text_input("Customer Name")
    mobile = c2.text_input("Mobile Number")
    vehicle = c1.text_input("Vehicle Reg Number")
    model = c2.text_input("Vehicle Model")

    st.subheader("Spare Parts")
    spare_count = st.number_input("Number of Spare Rows", min_value=1, max_value=10, value=2)
    spare_rows = []
    for i in range(spare_count):
        c1, c2, c3, c4 = st.columns(4)
        name = c1.text_input(f"Spare Name {i+1}", key=f"spare_name_{i}")
        qty = c2.number_input(f"Qty {i+1}", min_value=0, value=1, key=f"spare_qty_{i}")
        rate = c3.number_input(f"Rate {i+1}", min_value=0.0, value=0.0, key=f"spare_rate_{i}")
        amount = qty * rate
        c4.metric("Amount", f"₹{amount:.2f}")
        spare_rows.append({"name": name, "qty": qty, "rate": rate, "amount": amount})

    st.subheader("Labour Charges")
    labour_count = st.number_input("Number of Labour Rows", min_value=1, max_value=10, value=1)
    labour_rows = []
    for i in range(labour_count):
        c1, c2 = st.columns(2)
        name = c1.text_input(f"Labour Work {i+1}", key=f"lab_name_{i}")
        amount = c2.number_input(f"Labour Amount {i+1}", min_value=0.0, value=0.0, key=f"lab_amt_{i}")
        labour_rows.append({"name": name, "amount": amount})

    discount = st.number_input("Discount", min_value=0.0, value=0.0)

    if st.button("Generate Invoice PDF", use_container_width=True):
        if not customer or not vehicle:
            st.error("Customer name and vehicle number required.")
            return

        pdf_path, total = generate_hero_invoice_pdf(customer, mobile, vehicle, model, spare_rows, labour_rows, discount)
        st.success(f"Invoice generated. Grand Total ₹{total:.2f}")
        with open(pdf_path, "rb") as f:
            st.download_button("Download Invoice PDF", f, file_name=Path(pdf_path).name, mime="application/pdf")


# =========================================================
# ADMIN PANEL
# =========================================================
def page_admin_panel():
    st.markdown('<div class="hero-title">⚙️ Admin Panel</div>', unsafe_allow_html=True)

    st.subheader("Employees")
    emp = read_sheet("employees")
    st.dataframe(emp, use_container_width=True)

    with st.expander("Add Employee"):
        c1, c2, c3 = st.columns(3)
        employee_id = c1.text_input("Employee ID")
        password = c2.text_input("Password")
        name = c3.text_input("Name")
        role = c1.selectbox("Role", ["Employee", "Branch Admin", "Manager", "Super Admin"])
        branch = c2.text_input("Branch", value="Main Branch")
        mobile = c3.text_input("Mobile")

        if st.button("Create Employee"):
            if not employee_id or not password or not name:
                st.error("Required fields missing")
            else:
                if (emp["employee_id"].astype(str) == employee_id).any():
                    st.error("Employee ID already exists")
                else:
                    append_row("employees", {
                        "employee_id": employee_id,
                        "password": password,
                        "name": name,
                        "role": role,
                        "branch": branch,
                        "mobile": mobile,
                        "device_id": "",
                        "face_image_path": "",
                        "status": "Active",
                        "created_at": now_dt()
                    })
                    st.success("Employee created")
                    st.rerun()

    st.subheader("Excel Database Sheets")
    selected = st.selectbox("Select Sheet", list(SHEETS.keys()))
    st.dataframe(read_sheet(selected), use_container_width=True)


# =========================================================
# NOTIFICATIONS
# =========================================================
def page_notifications():
    st.markdown('<div class="hero-title">🔔 Live Notifications</div>', unsafe_allow_html=True)
    noti = read_sheet("notifications")
    if noti.empty:
        st.info("No notifications")
    else:
        st.dataframe(noti.sort_index(ascending=False), use_container_width=True)


# =========================================================
# BACKUP
# =========================================================
def page_backup():
    st.markdown('<div class="hero-title">💾 Auto Backup System</div>', unsafe_allow_html=True)

    st.info("Local Excel database backup. Streamlit Cloud la files app storage la temporary irukkum; backup download pannunga.")

    if st.button("Create Backup ZIP"):
        backup_name = f"selva_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        backup_path = BACKUP_DIR / backup_name

        with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as z:
            if EXCEL_FILE.exists():
                z.write(EXCEL_FILE, arcname=EXCEL_FILE.name)
            for p in PDF_DIR.glob("*"):
                z.write(p, arcname=f"generated_pdfs/{p.name}")
            for p in UPLOAD_DIR.glob("*"):
                z.write(p, arcname=f"uploads/{p.name}")

        with open(backup_path, "rb") as f:
            st.download_button("Download Backup ZIP", f, file_name=backup_name, mime="application/zip")

    st.subheader("Download Current Excel Database")
    if EXCEL_FILE.exists():
        with open(EXCEL_FILE, "rb") as f:
            st.download_button(
                "Download selva_motors_erp_data.xlsx",
                f,
                file_name="selva_motors_erp_data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )


# =========================================================
# MAIN
# =========================================================
def main():
    if not st.session_state.get("logged_in"):
        login_page()
        return

    page = sidebar_menu()

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
    elif page == "Customer History":
        page_customer_history()
    elif page == "Manual Invoice Generator":
        page_manual_invoice()
    elif page == "Analytics":
        page_analytics()
    elif page == "Inventory":
        page_inventory()
    elif page == "Admin Panel":
        page_admin_panel()
    elif page == "Notifications":
        page_notifications()
    elif page == "Backup":
        page_backup()


if __name__ == "__main__":
    main()
