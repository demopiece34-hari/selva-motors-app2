import os
import re
import io
import json
import math
import time
import uuid
import hashlib
import zipfile
from pathlib import Path
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import plotly.express as px
from PIL import Image

from sqlalchemy.exc import SQLAlchemyError

import pdfplumber
from PyPDF2 import PdfReader
import pytesseract

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfgen import canvas
import qrcode

try:
    from streamlit_js_eval import streamlit_js_eval
except Exception:
    streamlit_js_eval = None

try:
    import face_recognition
except Exception:
    face_recognition = None

APP_TZ = ZoneInfo("Asia/Kolkata")
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
INVOICE_DIR = BASE_DIR / "generated_invoices"
BACKUP_DIR = BASE_DIR / "backups"
for p in [UPLOAD_DIR, INVOICE_DIR, BACKUP_DIR]:
    p.mkdir(exist_ok=True)

st.set_page_config(page_title="Selva Motors Smart ERP", page_icon="🏍️", layout="wide")

# --------------------------- UI STYLE ---------------------------
def inject_css():
    st.markdown(
        """
        <style>
        .stApp {background: linear-gradient(135deg,#f7f9fc 0%,#eef3ff 100%);} 
        .hero-card{padding:22px;border-radius:20px;background:white;box-shadow:0 8px 30px rgba(19,35,65,.08);border:1px solid #e9eef8;}
        .metric-card{padding:18px;border-radius:18px;background:#ffffff;box-shadow:0 4px 18px rgba(0,0,0,.06);}
        .small-muted{color:#6b7280;font-size:13px;}
        .danger-box{padding:12px;border-radius:12px;background:#fff1f2;border:1px solid #fecdd3;}
        .success-box{padding:12px;border-radius:12px;background:#f0fdf4;border:1px solid #bbf7d0;}
        .stButton>button{border-radius:12px;font-weight:700;border:0;background:#111827;color:white;}
        .stDownloadButton>button{border-radius:12px;font-weight:700;}
        </style>
        """,
        unsafe_allow_html=True,
    )

inject_css()

# --------------------------- DATABASE ---------------------------
def get_database_url():
    # Streamlit secrets example:
    # MYSQL_URL="mysql+pymysql://user:password@host:3306/dbname"
    if "MYSQL_URL" in st.secrets:
        return st.secrets["MYSQL_URL"]
    env_url = os.getenv("MYSQL_URL")
    if env_url:
        return env_url
    return f"sqlite:///{BASE_DIR / 'smart_showroom_erp.db'}"

@st.cache_resource
def db_engine():
    return create_engine(get_database_url(), pool_pre_ping=True, future=True)

engine = db_engine()

def run_sql(sql, params=None, fetch=False):
    try:
        with engine.begin() as conn:
            result = conn.execute(text(sql), params or {})
            if fetch:
                return [dict(row._mapping) for row in result]
    except SQLAlchemyError as e:
        st.error(f"Database error: {e}")
        return [] if fetch else None


def init_db():
    ddl = [
        """
        CREATE TABLE IF NOT EXISTS employees(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id VARCHAR(50) UNIQUE,
            name VARCHAR(120), role VARCHAR(50), branch VARCHAR(80),
            password_hash VARCHAR(128), device_id VARCHAR(120),
            registered_face_path TEXT, active INTEGER DEFAULT 1,
            created_at VARCHAR(40)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS attendance(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id VARCHAR(50), name VARCHAR(120), role VARCHAR(50), branch VARCHAR(80),
            date VARCHAR(20), time VARCHAR(30), status VARCHAR(50),
            latitude REAL, longitude REAL, distance_m REAL, gps_accuracy REAL,
            wifi_ssid VARCHAR(120), selfie_path TEXT, face_verified INTEGER,
            fake_gps_flag INTEGER, device_id VARCHAR(120), remarks TEXT,
            created_at VARCHAR(40)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS invoices(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id VARCHAR(80) UNIQUE, upload_date VARCHAR(30), employee_id VARCHAR(50), branch VARCHAR(80),
            invoice_date VARCHAR(30), job_card_no VARCHAR(120), job_card_last8 VARCHAR(20),
            vehicle_reg_no VARCHAR(40), customer_name VARCHAR(160), vehicle_model VARCHAR(120), mobile_number VARCHAR(30),
            spare_parts_count INTEGER, total_spare_amount REAL, oil_change_status VARCHAR(10),
            total_labour_amount REAL, gst_amount REAL, total_invoice_value REAL,
            ocr_confidence REAL, duplicate_flag INTEGER, source_file TEXT, raw_text TEXT, created_at VARCHAR(40)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS inventory(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spare_code VARCHAR(80) UNIQUE, spare_name VARCHAR(160), category VARCHAR(80),
            stock_qty INTEGER, min_qty INTEGER, purchase_price REAL, selling_price REAL,
            supplier VARCHAR(160), barcode VARCHAR(120), updated_at VARCHAR(40)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS notifications(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type VARCHAR(80), title VARCHAR(160), message TEXT,
            severity VARCHAR(30), is_read INTEGER DEFAULT 0, created_at VARCHAR(40)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS customers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_reg_no VARCHAR(40), customer_name VARCHAR(160), mobile_number VARCHAR(30),
            vehicle_model VARCHAR(120), warranty_history TEXT, insurance_expiry VARCHAR(30), service_due_date VARCHAR(30),
            updated_at VARCHAR(40)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS settings(
            key VARCHAR(80) PRIMARY KEY, value TEXT
        )
        """,
    ]
    for statement in ddl:
        run_sql(statement)


def now_str():
    return datetime.now(APP_TZ).strftime("%Y-%m-%d %H:%M:%S")


def today_str():
    return datetime.now(APP_TZ).strftime("%Y-%m-%d")


