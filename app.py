
from __future__ import annotations

import base64
import io
import json
import math
import os
import re
import time
from datetime import datetime, date
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from zoneinfo import ZoneInfo

try:
    import gspread
    from google.oauth2.service_account import Credentials
except Exception:
    gspread = None
    Credentials = None

try:
    from PIL import Image
except Exception:
    Image = None

try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    import pdfplumber
except Exception:
    pdfplumber = None

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.pdfgen import canvas
except Exception:
    colors = None
    A4 = None

try:
    import qrcode
except Exception:
    qrcode = None


# ============================================================
# SELVA MOTORS — Single-file Google Sheet ERP
# Two-user architecture:
# ENTRY  -> data entry only
# REPORT -> read-only reports
# ============================================================

st.set_page_config(page_title="Selva Motors ERP", page_icon="🏍️", layout="wide")

APP_TZ = ZoneInfo("Asia/Kolkata")
BASE_DIR = Path(".")
REPORT_DIR = BASE_DIR / "generated_reports"
UPLOAD_DIR = BASE_DIR / "uploads"
REPORT_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

SHEET_ID_ENV = "SHEET_ID"

SYSTEM_USERS = {
    "ENTRY": {"password": "ENTRY123", "purpose": "Data Entry Only", "role": "ENTRY"},
    "REPORT": {"password": "REPORT123", "purpose": "Read Only / Reports", "role": "REPORT"},
}

SHEET_ALIASES = {
    "technicians": ["technicians", "Technicians", "Technician Master", "technician_master"],
    "customers": ["customers", "Customers", "customer_master"],
    "invoices": ["invoices", "Invoices", "invoice_data"],
    "attendance": ["attendance", "Attendance"],
    "job_cards": ["job_cards", "Job Cards", "jobcards"],
    "manual_bills": ["manual_bills", "Manual Bills", "manual_invoices"],
    "ocr_uploads": ["ocr_uploads", "OCR Uploads", "ocr_logs"],
}

SHEET_COLUMNS = {
    "technicians": ["Technician ID", "Technician Name", "Status", "Role"],
    "customers": ["Customer ID", "Date", "Customer Name", "Mobile", "Vehicle Number", "Bike Model", "Address", "Notes"],
    "invoices": ["Invoice ID", "Date", "Time", "Technician Name", "Customer Name", "Invoice Number", "Job Card Number", "Registration Number", "Bike Model", "Service Type", "Labour Amount", "Spare Amount", "Oil Amount", "Total Amount", "Entry Type", "Status"],
    "attendance": ["Date", "Time", "Technician Name", "Attendance Status", "Notes"],
    "job_cards": ["Job Card ID", "Date", "Time", "Technician Name", "Customer Name", "Registration Number", "Bike Model", "Complaint", "Service Type", "Status", "Notes"],
    "manual_bills": ["Manual Bill ID", "Date", "Time", "Technician Name", "Customer Name", "Registration Number", "Bike Model", "Labour Amount", "Spare Amount", "Oil Amount", "Total Amount", "PDF File", "Status"],
    "ocr_uploads": ["Upload ID", "Date", "Time", "File Name", "Technician Name", "Customer Name", "Invoice Number", "Job Card Number", "Registration Number", "Bike Model", "Service Type", "Labour Amount", "Spare Amount", "Oil Amount", "Total Amount", "Extracted Text"],
}

DEFAULT_TECHNICIANS = [
    {"Technician ID": "T001", "Technician Name": "Selvam", "Status": "Active", "Role": "Technician"},
    {"Technician ID": "T002", "Technician Name": "Kumar", "Status": "Active", "Role": "Technician"},
    {"Technician ID": "T003", "Technician Name": "Mani", "Status": "Active", "Role": "Technician"},
    {"Technician ID": "T004", "Technician Name": "Ravi", "Status": "Active", "Role": "Technician"},
]

CURRENCY = "₹"


# ============================================================
# Utilities
# ============================================================

def now() -> datetime:
    return datetime.now(APP_TZ)

def today_str() -> str:
    return now().strftime("%d-%m-%Y")

def time_str() -> str:
    return now().strftime("%I:%M %p")

def stamp_str() -> str:
    return now().strftime("%d-%m-%Y %I:%M:%S %p")

def money(v: Any) -> float:
    try:
        return float(str(v).replace(",", "").strip() or 0)
    except Exception:
        return 0.0

def fmt_money(v: Any) -> str:
    try:
        return f"{CURRENCY}{money(v):,.2f}"
    except Exception:
        return f"{CURRENCY}0.00"

def safe_text(v: Any) -> str:
    return "" if v is None else str(v).strip()

def normalize(s: Any) -> str:
    return re.sub(r"\s+", " ", safe_text(s)).strip().lower()