def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def seed_data():
    rows = run_sql("SELECT COUNT(*) AS c FROM employees", fetch=True)
    if rows and rows[0]["c"] == 0:
        users = [
            ("superadmin", "Super Admin", "Super Admin", "Head Office", "admin123"),
            ("manager", "Manager", "Manager", "Main Branch", "manager123"),
            ("mohan", "Mohan", "Employee", "Main Branch", "mohan"),
            ("ajay", "Ajay", "Employee", "Main Branch", "ajay"),
            ("prathisha", "Prathisha", "Branch Admin", "Main Branch", "prathisha"),
            ("vengadesh", "Vegadesh", "Employee", "Main Branch", "vengadesh"),
        ]
        for emp_id, name, role, branch, pwd in users:
            run_sql(
                """INSERT INTO employees(employee_id,name,role,branch,password_hash,created_at)
                   VALUES(:employee_id,:name,:role,:branch,:password_hash,:created_at)""",
                dict(employee_id=emp_id, name=name, role=role, branch=branch, password_hash=hash_password(pwd), created_at=now_str()),
            )
    default_settings = {
        "company_lat": "13.0827",
        "company_lng": "80.2707",
        "allowed_radius_m": "250",
        "office_wifi_ssid": "SELVA_MOTORS_WIFI",
        "session_timeout_min": "30",
        "gst_percent": "18",
    }
    for k, v in default_settings.items():
        exists = run_sql("SELECT key FROM settings WHERE key=:k", {"k": k}, fetch=True)
        if not exists:
            run_sql("INSERT INTO settings(key,value) VALUES(:k,:v)", {"k": k, "v": v})

init_db()
seed_data()


def read_table(table):
    try:
        return pd.read_sql(f"SELECT * FROM {table}", engine)
    except Exception:
        return pd.DataFrame()


def get_setting(key, default=""):
    row = run_sql("SELECT value FROM settings WHERE key=:k", {"k": key}, fetch=True)
    return row[0]["value"] if row else default


def set_setting(key, value):
    run_sql("DELETE FROM settings WHERE key=:k", {"k": key})
    run_sql("INSERT INTO settings(key,value) VALUES(:k,:v)", {"k": key, "v": str(value)})


def notify(kind, title, message, severity="info"):
    run_sql(
        "INSERT INTO notifications(type,title,message,severity,created_at) VALUES(:type,:title,:message,:severity,:created_at)",
        dict(type=kind, title=title, message=message, severity=severity, created_at=now_str()),
    )

# --------------------------- AUTH ---------------------------
def current_user():
    return st.session_state.get("user")


def logout():
    st.session_state.clear()
    st.rerun()


def login_page():
    st.markdown("<div class='hero-card'><h1>🏍️ Selva Motors Smart ERP</h1><p class='small-muted'>Attendance • Invoice OCR • Inventory • Analytics • Reports</p></div>", unsafe_allow_html=True)
    st.write("")
    col1, col2 = st.columns([1, 1])
    with col1:
        emp_id = st.text_input("Employee/User ID", value="superadmin")
        password = st.text_input("Password", type="password", value="admin123")
        device_id = st.text_input("Device Code", value="demo-device", help="Use same device code to restrict login per employee.")
        use_otp = st.checkbox("OTP login verification", value=False)
        if use_otp and st.button("Generate OTP"):
            otp = str(uuid.uuid4().int)[0:6]
            st.session_state["otp"] = otp
            st.info(f"Demo OTP: {otp}. Production la email/SMS gateway connect pannalam.")
        otp_input = st.text_input("OTP", disabled=not use_otp)
        if st.button("Login"):
            rows = run_sql("SELECT * FROM employees WHERE employee_id=:e AND active=1", {"e": emp_id}, fetch=True)
            if not rows or rows[0]["password_hash"] != hash_password(password):
                st.error("Invalid login")
            elif use_otp and otp_input != st.session_state.get("otp"):
                st.error("Invalid OTP")
            elif rows[0].get("device_id") and rows[0].get("device_id") != device_id:
                st.error("Device restriction enabled. This employee is linked with another device.")
            else:
                if not rows[0].get("device_id"):
                    run_sql("UPDATE employees SET device_id=:d WHERE employee_id=:e", {"d": device_id, "e": emp_id})
                st.session_state["user"] = rows[0]
                st.session_state["login_time"] = time.time()
                st.success("Login successful")
                st.rerun()
    with col2:
        st.info("Demo Login: superadmin/admin123, mohan/mohan, ajay/ajay, prathisha/prathisha")
        st.warning("Production note: OTP needs SMTP/Twilio/WhatsApp Business API credentials.")


def check_session_timeout():
    timeout = int(float(get_setting("session_timeout_min", "30"))) * 60
    if current_user() and time.time() - st.session_state.get("login_time", time.time()) > timeout:
        st.warning("Session timeout. Please login again.")
        logout()

# --------------------------- GPS / ATTENDANCE ---------------------------
def haversine_m(lat1, lon1, lat2, lon2):
    radius = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_browser_location():
    if streamlit_js_eval is None:
        st.warning("Install streamlit-js-eval for live GPS: pip install streamlit-js-eval")
        return None
    location = streamlit_js_eval(
        js_expressions="""
        new Promise((resolve) => {
          navigator.geolocation.getCurrentPosition(
            (pos) => resolve({latitude:pos.coords.latitude, longitude:pos.coords.longitude, accuracy:pos.coords.accuracy, speed:pos.coords.speed}),
            (err) => resolve({error:err.message}),
            {enableHighAccuracy:true, timeout:10000, maximumAge:0}
          );
        })
        """,
        key="gps_location",
    )
    return location


def face_check(selfie_file, employee):
    if not selfie_file:
        return False, "No selfie"
    if face_recognition is None:
        return False, "face_recognition package not installed"
    ref_path = employee.get("registered_face_path")
    if not ref_path or not Path(ref_path).exists():
        return False, "Reference face not registered"
    try:
        selfie_img = face_recognition.load_image_file(selfie_file)
        ref_img = face_recognition.load_image_file(ref_path)
        selfie_enc = face_recognition.face_encodings(selfie_img)
        ref_enc = face_recognition.face_encodings(ref_img)
        if not selfie_enc or not ref_enc:
            return False, "Face not detected"
        matched = face_recognition.compare_faces([ref_enc[0]], selfie_enc[0], tolerance=0.5)[0]
        return bool(matched), "Verified" if matched else "Face mismatch"
    except Exception as e:
        return False, str(e)


def attendance_page():
    user = current_user()
    st.header("📍 Smart GPS Attendance")
    company_lat = float(get_setting("company_lat", "13.0827"))
    company_lng = float(get_setting("company_lng", "80.2707"))
    radius_m = float(get_setting("allowed_radius_m", "250"))
    office_wifi = get_setting("office_wifi_ssid", "SELVA_MOTORS_WIFI")

    c1, c2, c3 = st.columns(3)
    c1.metric("Allowed Radius", f"{radius_m:.0f} m")
    c2.metric("Office WiFi", office_wifi)
    c3.metric("Today", today_str())

    st.write("Click GPS button first. Mobile browser la location permission allow pannunga.")
    location = get_browser_location()
    manual_mode = st.checkbox("Manual GPS fallback for local testing")
    if manual_mode:
        lat = st.number_input("Latitude", value=company_lat, format="%.6f")
        lng = st.number_input("Longitude", value=company_lng, format="%.6f")
        acc = st.number_input("GPS Accuracy meters", value=20.0)
        location = {"latitude": lat, "longitude": lng, "accuracy": acc, "speed": 0}

    if location and isinstance(location, dict) and "error" in location:
        st.error(f"GPS error: {location['error']}")

    status = st.selectbox("Attendance Status", ["Present", "Half Day Leave", "Late Present"])
    wifi_ssid = st.text_input("Office WiFi SSID", placeholder="SELVA_MOTORS_WIFI")
    selfie = st.camera_input("Selfie Attendance")
    remarks = st.text_area("Remarks", height=80)

    if st.button("Mark Attendance"):
        existing = run_sql(
            "SELECT id FROM attendance WHERE employee_id=:e AND date=:d AND status!='Absent'",
            {"e": user["employee_id"], "d": today_str()},
            fetch=True,
        )
        if existing:
            st.warning("Today attendance already marked")
            return
        if not location or "latitude" not in location:
            st.error("GPS location missing. Attendance blocked.")
            return
        lat, lng = float(location["latitude"]), float(location["longitude"])
        accuracy = float(location.get("accuracy") or 999)
        distance = haversine_m(company_lat, company_lng, lat, lng)
        fake_flag = 1 if accuracy > 150 else 0
        wifi_ok = (not office_wifi) or (wifi_ssid.strip().lower() == office_wifi.strip().lower())
        inside = distance <= radius_m
        if not inside:
            notify("attendance", "Outside location attendance blocked", f"{user['name']} tried from {distance:.0f}m away", "danger")
            st.error(f"Attendance blocked. You are {distance:.0f}m away from company radius.")
            return
        if not wifi_ok:
            st.warning("WiFi SSID mismatch. Admin will see warning, but GPS inside radius is accepted.")
        selfie_path = ""
        if selfie:
            selfie_path = str(UPLOAD_DIR / f"selfie_{user['employee_id']}_{uuid.uuid4().hex}.jpg")
            Path(selfie_path).write_bytes(selfie.getvalue())
        face_verified, face_msg = face_check(selfie_path, user) if selfie_path else (False, "No selfie")
        run_sql(
            """INSERT INTO attendance(employee_id,name,role,branch,date,time,status,latitude,longitude,distance_m,gps_accuracy,wifi_ssid,selfie_path,face_verified,fake_gps_flag,device_id,remarks,created_at)
               VALUES(:employee_id,:name,:role,:branch,:date,:time,:status,:latitude,:longitude,:distance_m,:gps_accuracy,:wifi_ssid,:selfie_path,:face_verified,:fake_gps_flag,:device_id,:remarks,:created_at)""",
            dict(employee_id=user["employee_id"], name=user["name"], role=user["role"], branch=user["branch"], date=today_str(), time=datetime.now(APP_TZ).strftime("%I:%M:%S %p"), status=status, latitude=lat, longitude=lng, distance_m=distance, gps_accuracy=accuracy, wifi_ssid=wifi_ssid, selfie_path=selfie_path, face_verified=int(face_verified), fake_gps_flag=fake_flag, device_id=user.get("device_id", ""), remarks=remarks, created_at=now_str()),
        )
        if fake_flag:
            notify("attendance", "Fake GPS suspected", f"{user['name']} GPS accuracy {accuracy}m", "warning")
        st.success(f"Attendance saved. Distance: {distance:.0f}m. Face: {face_msg}")

# --------------------------- OCR ---------------------------
def extract_text_from_pdf(path):
    text_chunks = []
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text_chunks.append(page.extract_text() or "")
    except Exception:
        pass
    if not "\n".join(text_chunks).strip():
        try:
            reader = PdfReader(str(path))
            for page in reader.pages:
                text_chunks.append(page.extract_text() or "")
        except Exception:
            pass
    return "\n".join(text_chunks)


def extract_text_from_image(path):
    try:
        img = Image.open(path)
        return pytesseract.image_to_string(img)
    except Exception as e:
        return f"OCR_ERROR: {e}"


def money_value(text_value):
    if not text_value:
        return 0.0
    cleaned = re.sub(r"[^0-9.]", "", str(text_value))
    try:
        return float(cleaned) if cleaned else 0.0
    except Exception:
        return 0.0