def safe_filename(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", safe_text(name))
    return name[:140] if name else "file"

def next_id(prefix: str, existing_ids: list[str]) -> str:
    nums = []
    for val in existing_ids:
        m = re.search(r"(\d+)$", safe_text(val))
        if m:
            nums.append(int(m.group(1)))
    return f"{prefix}{(max(nums) + 1) if nums else 1:04d}"

def app_msg(title: str, body: str, icon: str = "⚡") -> None:
    st.markdown(
        f"""
        <div style="padding:16px 18px;border-radius:18px;background:linear-gradient(135deg,#ffffff,#f8fafc);border:1px solid #e2e8f0;box-shadow:0 12px 30px rgba(15,23,42,.06);margin:8px 0 14px 0;">
          <div style="font-size:18px;font-weight:900;color:#0f172a;">{icon} {title}</div>
          <div style="color:#475569;font-size:14px;margin-top:4px;">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def hero_loader(message: str = "Loading...", sub: str = "Please wait") -> None:
    st.markdown(
        f"""
        <div style="position:fixed;inset:0;z-index:99999;background:rgba(248,250,252,.98);display:flex;align-items:center;justify-content:center;">
          <div style="text-align:center;padding:28px 34px;border-radius:28px;border:2px solid #fecaca;box-shadow:0 30px 80px rgba(127,29,29,.18);background:white;min-width:320px;">
            <div style="font-size:52px;font-weight:1000;letter-spacing:3px;color:#e11d48;">HERO</div>
            <div style="width:68px;height:68px;border-radius:50%;border:7px solid #fee2e2;border-top-color:#e11d48;margin:18px auto 14px auto;animation:spin 0.8s linear infinite;"></div>
            <div style="font-size:18px;font-weight:900;color:#111827;">{message}</div>
            <div style="font-size:13px;color:#475569;margin-top:8px;">{sub}</div>
          </div>
        </div>
        <style>@keyframes spin{{to{{transform:rotate(360deg)}}}}</style>
        """,
        unsafe_allow_html=True,
    )

def big_button(label: str, key: str) -> bool:
    return st.button(label, key=key, use_container_width=True)

def card(title: str, value: str, caption: str = "") -> None:
    st.markdown(
        f"""
        <div style="padding:18px 16px;border-radius:20px;background:linear-gradient(135deg,#ffffff,#f8fafc);border:1px solid #e2e8f0;box-shadow:0 12px 28px rgba(15,23,42,.06);min-height:100px;">
          <div style="font-size:13px;color:#64748b;font-weight:800;text-transform:uppercase;letter-spacing:.7px;">{title}</div>
          <div style="font-size:30px;font-weight:900;color:#0f172a;margin-top:6px;">{value}</div>
          <div style="font-size:12px;color:#64748b;margin-top:6px;">{caption}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def section(title: str, subtitle: str = "") -> None:
    st.markdown(f"<h2 style='margin-bottom:2px;color:#0f172a;font-weight:950;'>{title}</h2>", unsafe_allow_html=True)
    if subtitle:
        st.markdown(f"<div style='color:#64748b;margin-bottom:10px;'>{subtitle}</div>", unsafe_allow_html=True)

def login_panel():
    st.markdown(
        """
        <style>
        .stApp { background: linear-gradient(135deg,#f8fafc,#eef2ff 48%,#f0fdf4); }
        .login-card {
            max-width: 650px;
            margin: 6vh auto;
            padding: 32px;
            border-radius: 28px;
            background: rgba(255,255,255,.9);
            border: 1px solid rgba(226,232,240,.9);
            box-shadow: 0 30px 80px rgba(15,23,42,.18);
        }
        .login-title { font-size: 32px; font-weight: 950; color:#0f172a; margin:0; }
        .login-sub { color:#16a34a; font-weight:800; letter-spacing:2px; font-size:12px; margin-top:4px; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<div class='login-card'>", unsafe_allow_html=True)
    st.markdown("<div class='login-title'>SELVA MOTORS ERP</div>", unsafe_allow_html=True)
    st.markdown("<div class='login-sub'>ENTRY / REPORT ACCESS</div>", unsafe_allow_html=True)
    st.caption("Tamil friendly: Data Entry மட்டும் / Reports மட்டும்")
    cols = st.columns(2)
    with cols[0]:
        st.info("ENTRY\n\nData Entry Only")
    with cols[1]:
        st.info("REPORT\n\nRead Only / Reports")

    user_id = st.text_input("User ID", placeholder="ENTRY or REPORT").strip().upper()
    password = st.text_input("Password", type="password", placeholder="ENTRY123 or REPORT123")
    if st.button("Login", use_container_width=True):
        if user_id in SYSTEM_USERS and SYSTEM_USERS[user_id]["password"] == password:
            st.session_state["auth"] = True
            st.session_state["user_id"] = user_id
            st.session_state["role"] = SYSTEM_USERS[user_id]["role"]
            st.session_state["current_page"] = "Invoice Entry" if user_id == "ENTRY" else "Dashboard"
            for k in list(st.session_state.keys()):
                if k.startswith("show_"):
                    st.session_state[k] = False
            st.rerun()
        else:
            st.error("Invalid credentials")
    st.markdown("</div>", unsafe_allow_html=True)

# ============================================================
# Google Sheets
# ============================================================

def get_sheet_id() -> str:
    try:
        return safe_text(st.secrets.get(SHEET_ID_ENV, "")).strip()
    except Exception:
        return safe_text(os.environ.get(SHEET_ID_ENV, "")).strip()

def google_client():
    if gspread is None or Credentials is None:
        return None, "Missing gspread / google-auth dependencies"
    try:
        secrets = st.secrets["gcp_service_account"]
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(secrets, scopes=scope)
        return gspread.authorize(creds), ""
    except Exception as e:
        return None, str(e)

def open_spreadsheet():
    client, err = google_client()
    sheet_id = get_sheet_id()
    if client is None:
        raise RuntimeError(err or "Google client unavailable")
    if not sheet_id:
        raise RuntimeError("Missing SHEET_ID in Streamlit secrets")
    return client.open_by_key(sheet_id)

def existing_worksheets(ss) -> list[str]:
    try:
        return [ws.title for ws in ss.worksheets()]
    except Exception:
        return []

def resolve_sheet_title(ss, canonical: str) -> str:
    titles = set(existing_worksheets(ss))
    for name in SHEET_ALIASES.get(canonical, [canonical]):
        if name in titles:
            return name
    return canonical

def ensure_sheet(ss, canonical: str, headers: list[str]):
    title = resolve_sheet_title(ss, canonical)
    try:
        ws = ss.worksheet(title)
    except Exception:
        ws = ss.add_worksheet(title=title, rows=100, cols=max(len(headers) + 5, 20))
    try:
        values = ws.get_all_values()
        if not values and headers:
            ws.update([headers], value_input_option="USER_ENTERED")
    except Exception:
        pass
    return ws

def ws_to_df(ws, columns: list[str]) -> pd.DataFrame:
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame(columns=columns)
    header = values[0]
    data = values[1:]
    df = pd.DataFrame(data, columns=header)
    for c in columns:
        if c not in df.columns:
            df[c] = ""
    df = df[[c for c in columns if c in df.columns]]
    return df.fillna("")

@st.cache_data(ttl=10, show_spinner=False)
def read_sheet(canonical: str) -> pd.DataFrame:
    ss = open_spreadsheet()
    headers = SHEET_COLUMNS[canonical]
    ws = ensure_sheet(ss, canonical, headers)
    return ws_to_df(ws, headers)

def append_row(canonical: str, row: dict[str, Any]) -> tuple[bool, str]:
    try:
        ss = open_spreadsheet()
        headers = SHEET_COLUMNS[canonical]
        ws = ensure_sheet(ss, canonical, headers)
        current = ws.row_values(1)
        if not current:
            ws.update([headers], value_input_option="USER_ENTERED")
            current = headers
        headers = current
        row_values = [safe_text(row.get(col, "")) for col in headers]
        ws.append_row(row_values, value_input_option="USER_ENTERED")
        read_sheet.clear()
        return True, "Saved"
    except Exception as e:
        return False, str(e)

def read_small_technicians() -> pd.DataFrame:
    try:
        df = read_sheet("technicians")
        if df.empty:
            return df
        active = df.copy()
        if "Status" in active.columns:
            active = active[active["Status"].astype(str).str.lower().isin(["active", "yes", "1", "true"]) | (active["Status"].astype(str).str.strip() == "")]
        return active.fillna("")
    except Exception:
        return pd.DataFrame(columns=SHEET_COLUMNS["technicians"])

def technician_names() -> list[str]:
    df = read_small_technicians()
    names = []
    if not df.empty and "Technician Name" in df.columns:
        names = [safe_text(x) for x in df["Technician Name"].tolist() if safe_text(x)]
    if not names:
        names = [x["Technician Name"] for x in DEFAULT_TECHNICIANS]
    return names

def bootstrap_default_technicians():
    try:
        df = read_sheet("technicians")
        if df.empty:
            for row in DEFAULT_TECHNICIANS:
                append_row("technicians", row)
    except Exception:
        pass

# ============================================================
# OCR
# ============================================================

def save_upload(uploaded) -> Path:
    target = UPLOAD_DIR / safe_filename(uploaded.name)
    target.write_bytes(uploaded.getbuffer())
    return target

def extract_text_from_file(path: Path) -> str:
    suffix = path.suffix.lower()
    text = ""
    if suffix == ".pdf" and pdfplumber is not None:
        try:
            with pdfplumber.open(str(path)) as pdf:
                parts = []
                for pg in pdf.pages:
                    parts.append(pg.extract_text() or "")
                text = "\n".join(parts)
        except Exception:
            text = ""
    elif suffix in {".png", ".jpg", ".jpeg", ".webp"} and pytesseract is not None and Image is not None:
        try:
            text = pytesseract.image_to_string(Image.open(str(path)))
        except Exception:
            text = ""
    return text or ""

def find_first(patterns: list[str], text: str, default: str = "") -> str:
    for pat in patterns:
        m = re.search(pat, text, re.I | re.M)
        if m:
            if m.lastindex:
                return safe_text(m.group(1))
            return safe_text(m.group(0))
    return default

def parse_invoice_text(text: str) -> dict[str, Any]:
    t = text or ""
    invoice_no = find_first([r"Invoice\s*(?:No|Number)?\s*[:\-]?\s*([A-Z0-9\/\-_]+)", r"Bill\s*No\s*[:\-]?\s*([A-Z0-9\/\-_]+)"], t)
    job_no = find_first([r"Job\s*Card\s*(?:No|Number)?\s*[:\-]?\s*([A-Z0-9\/\-_]+)"], t)
    reg_no = find_first([r"(?:Reg(?:istration)?\.?\s*No|Vehicle\s*No|Vehicle\s*Number)\s*[:\-]?\s*([A-Z0-9\-\/]+)"], t)
    bike = find_first([r"(?:Bike|Model)\s*[:\-]?\s*([A-Za-z0-9 \-]+)"], t)
    tech = find_first([r"(?:Technician|Mechanic)\s*[:\-]?\s*([A-Za-z .]+)"], t)
    customer = find_first([r"(?:Customer|Name)\s*[:\-]?\s*([A-Za-z .]+)"], t)
    service = find_first([r"(?:Service\s*Type|Type)\s*[:\-]?\s*([A-Za-z0-9 /-]+)"], t)
    labour = find_first([r"(?:Labour|Labor)\s*(?:Amount)?\s*[:\-]?\s*([0-9,.]+)"], t)
    spare = find_first([r"(?:Spare|Spare\s*Amount|Parts\s*Amount)\s*[:\-]?\s*([0-9,.]+)"], t)
    oil = find_first([r"(?:Oil|Oil\s*Amount)\s*[:\-]?\s*([0-9,.]+)"], t)
    total = find_first([r"(?:Total|Grand\s*Total)\s*(?:Amount)?\s*[:\-]?\s*([0-9,.]+)"], t)
    return {
        "Invoice Number": invoice_no,
        "Job Card Number": job_no,
        "Registration Number": reg_no,
        "Bike Model": bike,
        "Technician Name": tech,
        "Customer Name": customer,
        "Service Type": service,
        "Labour Amount": money(labour),
        "Spare Amount": money(spare),
        "Oil Amount": money(oil),
        "Total Amount": money(total) if total else round(money(labour) + money(spare) + money(oil), 2),
        "Extracted Text": t[:4000],
    }

# ============================================================
# PDF
# ============================================================

def build_pdf_table_pdf(path: Path, title: str, subtitle: str, rows: list[list[Any]]) -> Path:
    if colors is None:
        path.write_text("PDF generation unavailable")
        return path
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=16, leftMargin=16, topMargin=18, bottomMargin=18)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="SelvaSmall", fontName="Helvetica", fontSize=9, leading=11))
    story = [
        Paragraph(f"<b>{title}</b>", styles["Title"]),
        Paragraph(subtitle, styles["Normal"]),
        Spacer(1, 8),
    ]
    table = Table(rows, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(table)
    doc.build(story)
    return path

def df_for_pdf(df: pd.DataFrame, cols: list[str]) -> list[list[str]]:
    if df is None or df.empty:
        return [["No data found"]]
    tmp = df.copy()
    for c in cols:
        if c not in tmp.columns:
            tmp[c] = ""
    tmp = tmp[cols]
    rows = [cols]
    for _, r in tmp.iterrows():
        rows.append([safe_text(r.get(c, ""))[:60] for c in cols])
    return rows

def generate_report_pdf(df: pd.DataFrame, title: str, filename: str, cols: list[str], subtitle: str = "SELVA MOTORS ERP") -> Path:
    pdf_path = REPORT_DIR / filename
    return build_pdf_table_pdf(pdf_path, title, subtitle, df_for_pdf(df, cols))

def generate_invoice_pdf(data: dict[str, Any], filename: str) -> Path:
    pdf_path = REPORT_DIR / filename
    rows = [
        ["Field", "Value"],
        ["Invoice ID", safe_text(data.get("Invoice ID"))],
        ["Date", safe_text(data.get("Date"))],
        ["Time", safe_text(data.get("Time"))],
        ["Technician Name", safe_text(data.get("Technician Name"))],
        ["Customer Name", safe_text(data.get("Customer Name"))],
        ["Invoice Number", safe_text(data.get("Invoice Number"))],
        ["Job Card Number", safe_text(data.get("Job Card Number"))],
        ["Registration Number", safe_text(data.get("Registration Number"))],
        ["Bike Model", safe_text(data.get("Bike Model"))],
        ["Service Type", safe_text(data.get("Service Type"))],
        ["Labour Amount", fmt_money(data.get("Labour Amount"))],
        ["Spare Amount", fmt_money(data.get("Spare Amount"))],
        ["Oil Amount", fmt_money(data.get("Oil Amount"))],
        ["Total Amount", fmt_money(data.get("Total Amount"))],
        ["Entry Type", safe_text(data.get("Entry Type"))],
        ["Status", safe_text(data.get("Status"))],
    ]
    return build_pdf_table_pdf(pdf_path, "Selva Motors Invoice", "Professional invoice summary", rows)

def generate_manual_bill_pdf(data: dict[str, Any]) -> Path:
    return generate_invoice_pdf(data, f"manual_bill_{safe_filename(data.get('Manual Bill ID', stamp_str()))}.pdf")

# ============================================================
# Authentication and permissions
# ============================================================

def is_logged_in() -> bool:
    return bool(st.session_state.get("auth"))

def role() -> str:
    return safe_text(st.session_state.get("role", ""))

def require_role(expected: str) -> bool:
    if role() != expected:
        st.error("Access denied")
        return False
    return True

def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# ============================================================
# Data entry pages
# ============================================================

def page_technician_master():
    section("Technician Master", "Drop-down list setup for all forms.")
    if not require_role("ENTRY"):
        return
    with st.form("tech_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            tech_id = st.text_input("Technician ID", placeholder="T005")
        with c2:
            tech_name = st.text_input("Technician Name", placeholder="Arun")
        with c3:
            status = st.selectbox("Status", ["Active", "Inactive"])
        with c4:
            tech_role = st.text_input("Role", value="Technician")
        submit = st.form_submit_button("Save Technician", use_container_width=True)
    if submit:
        if not tech_name.strip():
            st.error("Technician name required")
        else:
            if not tech_id.strip():
                existing = read_sheet("technicians")
                tech_id = next_id("T", existing["Technician ID"].tolist()) if not existing.empty and "Technician ID" in existing.columns else "T001"
            ok, msg = append_row("technicians", {
                "Technician ID": tech_id.strip(),
                "Technician Name": tech_name.strip(),
                "Status": status,
                "Role": tech_role.strip() or "Technician",
            })
            if ok:
                st.success("Technician saved")
                st.rerun()
            else:
                st.error(msg)
    st.subheader("Technician List")
    tech_df = read_small_technicians()
    st.dataframe(tech_df, use_container_width=True, hide_index=True)

def page_customer_entry():
    section("Customer Entry", "Save customer details directly to Google Sheet.")
    if not require_role("ENTRY"):
        return
    with st.form("customer_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            customer_name = st.text_input("Customer Name")
            mobile = st.text_input("Mobile")
        with c2:
            vehicle_no = st.text_input("Vehicle Number")
            bike_model = st.text_input("Bike Model")
        with c3:
            address = st.text_area("Address")
            notes = st.text_area("Notes")
        submit = st.form_submit_button("Save Customer", use_container_width=True)
    if submit:
        if not customer_name.strip():
            st.error("Customer name required")
        else:
            existing = read_sheet("customers")
            cid = next_id("C", existing["Customer ID"].tolist()) if not existing.empty and "Customer ID" in existing.columns else "C001"
            ok, msg = append_row("customers", {
                "Customer ID": cid,
                "Date": today_str(),
                "Customer Name": customer_name,
                "Mobile": mobile,
                "Vehicle Number": vehicle_no,
                "Bike Model": bike_model,
                "Address": address,
                "Notes": notes,
            })
            if ok:
                st.success("Customer saved")
                st.rerun()
            else:
                st.error(msg)

def page_attendance_entry():
    section("Attendance Entry", "Select technician and mark Present / Absent / Leave.")
    if not require_role("ENTRY"):
        return
    techs = technician_names()
    if not techs:
        st.warning("No technicians found. Add in Technician Master.")
        return
    with st.form("attendance_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            tech_name = st.selectbox("Select Technician", techs)
            att_date = st.text_input("Date", value=today_str())
        with c2:
            status = st.selectbox("Attendance Status", ["Present", "Absent", "Leave"])
            att_time = st.text_input("Time", value=time_str())
        with c3:
            notes = st.text_area("Notes")
        submit = st.form_submit_button("Save Attendance", use_container_width=True)
    if submit:
        ok, msg = append_row("attendance", {
            "Date": att_date,
            "Time": att_time,
            "Technician Name": tech_name,
            "Attendance Status": status,
            "Notes": notes,
        })
        if ok:
            st.success("Attendance saved")
            st.rerun()
        else:
            st.error(msg)

def page_job_card_entry():
    section("Job Card Entry", "Select technician and save job card details.")
    if not require_role("ENTRY"):
        return
    techs = technician_names()
    with st.form("job_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            tech_name = st.selectbox("Assigned Technician", techs)
            customer_name = st.text_input("Customer Name")
            reg_no = st.text_input("Registration Number")
        with c2:
            bike_model = st.text_input("Bike Model")
            service_type = st.selectbox("Service Type", ["FSC", "Paid Service", "General", "Accident", "Joyride"])
            status = st.selectbox("Status", ["Open", "In Progress", "Completed"])
        with c3:
            complaint = st.text_area("Complaint")
            notes = st.text_area("Notes")
        submit = st.form_submit_button("Save Job Card", use_container_width=True)
    if submit:
        existing = read_sheet("job_cards")
        jid = next_id("JC", existing["Job Card ID"].tolist()) if not existing.empty and "Job Card ID" in existing.columns else "JC0001"
        ok, msg = append_row("job_cards", {
            "Job Card ID": jid,
            "Date": today_str(),
            "Time": time_str(),
            "Technician Name": tech_name,
            "Customer Name": customer_name,
            "Registration Number": reg_no,
            "Bike Model": bike_model,
            "Complaint": complaint,
            "Service Type": service_type,
            "Status": status,
            "Notes": notes,
        })
        if ok:
            st.success("Job card saved")
            st.rerun()
        else:
            st.error(msg)

def save_invoice_common(entry_type: str, tech_name: str, customer_name: str, invoice_no: str, job_no: str, reg_no: str, bike_model: str, service_type: str, labour: float, spare: float, oil: float, total: float, status: str = "Saved", extra: dict[str, Any] | None = None):
    existing = read_sheet("invoices")
    inv_id = next_id("INV", existing["Invoice ID"].tolist()) if not existing.empty and "Invoice ID" in existing.columns else "INV0001"
    row = {
        "Invoice ID": inv_id,
        "Date": today_str(),
        "Time": time_str(),
        "Technician Name": tech_name,
        "Customer Name": customer_name,
        "Invoice Number": invoice_no,
        "Job Card Number": job_no,
        "Registration Number": reg_no,
        "Bike Model": bike_model,
        "Service Type": service_type,
        "Labour Amount": labour,
        "Spare Amount": spare,
        "Oil Amount": oil,
        "Total Amount": total,
        "Entry Type": entry_type,
        "Status": status,
    }
    if extra:
        row.update(extra)
    ok, msg = append_row("invoices", row)
    if ok:
        return True, inv_id, msg, row
    return False, inv_id, msg, row

def page_invoice_entry():
    section("Invoice Entry", "Fast direct save to Google Sheet. No heavy sheet read.")
    if not require_role("ENTRY"):
        return
    techs = technician_names()
    with st.form("invoice_form", clear_on_submit=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            tech_name = st.selectbox("Assigned Technician", techs)
            customer_name = st.text_input("Customer Name")
            invoice_no = st.text_input("Invoice Number")
            job_no = st.text_input("Job Card Number")
        with c2:
            reg_no = st.text_input("Registration Number")
            bike_model = st.text_input("Bike Model")
            service_type = st.selectbox("Service Type", ["FSC", "Paid Service", "General", "Accident", "Joyride"])
            labour = st.number_input("Labour Amount", min_value=0.0, step=1.0, format="%.2f")
        with c3:
            spare = st.number_input("Spare Amount", min_value=0.0, step=1.0, format="%.2f")
            oil = st.number_input("Oil Amount", min_value=0.0, step=1.0, format="%.2f")
            total = st.number_input("Total Amount", min_value=0.0, step=1.0, format="%.2f")
            status = st.selectbox("Status", ["Saved", "Billed", "Pending"])
        submit = st.form_submit_button("Save Invoice", use_container_width=True)
    if submit:
        ok, inv_id, msg, row = save_invoice_common("Manual Entry", tech_name, customer_name, invoice_no, job_no, reg_no, bike_model, service_type, labour, spare, oil, total, status=status)
        if ok:
            st.success(f"Invoice saved: {inv_id}")
            pdf = generate_invoice_pdf(row, f"{safe_filename(inv_id)}.pdf")
            with open(pdf, "rb") as f:
                st.download_button("Download Invoice PDF", f, file_name=pdf.name, mime="application/pdf", use_container_width=True)
            st.rerun()
        else:
            st.error(msg)

def page_ocr_upload():
    section("OCR Invoice Upload", "Upload PDF/Image. Extract text and save to Google Sheet.")
    if not require_role("ENTRY"):
        return
    techs = technician_names()
    uploaded = st.file_uploader("Upload Invoice PDF / Image", type=["pdf", "png", "jpg", "jpeg", "webp"])
    parsed = None
    ocr_text = ""
    if uploaded:
        path = save_upload(uploaded)
        ocr_text = extract_text_from_file(path)
        parsed = parse_invoice_text(ocr_text)
        st.success("OCR extraction completed")
        with st.expander("Extracted Text Preview", expanded=False):
            st.text_area("OCR Text", value=ocr_text[:5000], height=240)
    with st.form("ocr_form", clear_on_submit=False):
        c1, c2, c3 = st.columns(3)
        default_tech = parsed.get("Technician Name") if parsed else techs[0]
        default_customer = parsed.get("Customer Name") if parsed else ""
        default_invoice = parsed.get("Invoice Number") if parsed else ""
        default_job = parsed.get("Job Card Number") if parsed else ""
        default_reg = parsed.get("Registration Number") if parsed else ""
        default_bike = parsed.get("Bike Model") if parsed else ""
        default_service = parsed.get("Service Type") if parsed else "General"
        default_labour = parsed.get("Labour Amount") if parsed else 0.0
        default_spare = parsed.get("Spare Amount") if parsed else 0.0
        default_oil = parsed.get("Oil Amount") if parsed else 0.0
        default_total = parsed.get("Total Amount") if parsed else 0.0
        with c1:
            tech_name = st.selectbox("Assigned Technician", techs, index=max(0, techs.index(default_tech)) if default_tech in techs else 0)
            customer_name = st.text_input("Customer Name", value=default_customer)
            invoice_no = st.text_input("Invoice Number", value=default_invoice)
            job_no = st.text_input("Job Card Number", value=default_job)
        with c2:
            reg_no = st.text_input("Registration Number", value=default_reg)
            bike_model = st.text_input("Bike Model", value=default_bike)
            service_type = st.text_input("Service Type", value=default_service)
            labour = st.number_input("Labour Amount", min_value=0.0, step=1.0, format="%.2f", value=float(default_labour or 0.0))
        with c3:
            spare = st.number_input("Spare Amount", min_value=0.0, step=1.0, format="%.2f", value=float(default_spare or 0.0))
            oil = st.number_input("Oil Amount", min_value=0.0, step=1.0, format="%.2f", value=float(default_oil or 0.0))
            total = st.number_input("Total Amount", min_value=0.0, step=1.0, format="%.2f", value=float(default_total or 0.0))
            status = st.selectbox("Status", ["Saved", "OCR Saved", "Pending"])
        submit = st.form_submit_button("Save OCR Invoice", use_container_width=True)
    if submit:
        ok, inv_id, msg, row = save_invoice_common("OCR Upload", tech_name, customer_name, invoice_no, job_no, reg_no, bike_model, service_type, labour, spare, oil, total, status=status, extra={})
        if ok:
            append_row("ocr_uploads", {
                "Upload ID": f"UP{inv_id}",
                "Date": today_str(),
                "Time": time_str(),
                "File Name": safe_text(uploaded.name) if uploaded else "",
                "Technician Name": tech_name,
                "Customer Name": customer_name,
                "Invoice Number": invoice_no,
                "Job Card Number": job_no,
                "Registration Number": reg_no,
                "Bike Model": bike_model,
                "Service Type": service_type,
                "Labour Amount": labour,
                "Spare Amount": spare,
                "Oil Amount": oil,
                "Total Amount": total,
                "Extracted Text": ocr_text[:4000],
            })
            st.success(f"OCR invoice saved: {inv_id}")
            pdf = generate_invoice_pdf(row, f"{safe_filename(inv_id)}_ocr.pdf")
            with open(pdf, "rb") as f:
                st.download_button("Download PDF", f, file_name=pdf.name, mime="application/pdf", use_container_width=True)
            st.rerun()
        else:
            st.error(msg)

def page_manual_bill():
    section("Manual Bill Entry", "Save a bill and generate PDF.")
    if not require_role("ENTRY"):
        return
    techs = technician_names()
    with st.form("manual_bill_form", clear_on_submit=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            tech_name = st.selectbox("Assigned Technician", techs)
            customer_name = st.text_input("Customer Name")
            reg_no = st.text_input("Registration Number")
        with c2:
            bike_model = st.text_input("Bike Model")
            labour = st.number_input("Labour Amount", min_value=0.0, step=1.0, format="%.2f")
            spare = st.number_input("Spare Amount", min_value=0.0, step=1.0, format="%.2f")
        with c3:
            oil = st.number_input("Oil Amount", min_value=0.0, step=1.0, format="%.2f")
            total = st.number_input("Total Amount", min_value=0.0, step=1.0, format="%.2f")
            status = st.selectbox("Status", ["Saved", "Billed", "Pending"])
        submit = st.form_submit_button("Save Manual Bill", use_container_width=True)
    if submit:
        existing = read_sheet("manual_bills")
        bill_id = next_id("MB", existing["Manual Bill ID"].tolist()) if not existing.empty and "Manual Bill ID" in existing.columns else "MB0001"
        row = {
            "Manual Bill ID": bill_id,
            "Date": today_str(),
            "Time": time_str(),
            "Technician Name": tech_name,
            "Customer Name": customer_name,
            "Registration Number": reg_no,
            "Bike Model": bike_model,
            "Labour Amount": labour,
            "Spare Amount": spare,
            "Oil Amount": oil,
            "Total Amount": total,
            "PDF File": f"{bill_id}.pdf",
            "Status": status,
        }
        ok, msg = append_row("manual_bills", row)
        if ok:
            pdf = generate_manual_bill_pdf(row)
            st.success("Manual bill saved")
            with open(pdf, "rb") as f:
                st.download_button("Download Manual Bill PDF", f, file_name=pdf.name, mime="application/pdf", use_container_width=True)
            st.rerun()
        else:
            st.error(msg)

# ============================================================
# Report pages
# ============================================================

def show_gate(page_key: str, label: str, loader_message: str) -> bool:
    if st.button(label, key=f"show_{page_key}", use_container_width=True):
        st.session_state[f"gate_{page_key}"] = True
    if not st.session_state.get(f"gate_{page_key}", False):
        st.info("Press SHOW button to load data.")
        return False
    hero_loader(loader_message, "Read Google Sheet → Display")
    return True

def page_dashboard():
    section("Dashboard", "SHOW button needed. Report user only.")
    if not require_role("REPORT"):
        return
    if not show_gate("dashboard", "🚀 SHOW DASHBOARD", "HERO Loading Dashboard"):
        return
    inv = read_sheet("invoices")
    att = read_sheet("attendance")
    cust = read_sheet("customers")
    tech = read_sheet("technicians")
    jobs = read_sheet("job_cards")
    total_revenue = money(inv["Total Amount"].astype(str).map(money).sum()) if (not inv.empty and "Total Amount" in inv.columns) else 0.0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Invoices", len(inv))
    c2.metric("Revenue", fmt_money(total_revenue))
    c3.metric("Customers", len(cust))
    c4.metric("Technicians", len(tech))
    c5, c6, c7 = st.columns(3)
    c5.metric("Attendance Rows", len(att))
    c6.metric("Job Cards", len(jobs))
    c7.metric("Report Mode", "Read Only")
    st.divider()
    st.subheader("Recent Invoices")
    if not inv.empty:
        st.dataframe(inv.tail(10), use_container_width=True, hide_index=True)

def page_search():
    section("Search", "Search invoices, job cards, customers.")
    if not require_role("REPORT"):
        return
    if not show_gate("search", "🔍 SHOW SEARCH", "HERO Loading Search"):
        return
    invoices = read_sheet("invoices")
    jobs = read_sheet("job_cards")
    customers = read_sheet("customers")
    q = st.text_input("Search keyword", placeholder="Invoice No / Job Card / Registration / Name")
    if q:
        patt = normalize(q)
        def filter_df(df):
            if df.empty:
                return df
            mask = pd.Series(False, index=df.index)
            for col in df.columns:
                mask = mask | df[col].astype(str).str.lower().str.contains(re.escape(patt), na=False)
            return df[mask]
        res_inv = filter_df(invoices)
        res_job = filter_df(jobs)
        res_cust = filter_df(customers)
        st.write("Invoices")
        st.dataframe(res_inv, use_container_width=True, hide_index=True)
        st.write("Job Cards")
        st.dataframe(res_job, use_container_width=True, hide_index=True)
        st.write("Customers")
        st.dataframe(res_cust, use_container_width=True, hide_index=True)

def page_customer_history():
    section("Customer History", "Read-only customer and invoice history.")
    if not require_role("REPORT"):
        return
    if not show_gate("history", "📖 SHOW HISTORY", "HERO Loading History"):
        return
    customers = read_sheet("customers")
    invoices = read_sheet("invoices")
    names = ["All"] + sorted({safe_text(x) for x in customers.get("Customer Name", pd.Series(dtype=str)).tolist() if safe_text(x)})
    selected = st.selectbox("Customer", names)
    if selected != "All":
        customers = customers[customers["Customer Name"].astype(str) == selected] if not customers.empty and "Customer Name" in customers.columns else customers
        invoices = invoices[invoices["Customer Name"].astype(str) == selected] if not invoices.empty and "Customer Name" in invoices.columns else invoices
    st.subheader("Customer Records")
    st.dataframe(customers, use_container_width=True, hide_index=True)
    st.subheader("Invoice History")
    st.dataframe(invoices, use_container_width=True, hide_index=True)

def page_attendance_report():
    section("Attendance Report", "Read-only attendance report with PDF export.")
    if not require_role("REPORT"):
        return
    if not show_gate("att_report", "📅 SHOW ATTENDANCE REPORT", "HERO Loading Attendance Report"):
        return
    att = read_sheet("attendance")
    c1, c2, c3 = st.columns(3)
    with c1:
        start_date = st.text_input("Start Date (DD-MM-YYYY)", value=today_str())
    with c2:
        end_date = st.text_input("End Date (DD-MM-YYYY)", value=today_str())
    with c3:
        status = st.selectbox("Attendance Status", ["All", "Present", "Absent", "Leave"])
    if not att.empty and "Date" in att.columns:
        df = att.copy()
        if start_date:
            df = df[df["Date"].astype(str) >= start_date]
        if end_date:
            df = df[df["Date"].astype(str) <= end_date]
        if status != "All":
            df = df[df["Attendance Status"].astype(str) == status]
    else:
        df = att
    st.dataframe(df, use_container_width=True, hide_index=True)
    if st.button("Generate Attendance PDF", use_container_width=True):
        pdf = generate_report_pdf(df, "Attendance Report", f"attendance_report_{safe_filename(stamp_str())}.pdf", SHEET_COLUMNS["attendance"])
        with open(pdf, "rb") as f:
            st.download_button("Download Attendance PDF", f, file_name=pdf.name, mime="application/pdf", use_container_width=True)

def page_technician_report():
    section("Technician Report", "Attendance + jobs + revenue + service count.")
    if not require_role("REPORT"):
        return
    if not show_gate("tech_report", "👨‍🔧 SHOW TECHNICIAN REPORT", "HERO Loading Technician Report"):
        return
    techs = technician_names()
    tech_name = st.selectbox("Select Technician", techs)
    invoices = read_sheet("invoices")
    att = read_sheet("attendance")
    jobs = read_sheet("job_cards")
    inv_t = invoices[invoices["Technician Name"].astype(str) == tech_name] if not invoices.empty and "Technician Name" in invoices.columns else invoices
    att_t = att[att["Technician Name"].astype(str) == tech_name] if not att.empty and "Technician Name" in att.columns else att
    job_t = jobs[jobs["Technician Name"].astype(str) == tech_name] if not jobs.empty and "Technician Name" in jobs.columns else jobs
    revenue = inv_t["Total Amount"].astype(str).map(money).sum() if not inv_t.empty and "Total Amount" in inv_t.columns else 0.0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Attendance", len(att_t))
    c2.metric("Jobs", len(job_t))
    c3.metric("Revenue", fmt_money(revenue))
    c4.metric("Service Count", len(inv_t))
    st.subheader("Invoices")
    st.dataframe(inv_t, use_container_width=True, hide_index=True)
    st.subheader("Attendance")
    st.dataframe(att_t, use_container_width=True, hide_index=True)
    st.subheader("Job Cards")
    st.dataframe(job_t, use_container_width=True, hide_index=True)
    if st.button("Generate Technician PDF", use_container_width=True):
        merged = pd.DataFrame({
            "Technician": [tech_name],
            "Attendance Rows": [len(att_t)],
            "Jobs": [len(job_t)],
            "Service Count": [len(inv_t)],
            "Revenue": [fmt_money(revenue)],
        })
        pdf = generate_report_pdf(merged, f"Technician Report - {tech_name}", f"technician_report_{safe_filename(tech_name)}.pdf", list(merged.columns))
        with open(pdf, "rb") as f:
            st.download_button("Download Technician PDF", f, file_name=pdf.name, mime="application/pdf", use_container_width=True)

def page_revenue_report():
    section("Revenue Report", "Read-only revenue analytics.")
    if not require_role("REPORT"):
        return
    if not show_gate("revenue", "📋 SHOW REPORTS", "HERO Loading Revenue Report"):
        return
    inv = read_sheet("invoices")
    if inv.empty:
        st.info("No invoice data found.")
        return
    df = inv.copy()
    df["Total Amount"] = df["Total Amount"].map(money)
    by_tech = df.groupby("Technician Name", dropna=False)["Total Amount"].sum().reset_index().sort_values("Total Amount", ascending=False)
    by_service = df.groupby("Service Type", dropna=False)["Total Amount"].sum().reset_index().sort_values("Total Amount", ascending=False)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("By Technician")
        st.dataframe(by_tech, use_container_width=True, hide_index=True)
    with c2:
        st.subheader("By Service Type")
        st.dataframe(by_service, use_container_width=True, hide_index=True)
    pdf = generate_report_pdf(by_tech, "Revenue Report", f"revenue_report_{safe_filename(stamp_str())}.pdf", list(by_tech.columns))
    with open(pdf, "rb") as f:
        st.download_button("Download Revenue PDF", f, file_name=pdf.name, mime="application/pdf", use_container_width=True)

def page_reports():
    section("Reports", "Read-only reports after SHOW button click.")
    if not require_role("REPORT"):
        return
    if not show_gate("reports", "📋 SHOW REPORTS", "HERO Loading Reports"):
        return
    inv = read_sheet("invoices")
    st.subheader("Service / Invoice Report")
    st.dataframe(inv, use_container_width=True, hide_index=True)
    if st.button("Generate Service PDF", use_container_width=True):
        pdf = generate_report_pdf(inv, "Service Report", f"service_report_{safe_filename(stamp_str())}.pdf", SHEET_COLUMNS["invoices"])
        with open(pdf, "rb") as f:
            st.download_button("Download Service PDF", f, file_name=pdf.name, mime="application/pdf", use_container_width=True)

# ============================================================
# Navigation
# ============================================================

def entry_navigation():
    st.sidebar.markdown("### ENTRY MODE")
    st.sidebar.success("Data Entry Only")
    if st.sidebar.button("Logout", use_container_width=True):
        logout()
    pages = [
        "Invoice Entry",
        "OCR Invoice Upload",
        "Manual Bill Entry",
        "Attendance Entry",
        "Job Card Entry",
        "Customer Entry",
        "Technician Master",
    ]
    current = st.session_state.get("current_page", pages[0])
    st.session_state["current_page"] = current
    cols = st.columns(2)
    for idx, page in enumerate(pages):
        with cols[idx % 2]:
            if st.button(page, key=f"nav_{page}", use_container_width=True):
                st.session_state["current_page"] = page
                st.rerun()
    st.divider()
    page = st.session_state.get("current_page", "Invoice Entry")
    if page == "Invoice Entry":
        page_invoice_entry()
    elif page == "OCR Invoice Upload":
        page_ocr_upload()
    elif page == "Manual Bill Entry":
        page_manual_bill()
    elif page == "Attendance Entry":
        page_attendance_entry()
    elif page == "Job Card Entry":
        page_job_card_entry()
    elif page == "Customer Entry":
        page_customer_entry()
    elif page == "Technician Master":
        page_technician_master()

def report_navigation():
    st.sidebar.markdown("### REPORT MODE")
    st.sidebar.info("Read Only / Reports")
    if st.sidebar.button("Logout", use_container_width=True):
        logout()
    pages = [
        ("Dashboard", "dashboard"),
        ("Search", "search"),
        ("Reports", "reports"),
        ("History", "history"),
        ("Attendance Report", "att_report"),
        ("Technician Report", "tech_report"),
        ("Revenue Report", "revenue"),
    ]
    current = st.session_state.get("current_page", "Dashboard")
    st.session_state["current_page"] = current
    cols = st.columns(2)
    for idx, (label, key) in enumerate(pages):
        with cols[idx % 2]:
            if st.button(label, key=f"nav_{key}", use_container_width=True):
                st.session_state["current_page"] = label
                st.rerun()
    st.divider()
    page = st.session_state.get("current_page", "Dashboard")
    if page == "Dashboard":
        page_dashboard()
    elif page == "Search":
        page_search()
    elif page == "Reports":
        page_reports()
    elif page == "History":
        page_customer_history()
    elif page == "Attendance Report":
        page_attendance_report()
    elif page == "Technician Report":
        page_technician_report()
    elif page == "Revenue Report":
        page_revenue_report()

# ============================================================
# Main
# ============================================================

def inject_styles():
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 1420px; }
        [data-testid="stSidebar"] { background: linear-gradient(180deg,#0f172a,#111827 58%,#052e16); }
        [data-testid="stSidebar"] * { color: #e5e7eb; }
        button[kind="primary"] { border-radius: 14px !important; }
        .stButton button { border-radius: 14px !important; font-weight: 700; }
        </style>
        """,
        unsafe_allow_html=True,
    )

def main():
    inject_styles()
    bootstrap_default_technicians()

    if not is_logged_in():
        login_panel()
        return

    st.sidebar.markdown(f"### Logged in as `{st.session_state.get('user_id','')}`")
    st.sidebar.markdown(f"**Role:** {role()}")
    if role() == "ENTRY":
        entry_navigation()
    elif role() == "REPORT":
        report_navigation()
    else:
        st.error("Unknown role")
        logout()

if __name__ == "__main__":
    main()