def first_match(patterns, text_data, default=""):
    for p in patterns:
        m = re.search(p, text_data, re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1).strip()
    return default


def parse_invoice_text(text_data):
    clean = re.sub(r"[ \t]+", " ", text_data or "")
    job = first_match([
        r"Job\s*Card\s*(?:No|Number)?\s*[:\-]?\s*([A-Z0-9\-\/]+)",
        r"JC\s*(?:No)?\s*[:\-]?\s*([A-Z0-9\-\/]+)",
        r"(\d{5,}-\d{2}-[A-Z]{2,4}-\d{4}-\d{3,})",
    ], clean)
    vehicle = first_match([
        r"Vehicle\s*(?:Reg|Registration)?\s*(?:No|Number)?\s*[:\-]?\s*([A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{3,4})",
        r"Reg\s*(?:No|Number)?\s*[:\-]?\s*([A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{3,4})",
        r"\b([A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{3,4})\b",
    ], clean).replace(" ", "")
    invoice_date = first_match([
        r"Invoice\s*Date\s*[:\-]?\s*(\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4})",
        r"Date\s*[:\-]?\s*(\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4})",
    ], clean)
    spare_amount = money_value(first_match([
        r"Total\s*Spare\s*(?:Amount)?\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([0-9,]+\.?[0-9]*)",
        r"Parts\s*Total\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([0-9,]+\.?[0-9]*)",
    ], clean))
    labour_amount = money_value(first_match([
        r"Total\s*Labou?r\s*(?:Amount)?\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([0-9,]+\.?[0-9]*)",
        r"Labou?r\s*Charges?\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([0-9,]+\.?[0-9]*)",
    ], clean))
    gst = money_value(first_match([
        r"GST\s*(?:Amount)?\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([0-9,]+\.?[0-9]*)",
        r"CGST\s*\+\s*SGST\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([0-9,]+\.?[0-9]*)",
    ], clean))
    total = money_value(first_match([
        r"Total\s*Invoice\s*(?:Value|Amount)?\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([0-9,]+\.?[0-9]*)",
        r"Grand\s*Total\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([0-9,]+\.?[0-9]*)",
        r"Net\s*Amount\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([0-9,]+\.?[0-9]*)",
    ], clean))
    customer = first_match([r"Customer\s*Name\s*[:\-]?\s*([A-Za-z .]{3,60})", r"Name\s*[:\-]?\s*([A-Za-z .]{3,60})"], clean)
    model = first_match([r"Vehicle\s*Model\s*[:\-]?\s*([A-Za-z0-9 +\-]{3,50})", r"Model\s*[:\-]?\s*([A-Za-z0-9 +\-]{3,50})"], clean)
    mobile = first_match([r"Mobile\s*(?:No|Number)?\s*[:\-]?\s*(\d{10})", r"\b([6-9]\d{9})\b"], clean)
    oil = "Yes" if re.search(r"oil\s*(change|filter|engine oil)|engine\s*oil", clean, re.I) else "No"
    parts_count = len(re.findall(r"\b(part|spare|qty|hsn)\b", clean, re.I))
    fields = {
        "invoice_date": invoice_date,
        "job_card_no": job,
        "job_card_last8": job[-8:] if job else "",
        "vehicle_reg_no": vehicle,
        "spare_parts_count": max(parts_count, 0),
        "total_spare_amount": spare_amount,
        "oil_change_status": oil,
        "total_labour_amount": labour_amount,
        "total_invoice_value": total if total else spare_amount + labour_amount + gst,
        "gst_amount": gst,
        "customer_name": customer,
        "vehicle_model": model,
        "mobile_number": mobile,
    }
    present = sum(1 for v in fields.values() if str(v).strip() not in ["", "0", "0.0"])
    confidence = round((present / len(fields)) * 100, 2)
    return fields, confidence


def upload_invoice_page():
    user = current_user()
    st.header("📄 PDF Invoice OCR & Auto Extraction")
    file = st.file_uploader("Upload PDF / scanned image / camera photo", type=["pdf", "png", "jpg", "jpeg"])
    if file:
        saved_path = UPLOAD_DIR / f"{uuid.uuid4().hex}_{file.name}"
        saved_path.write_bytes(file.getvalue())
        ext = saved_path.suffix.lower()
        if ext == ".pdf":
            raw_text = extract_text_from_pdf(saved_path)
        else:
            raw_text = extract_text_from_image(saved_path)
        fields, confidence = parse_invoice_text(raw_text)
        st.session_state["ocr_preview"] = {"fields": fields, "confidence": confidence, "raw_text": raw_text, "source_file": str(saved_path)}

    if "ocr_preview" in st.session_state:
        data = st.session_state["ocr_preview"]["fields"]
        conf = st.session_state["ocr_preview"]["confidence"]
        st.metric("OCR Confidence", f"{conf}%")
        if conf < 60:
            st.warning("Low confidence. Please verify all values before save.")
        with st.expander("Raw OCR Text"):
            st.text_area("Text", st.session_state["ocr_preview"]["raw_text"], height=220)
        st.subheader("Editable OCR Preview")
        c1, c2, c3 = st.columns(3)
        with c1:
            invoice_date = st.text_input("Invoice Date", data.get("invoice_date", ""))
            job_card_no = st.text_input("Job Card Number", data.get("job_card_no", ""))
            vehicle_reg_no = st.text_input("Vehicle Reg No", data.get("vehicle_reg_no", ""))
            customer_name = st.text_input("Customer Name", data.get("customer_name", ""))
        with c2:
            vehicle_model = st.text_input("Vehicle Model", data.get("vehicle_model", ""))
            mobile_number = st.text_input("Mobile Number", data.get("mobile_number", ""))
            spare_parts_count = st.number_input("No. of Spare Parts", min_value=0, value=int(data.get("spare_parts_count", 0) or 0))
            oil_change_status = st.selectbox("Oil Change Status", ["Yes", "No"], index=0 if data.get("oil_change_status") == "Yes" else 1)
        with c3:
            total_spare_amount = st.number_input("Total Spare Amount", min_value=0.0, value=float(data.get("total_spare_amount", 0) or 0))
            total_labour_amount = st.number_input("Total Labour Amount", min_value=0.0, value=float(data.get("total_labour_amount", 0) or 0))
            gst_amount = st.number_input("GST Amount", min_value=0.0, value=float(data.get("gst_amount", 0) or 0))
            total_invoice_value = st.number_input("Total Invoice Value", min_value=0.0, value=float(data.get("total_invoice_value", 0) or 0))

        missing = [name for name, val in {"Invoice Date": invoice_date, "Job Card": job_card_no, "Vehicle Reg No": vehicle_reg_no, "Total": total_invoice_value}.items() if not str(val).strip() or float(val) == 0 if isinstance(val, float)]
        if missing:
            st.warning("Missing important fields: " + ", ".join(missing))
        dup = run_sql(
            "SELECT invoice_id, job_card_no, vehicle_reg_no FROM invoices WHERE job_card_no=:j OR vehicle_reg_no=:v",
            {"j": job_card_no, "v": vehicle_reg_no},
            fetch=True,
        )
        duplicate_flag = 1 if dup else 0
        if duplicate_flag:
            st.error("Possible duplicate invoice/job card/vehicle upload detected.")
        if st.button("Save Invoice Data"):
            invoice_id = f"INV-{datetime.now(APP_TZ).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            run_sql(
                """INSERT INTO invoices(invoice_id,upload_date,employee_id,branch,invoice_date,job_card_no,job_card_last8,vehicle_reg_no,customer_name,vehicle_model,mobile_number,spare_parts_count,total_spare_amount,oil_change_status,total_labour_amount,gst_amount,total_invoice_value,ocr_confidence,duplicate_flag,source_file,raw_text,created_at)
                   VALUES(:invoice_id,:upload_date,:employee_id,:branch,:invoice_date,:job_card_no,:job_card_last8,:vehicle_reg_no,:customer_name,:vehicle_model,:mobile_number,:spare_parts_count,:total_spare_amount,:oil_change_status,:total_labour_amount,:gst_amount,:total_invoice_value,:ocr_confidence,:duplicate_flag,:source_file,:raw_text,:created_at)""",
                dict(invoice_id=invoice_id, upload_date=today_str(), employee_id=user["employee_id"], branch=user["branch"], invoice_date=invoice_date, job_card_no=job_card_no, job_card_last8=job_card_no[-8:] if job_card_no else "", vehicle_reg_no=vehicle_reg_no, customer_name=customer_name, vehicle_model=vehicle_model, mobile_number=mobile_number, spare_parts_count=spare_parts_count, total_spare_amount=total_spare_amount, oil_change_status=oil_change_status, total_labour_amount=total_labour_amount, gst_amount=gst_amount, total_invoice_value=total_invoice_value, ocr_confidence=conf, duplicate_flag=duplicate_flag, source_file=st.session_state["ocr_preview"]["source_file"], raw_text=st.session_state["ocr_preview"]["raw_text"][:8000], created_at=now_str()),
            )
            run_sql(
                "INSERT INTO customers(vehicle_reg_no,customer_name,mobile_number,vehicle_model,service_due_date,updated_at) VALUES(:v,:c,:m,:model,:due,:u)",
                {"v": vehicle_reg_no, "c": customer_name, "m": mobile_number, "model": vehicle_model, "due": (date.today() + timedelta(days=90)).isoformat(), "u": now_str()},
            )
            notify("invoice", "New invoice uploaded", f"{invoice_id} by {user['name']}", "success")
            st.success(f"Invoice saved: {invoice_id}")
            del st.session_state["ocr_preview"]

# --------------------------- REPORTS ---------------------------
def create_report_pdf(df, title, filename):
    path = BASE_DIR / filename
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=20, leftMargin=20, topMargin=30, bottomMargin=20)
    styles = getSampleStyleSheet()
    elements = [Paragraph(f"<b>{title}</b>", styles["Title"]), Spacer(1, 14)]
    if df.empty:
        elements.append(Paragraph("No records", styles["BodyText"]))
    else:
        show = df.astype(str).head(35)
        data = [show.columns.tolist()] + show.values.tolist()
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.black),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 6),
        ]))
        elements.append(table)
    doc.build(elements)
    return path


def reports_page():
    st.header("📊 Reports & Smart Search")
    invoices = read_table("invoices")
    if invoices.empty:
        st.info("No invoices yet")
        return
    q = st.text_input("Search vehicle / job card / employee / customer / mobile")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        branch = st.selectbox("Branch", ["All"] + sorted(invoices["branch"].dropna().unique().tolist()))
    with c2:
        employee = st.selectbox("Employee", ["All"] + sorted(invoices["employee_id"].dropna().unique().tolist()))
    with c3:
        min_amount = st.number_input("Min Amount", value=0.0)
    with c4:
        max_amount = st.number_input("Max Amount", value=float(invoices["total_invoice_value"].max() or 999999), min_value=0.0)

    df = invoices.copy()
    if q:
        mask = pd.Series(False, index=df.index)
        for col in ["vehicle_reg_no", "job_card_no", "employee_id", "customer_name", "mobile_number", "invoice_date"]:
            mask = mask | df[col].astype(str).str.contains(q, case=False, na=False)
        df = df[mask]
    if branch != "All":
        df = df[df["branch"] == branch]
    if employee != "All":
        df = df[df["employee_id"] == employee]
    df = df[(pd.to_numeric(df["total_invoice_value"], errors="coerce").fillna(0) >= min_amount) & (pd.to_numeric(df["total_invoice_value"], errors="coerce").fillna(0) <= max_amount)]
    st.dataframe(df, use_container_width=True)

    report_cols = ["upload_date", "employee_id", "job_card_no", "vehicle_reg_no", "total_spare_amount", "total_labour_amount", "gst_amount", "total_invoice_value", "oil_change_status"]
    export_df = df[[c for c in report_cols if c in df.columns]]
    csv = export_df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", csv, "invoice_report.csv", "text/csv")
    excel_buf = io.BytesIO()
    with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="Invoice Report")
    st.download_button("Download Excel", excel_buf.getvalue(), "invoice_report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    pdf_path = create_report_pdf(export_df, "SELVA MOTORS - INVOICE REPORT", "invoice_report.pdf")
    st.download_button("Download PDF", pdf_path.read_bytes(), "invoice_report.pdf", "application/pdf")

# --------------------------- ANALYTICS ---------------------------
def dashboard_page():
    st.header("📈 Real-Time Dashboard")
    invoices = read_table("invoices")
    attendance = read_table("attendance")
    today = today_str()
    today_inv = invoices[invoices.get("upload_date", pd.Series(dtype=str)).astype(str) == today] if not invoices.empty else pd.DataFrame()
    month_prefix = datetime.now(APP_TZ).strftime("%Y-%m")
    month_inv = invoices[invoices.get("upload_date", pd.Series(dtype=str)).astype(str).str.startswith(month_prefix)] if not invoices.empty else pd.DataFrame()
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Today Revenue", f"₹{pd.to_numeric(today_inv.get('total_invoice_value', pd.Series(dtype=float)), errors='coerce').sum():,.0f}")
    c2.metric("Monthly Revenue", f"₹{pd.to_numeric(month_inv.get('total_invoice_value', pd.Series(dtype=float)), errors='coerce').sum():,.0f}")
    c3.metric("Invoice Count", len(today_inv))
    c4.metric("Oil Change", int((today_inv.get("oil_change_status", pd.Series(dtype=str)) == "Yes").sum()) if not today_inv.empty else 0)
    c5.metric("Labour Income", f"₹{pd.to_numeric(today_inv.get('total_labour_amount', pd.Series(dtype=float)), errors='coerce').sum():,.0f}")
    today_att = attendance[attendance.get("date", pd.Series(dtype=str)).astype(str) == today] if not attendance.empty else pd.DataFrame()
    c6.metric("Attendance", len(today_att))

    if not invoices.empty:
        df = invoices.copy()
        df["total_spare_amount"] = pd.to_numeric(df["total_spare_amount"], errors="coerce").fillna(0)
        df["total_labour_amount"] = pd.to_numeric(df["total_labour_amount"], errors="coerce").fillna(0)
        chart_data = pd.DataFrame({"Type": ["Spare", "Labour"], "Amount": [df["total_spare_amount"].sum(), df["total_labour_amount"].sum()]})
        st.plotly_chart(px.pie(chart_data, names="Type", values="Amount", title="Spare vs Labour"), use_container_width=True)
        emp = df.groupby("employee_id", as_index=False).agg(uploads=("id", "count"), revenue=("total_invoice_value", "sum")).sort_values("uploads", ascending=False)
        st.plotly_chart(px.bar(emp, x="employee_id", y="uploads", title="Top Employee Ranking"), use_container_width=True)
        veh = df.groupby("vehicle_model", as_index=False).agg(count=("id", "count")).sort_values("count", ascending=False).head(10)
        st.plotly_chart(px.bar(veh, x="vehicle_model", y="count", title="Most Repaired Vehicles"), use_container_width=True)

# --------------------------- MANUAL INVOICE ---------------------------
def generate_invoice_pdf(invoice):
    invoice_id = invoice["invoice_id"]
    path = INVOICE_DIR / f"{invoice_id}.pdf"
    qr_data = json.dumps({"invoice_id": invoice_id, "vehicle": invoice["vehicle_reg_no"], "customer": invoice["customer_name"], "total": invoice["grand_total"]})
    qr_img = qrcode.make(qr_data)
    qr_path = INVOICE_DIR / f"{invoice_id}_qr.png"
    qr_img.save(qr_path)
    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    c.setFont("Helvetica-Bold", 18)
    c.drawString(35, height - 45, "HERO MOTOCORP - SERVICE INVOICE")
    c.setFont("Helvetica", 9)
    c.drawString(35, height - 62, "Selva Motors | Authorized Service Style Invoice")
    c.drawImage(str(qr_path), width - 110, height - 110, 75, 75)
    y = height - 120
    c.setFont("Helvetica-Bold", 10)
    c.drawString(35, y, f"Invoice ID: {invoice_id}")
    c.drawString(300, y, f"Date: {today_str()}")
    y -= 20
    c.setFont("Helvetica", 10)
    details = [
        f"Customer: {invoice['customer_name']}", f"Mobile: {invoice['mobile_number']}",
        f"Vehicle No: {invoice['vehicle_reg_no']}", f"Model: {invoice['vehicle_model']}",
        f"Job Card: {invoice['job_card_no']}",
    ]
    for item in details:
        c.drawString(35, y, item)
        y -= 16
    y -= 8
    c.setFont("Helvetica-Bold", 10)
    c.drawString(35, y, "Spare Parts / Labour")
    y -= 18
    c.line(35, y, width - 35, y)
    y -= 16
    c.setFont("Helvetica-Bold", 9)
    c.drawString(40, y, "Item")
    c.drawString(300, y, "Qty")
    c.drawString(360, y, "Rate")
    c.drawString(450, y, "Amount")
    y -= 12
    c.setFont("Helvetica", 9)
    for row in invoice["items"]:
        c.drawString(40, y, row["name"][:35])
        c.drawRightString(320, y, str(row["qty"]))
        c.drawRightString(410, y, f"{row['rate']:.2f}")
        c.drawRightString(510, y, f"{row['amount']:.2f}")
        y -= 15
    y -= 10
    c.line(350, y, 520, y)
    y -= 18
    c.setFont("Helvetica-Bold", 10)
    for label, value in [("Sub Total", invoice["subtotal"]), ("GST", invoice["gst"]), ("Discount", -invoice["discount"]), ("Grand Total", invoice["grand_total"] )]:
        c.drawString(360, y, label)
        c.drawRightString(515, y, f"₹{value:.2f}")
        y -= 18
    c.setFont("Helvetica", 9)
    c.drawString(35, 90, "Digital Signature: Selva Motors")
    c.line(35, 75, 180, 75)
    c.drawString(360, 90, "Customer Signature")
    c.line(360, 75, 520, 75)
    c.showPage()
    c.save()
    return path


def manual_invoice_page():
    st.header("🧾 Manual Hero-Style Invoice Generator")
    c1, c2, c3 = st.columns(3)
    with c1:
        customer_name = st.text_input("Customer Name")
        mobile_number = st.text_input("Mobile Number")
    with c2:
        vehicle_reg_no = st.text_input("Vehicle Reg No", "TN51AT6661")
        vehicle_model = st.text_input("Vehicle Model", "Splendor Plus")
    with c3:
        job_card_no = st.text_input("Job Card No", "67381-03-RJC-1225-1094")
        discount = st.number_input("Discount", min_value=0.0, value=0.0)
    gst_percent = float(get_setting("gst_percent", "18"))
    st.subheader("Items")
    items = []
    item_count = st.number_input("Number of rows", min_value=1, max_value=20, value=3)
    for i in range(int(item_count)):
        a, b, c = st.columns([3, 1, 1])
        name = a.text_input(f"Item {i+1}", key=f"item_name_{i}", value="Engine Oil" if i == 0 else "Labour" if i == 1 else "")
        qty = b.number_input("Qty", min_value=0.0, value=1.0, key=f"qty_{i}")
        rate = c.number_input("Rate", min_value=0.0, value=0.0, key=f"rate_{i}")
        if name:
            items.append({"name": name, "qty": qty, "rate": rate, "amount": qty * rate})
    subtotal = sum(x["amount"] for x in items)
    gst = subtotal * gst_percent / 100
    grand_total = subtotal + gst - discount
    st.metric("Grand Total", f"₹{grand_total:,.2f}")
    if st.button("Generate Invoice PDF"):
        invoice_id = f"MAN-{datetime.now(APP_TZ).strftime('%Y%m%d')}-{uuid.uuid4().hex[:5].upper()}"
        invoice = dict(invoice_id=invoice_id, customer_name=customer_name, mobile_number=mobile_number, vehicle_reg_no=vehicle_reg_no, vehicle_model=vehicle_model, job_card_no=job_card_no, discount=discount, gst=gst, subtotal=subtotal, grand_total=grand_total, items=items)
        path = generate_invoice_pdf(invoice)
        st.success("Invoice generated")
        st.download_button("Download Invoice PDF", path.read_bytes(), path.name, "application/pdf")

# --------------------------- INVENTORY ---------------------------
def inventory_page():
    st.header("📦 Inventory Management")
    with st.expander("Add / Update Spare"):
        c1, c2, c3 = st.columns(3)
        spare_code = c1.text_input("Spare Code / Barcode")
        spare_name = c2.text_input("Spare Name")
        category = c3.text_input("Category")
        c4, c5, c6, c7 = st.columns(4)
        stock_qty = c4.number_input("Stock Qty", min_value=0, value=0)
        min_qty = c5.number_input("Low Stock Min Qty", min_value=0, value=5)
        purchase_price = c6.number_input("Purchase Price", min_value=0.0, value=0.0)
        selling_price = c7.number_input("Selling Price", min_value=0.0, value=0.0)
        supplier = st.text_input("Supplier")
        if st.button("Save Spare") and spare_code and spare_name:
            run_sql("DELETE FROM inventory WHERE spare_code=:c", {"c": spare_code})
            run_sql(
                "INSERT INTO inventory(spare_code,spare_name,category,stock_qty,min_qty,purchase_price,selling_price,supplier,barcode,updated_at) VALUES(:spare_code,:spare_name,:category,:stock_qty,:min_qty,:purchase_price,:selling_price,:supplier,:barcode,:updated_at)",
                dict(spare_code=spare_code, spare_name=spare_name, category=category, stock_qty=stock_qty, min_qty=min_qty, purchase_price=purchase_price, selling_price=selling_price, supplier=supplier, barcode=spare_code, updated_at=now_str()),
            )
            st.success("Inventory saved")
    inv = read_table("inventory")
    if not inv.empty:
        st.dataframe(inv, use_container_width=True)
        low = inv[pd.to_numeric(inv["stock_qty"], errors="coerce") <= pd.to_numeric(inv["min_qty"], errors="coerce")]
        if not low.empty:
            st.error("Low stock warning")
            st.dataframe(low, use_container_width=True)
            for _, row in low.iterrows():
                notify("inventory", "Low stock warning", f"{row['spare_name']} stock {row['stock_qty']}", "warning")

# --------------------------- CUSTOMER HISTORY / ADMIN ---------------------------
def customer_history_page():
    st.header("🔎 Customer Service History")
    vehicle = st.text_input("Vehicle Number")
    if vehicle:
        inv = read_table("invoices")
        hist = inv[inv["vehicle_reg_no"].astype(str).str.upper() == vehicle.upper()] if not inv.empty else pd.DataFrame()
        st.subheader("Previous Services / Invoices")
        st.dataframe(hist, use_container_width=True)
        cust = read_table("customers")
        ch = cust[cust["vehicle_reg_no"].astype(str).str.upper() == vehicle.upper()] if not cust.empty else pd.DataFrame()
        if not ch.empty:
            st.subheader("Warranty / Insurance / Due Date")
            st.dataframe(ch, use_container_width=True)


def admin_panel_page():
    st.header("⚙️ Admin Panel")
    tabs = st.tabs(["Employees", "Notifications", "Settings", "Backup"])
    with tabs[0]:
        st.subheader("Create Employee")
        c1, c2, c3, c4 = st.columns(4)
        emp_id = c1.text_input("Employee ID")
        name = c2.text_input("Name")
        role = c3.selectbox("Role", ["Employee", "Manager", "Branch Admin", "Super Admin"])
        branch = c4.text_input("Branch", "Main Branch")
        pwd = st.text_input("Password", type="password")
        face = st.file_uploader("Register face image", type=["jpg", "jpeg", "png"])
        if st.button("Create / Update Employee") and emp_id and pwd:
            face_path = ""
            if face:
                face_path = str(UPLOAD_DIR / f"face_{emp_id}.jpg")
                Path(face_path).write_bytes(face.getvalue())
            run_sql("DELETE FROM employees WHERE employee_id=:e", {"e": emp_id})
            run_sql(
                "INSERT INTO employees(employee_id,name,role,branch,password_hash,registered_face_path,active,created_at) VALUES(:employee_id,:name,:role,:branch,:password_hash,:registered_face_path,1,:created_at)",
                dict(employee_id=emp_id, name=name, role=role, branch=branch, password_hash=hash_password(pwd), registered_face_path=face_path, created_at=now_str()),
            )
            st.success("Employee saved")
        st.dataframe(read_table("employees"), use_container_width=True)
    with tabs[1]:
        st.dataframe(read_table("notifications").sort_values("id", ascending=False) if not read_table("notifications").empty else pd.DataFrame(), use_container_width=True)
    with tabs[2]:
        company_lat = st.text_input("Company Latitude", get_setting("company_lat"))
        company_lng = st.text_input("Company Longitude", get_setting("company_lng"))
        radius = st.text_input("Allowed Radius Meter", get_setting("allowed_radius_m"))
        wifi = st.text_input("Office WiFi SSID", get_setting("office_wifi_ssid"))
        gst = st.text_input("GST Percent", get_setting("gst_percent"))
        if st.button("Save Settings"):
            for k, v in {"company_lat": company_lat, "company_lng": company_lng, "allowed_radius_m": radius, "office_wifi_ssid": wifi, "gst_percent": gst}.items():
                set_setting(k, v)
            st.success("Settings saved")
    with tabs[3]:
        if st.button("Create Backup ZIP"):
            backup_path = BACKUP_DIR / f"backup_{datetime.now(APP_TZ).strftime('%Y%m%d_%H%M%S')}.zip"
            with zipfile.ZipFile(backup_path, "w") as z:
                for table in ["employees", "attendance", "invoices", "inventory", "customers", "notifications"]:
                    df = read_table(table)
                    csv_path = BACKUP_DIR / f"{table}.csv"
                    df.to_csv(csv_path, index=False)
                    z.write(csv_path, f"{table}.csv")
                db_file = BASE_DIR / "smart_showroom_erp.db"
                if db_file.exists():
                    z.write(db_file, "smart_showroom_erp.db")
            st.download_button("Download Backup", backup_path.read_bytes(), backup_path.name, "application/zip")

# --------------------------- VOICE COMMAND ---------------------------
def voice_command_box():
    st.sidebar.markdown("### 🎙️ Voice Command")
    cmd = st.sidebar.text_input("Type voice command text", placeholder="Show today report")
    if cmd:
        low = cmd.lower()
        if "upload" in low and "invoice" in low:
            st.sidebar.info("Go to Upload Invoice page")
        elif "today" in low and "report" in low:
            st.sidebar.info("Go to Reports page and filter today")
        elif "search vehicle" in low:
            st.sidebar.info("Go to Customer History page")

# --------------------------- APP ROUTER ---------------------------
def main():
    check_session_timeout()
    if not current_user():
        login_page()
        return
    user = current_user()
    st.sidebar.success(f"{user['name']} | {user['role']}")
    if st.sidebar.button("Logout"):
        logout()
    voice_command_box()
    pages = ["Dashboard", "Attendance", "Upload Invoice", "Reports", "Analytics", "Inventory", "Manual Invoice Generator", "Customer History", "Admin Panel", "Settings"]
    allowed_employee = ["Dashboard", "Attendance", "Upload Invoice", "Reports", "Manual Invoice Generator", "Customer History"]
    if user["role"] == "Employee":
        pages = allowed_employee
    page = st.sidebar.radio("Pages", pages)
    st.markdown(f"<div class='hero-card'><h2>🏍️ Selva Motors Smart Employee Attendance & AI Invoice Management</h2><p class='small-muted'>Logged in as {user['employee_id']} • Branch: {user['branch']}</p></div>", unsafe_allow_html=True)
    st.write("")
    if page in ["Dashboard", "Analytics"]:
        dashboard_page()
    elif page == "Attendance":
        attendance_page()
    elif page == "Upload Invoice":
        upload_invoice_page()
    elif page == "Reports":
        reports_page()
    elif page == "Inventory":
        inventory_page()
    elif page == "Manual Invoice Generator":
        manual_invoice_page()
    elif page == "Customer History":
        customer_history_page()
    elif page in ["Admin Panel", "Settings"]:
        if user["role"] not in ["Super Admin", "Branch Admin", "Manager"]:
            st.error("Access denied")
        else:
            admin_panel_page()

if __name__ == "__main__":
    main()

