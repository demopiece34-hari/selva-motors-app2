
import re
import io
import uuid
import math
import zipfile
import time as time_module
import json
import base64
from pathlib import Path
from datetime import datetime, time
from zoneinfo import ZoneInfo

import streamlit as st
import pandas as pd

try:
    import gspread
    from google.oauth2.service_account import Credentials
except Exception:
    gspread = None
    Credentials = None
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
SYNC_STATE_FILE = DATA_DIR / "google_sync_state.json"
HERO_LOGO_PATH = Path("assets") / "hero_logo.jpg"
EMBEDDED_HERO_LOGO_B64 = ""

COMPANY_LAT = 10.759701
COMPANY_LON = 79.742837
ALLOWED_RADIUS_METER = 100

APP_TZ = ZoneInfo("Asia/Kolkata")


def app_now():
    """Return current India time. Streamlit Cloud UTC issue fix."""
    return datetime.now(APP_TZ)


# ============================================================
# STYLE
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap');

:root {
    --hero-dark: #070b13;
    --hero-navy: #0f172a;
    --hero-green: #22c55e;
    --hero-blue: #2563eb;
    --hero-red: #ef4444;
    --hero-gold: #f59e0b;
    --hero-card: rgba(255,255,255,.88);
    --hero-border: rgba(226,232,240,.85);
}

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background:
        radial-gradient(circle at 3% 0%, rgba(34,197,94,.18), transparent 26%),
        radial-gradient(circle at 98% 3%, rgba(37,99,235,.16), transparent 28%),
        radial-gradient(circle at 70% 100%, rgba(245,158,11,.12), transparent 30%),
        linear-gradient(135deg, #f8fafc 0%, #eef2ff 48%, #f0fdf4 100%);
}

.block-container {
    padding-top: 1.05rem;
    padding-bottom: 2rem;
    max-width: 1420px;
}

[data-testid="stSidebar"] {
    background:
        linear-gradient(180deg, rgba(2,6,23,.98), rgba(15,23,42,.99) 58%, rgba(5,46,22,.98)),
        radial-gradient(circle at 50% 0%, rgba(34,197,94,.22), transparent 36%);
    border-right: 1px solid rgba(255,255,255,.08);
}

[data-testid="stSidebar"] * {
    color: #e5e7eb;
}

[data-testid="stSidebar"] .stRadio label {
    background: rgba(255,255,255,.04);
    border: 1px solid rgba(255,255,255,.07);
    border-radius: 15px;
    margin: 6px 0;
    padding: 7px 8px;
    transition: all .18s ease;
}

[data-testid="stSidebar"] .stRadio label:hover {
    background: rgba(34,197,94,.18);
    border-color: rgba(34,197,94,.38);
    transform: translateX(3px);
}

[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
textarea {
    border-radius: 14px !important;
    border: 1px solid #cbd5e1 !important;
}

.app-title {
    font-size: 34px;
    font-weight: 900;
    letter-spacing: -.8px;
    color: #0f172a;
    margin-bottom: 2px;
}

.subtle {
    color: #64748b;
    font-size: 14px;
    margin-bottom: 12px;
}

.login-wrap {
    min-height: 77vh;
    display:flex;
    align-items:center;
    justify-content:center;
}

.login-hero {
    max-width: 620px;
    width: 100%;
    padding: 36px;
    border-radius: 32px;
    background:
        linear-gradient(145deg, rgba(255,255,255,.94), rgba(255,255,255,.78)),
        radial-gradient(circle at 0% 0%, rgba(34,197,94,.24), transparent 40%);
    box-shadow: 0 30px 80px rgba(15,23,42,.22);
    border: 1px solid rgba(255,255,255,.8);
    backdrop-filter: blur(18px);
    position: relative;
    overflow: hidden;
}

.login-hero:before {
    content:"";
    position:absolute;
    width:210px;
    height:210px;
    border-radius:50%;
    background:rgba(34,197,94,.16);
    right:-70px;
    top:-80px;
}

.brand-row {
    display:flex;
    align-items:center;
    gap:12px;
    margin-bottom: 12px;
}

.brand-logo {
    height:58px;
    width:58px;
    border-radius:20px;
    display:grid;
    place-items:center;
    background: linear-gradient(135deg, #111827, #16a34a);
    color:white;
    font-size:28px;
    box-shadow:0 16px 30px rgba(22,163,74,.28);
}

.brand-text h1 {
    margin:0;
    font-size:31px;
    font-weight:900;
    letter-spacing:-.7px;
    color:#0f172a;
}

.brand-text p {
    margin:0;
    color:#16a34a;
    font-weight:900;
    letter-spacing:3px;
    font-size:12px;
}

.feature-strip {
    display:flex;
    flex-wrap:wrap;
    gap:8px;
    margin: 14px 0 4px 0;
}

.feature-pill {
    padding: 7px 10px;
    border-radius: 999px;
    background:#ecfdf5;
    color:#166534;
    border:1px solid #bbf7d0;
    font-weight:800;
    font-size:12px;
}

.hero-panel {
    position:relative;
    overflow:hidden;
    padding: 24px;
    border-radius: 28px;
    background:
        radial-gradient(circle at 100% 0%, rgba(34,197,94,.28), transparent 34%),
        linear-gradient(135deg, #020617 0%, #0f172a 58%, #052e16 130%);
    color: white;
    box-shadow: 0 22px 54px rgba(2,6,23,.22);
    border: 1px solid rgba(255,255,255,.10);
    margin-bottom: 20px;
}

.hero-panel:after {
    content:"🏍️";
    position:absolute;
    right:24px;
    bottom:12px;
    font-size:74px;
    opacity:.10;
}

.hero-panel h1 {
    margin: 0;
    font-size: 31px;
    font-weight: 900;
    letter-spacing: -.7px;
}

.hero-panel p {
    margin: 7px 0 0 0;
    color: #cbd5e1;
}

.status-chip {
    display: inline-flex;
    align-items:center;
    gap:6px;
    padding: 6px 11px;
    border-radius: 999px;
    font-weight: 900;
    font-size: 12px;
    background: rgba(34,197,94,.16);
    color: #bbf7d0;
    border: 1px solid rgba(187,247,208,.25);
    margin-bottom: 10px;
}

.glow-card {
    background: rgba(255,255,255,.92);
    border: 1px solid var(--hero-border);
    border-radius: 24px;
    padding: 20px;
    box-shadow: 0 17px 42px rgba(15,23,42,.09);
    transition: transform .16s ease, box-shadow .16s ease;
}

.glow-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 24px 58px rgba(15,23,42,.13);
}

.metric-card {
    position: relative;
    overflow: hidden;
    min-height: 132px;
    border-radius: 26px;
    padding: 21px;
    color: white;
    background:
        radial-gradient(circle at 100% 0%, rgba(255,255,255,.18), transparent 30%),
        linear-gradient(135deg, #111827 0%, #1e293b 58%, #16a34a 145%);
    box-shadow: 0 20px 50px rgba(15,23,42,.20);
    border: 1px solid rgba(255,255,255,.13);
}

.metric-card:before {
    content: "";
    position: absolute;
    width: 135px;
    height: 135px;
    right: -46px;
    top: -48px;
    background: rgba(255,255,255,.12);
    border-radius: 999px;
}

.metric-card p {
    margin: 0;
    color: #dbeafe;
    font-size: 13px;
    font-weight: 800;
}

.metric-card h2 {
    margin: 8px 0 0 0;
    font-size: 31px;
    font-weight: 900;
    letter-spacing: -.6px;
}

.metric-card small {
    color: #bbf7d0;
    font-weight: 800;
}

.quick-card {
    padding:18px;
    border-radius:22px;
    background: linear-gradient(135deg, rgba(255,255,255,.95), rgba(240,253,244,.92));
    border:1px solid rgba(187,247,208,.7);
    box-shadow:0 14px 34px rgba(15,23,42,.08);
}

.quick-card h3 {
    margin:0;
    font-size:17px;
    color:#0f172a;
    font-weight:900;
}

.quick-card p {
    color:#64748b;
    margin:6px 0 0 0;
    font-size:13px;
}

.section-title {
    font-size: 20px;
    font-weight: 900;
    color: #0f172a;
    margin: 10px 0 11px 0;
    letter-spacing:-.2px;
}

.bill-preview {
    border-radius:26px;
    background:#fff;
    border:1px solid #e2e8f0;
    padding:22px;
    box-shadow:0 18px 44px rgba(15,23,42,.10);
    position:relative;
    overflow:hidden;
}

.bill-preview:before {
    content:"";
    height:7px;
    background:linear-gradient(90deg,#111827,#16a34a,#ef4444);
    position:absolute;
    top:0;
    left:0;
    right:0;
}

.bill-preview h2 {
    margin:8px 0 3px 0;
    font-weight:900;
    color:#0f172a;
}

.preview-grid {
    display:grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap:12px;
}

.preview-item {
    padding:13px;
    border-radius:17px;
    background:#f8fafc;
    border:1px solid #e2e8f0;
}

.preview-item b {
    display:block;
    color:#64748b;
    font-size:12px;
}

.preview-item span {
    display:block;
    color:#0f172a;
    font-weight:900;
    margin-top:4px;
}

.approve-box {
    border-radius:20px;
    background:#fff;
    padding:16px;
    border:1px solid #fee2e2;
    box-shadow:0 12px 28px rgba(239,68,68,.08);
    margin-bottom:12px;
}

.stButton>button {
    border-radius: 15px !important;
    font-weight: 900 !important;
    border: 0 !important;
    background: linear-gradient(135deg, #16a34a, #2563eb) !important;
    color: white !important;
    box-shadow: 0 12px 28px rgba(37,99,235,.19);
}

.stDownloadButton>button {
    border-radius: 15px !important;
    font-weight: 900 !important;
    border: 0 !important;
    background: linear-gradient(135deg, #0f172a, #16a34a) !important;
    color: white !important;
}

[data-testid="stDataFrame"] {
    border-radius: 20px;
    overflow: hidden;
    box-shadow: 0 11px 30px rgba(15,23,42,.08);
}

[data-testid="stMetric"] {
    background: rgba(255,255,255,.88);
    padding:16px;
    border-radius:18px;
    border:1px solid #e2e8f0;
    box-shadow:0 10px 28px rgba(15,23,42,.07);
}

hr {
    border: none;
    height: 1px;
    background: linear-gradient(90deg, transparent, #cbd5e1, transparent);
    margin: 24px 0;
}

@media (max-width: 768px) {
    .preview-grid { grid-template-columns: repeat(1, minmax(0, 1fr)); }
    .hero-panel h1 { font-size: 24px; }
    .metric-card h2 { font-size: 25px; }
}

.approve-box h3 {
    letter-spacing: -.3px;
}
.glow-card, .bill-preview, .approve-box {
    animation: softFadeIn .25s ease-in-out;
}
@keyframes softFadeIn {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: translateY(0); }
}


/* ===== SELVA MOTORS ULTRA DESIGN PATCH ===== */
.ultra-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 14px;
    margin-bottom: 18px;
}
.ultra-card {
    background: rgba(255,255,255,.94);
    border: 1px solid rgba(226,232,240,.95);
    border-radius: 24px;
    padding: 18px;
    box-shadow: 0 18px 42px rgba(15,23,42,.09);
    position: relative;
    overflow: hidden;
}
.ultra-card:before {
    content: "";
    position: absolute;
    width: 92px;
    height: 92px;
    right: -28px;
    top: -28px;
    background: rgba(34,197,94,.12);
    border-radius: 999px;
}
.ultra-card .label {
    color: #64748b;
    font-size: 12px;
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: .5px;
}
.ultra-card .value {
    color: #0f172a;
    font-size: 25px;
    font-weight: 900;
    margin-top: 6px;
}
.ultra-card .note {
    color: #16a34a;
    font-size: 12px;
    font-weight: 800;
    margin-top: 4px;
}
.ultra-status {
    padding: 14px;
    border-radius: 22px;
    background: linear-gradient(135deg, #0f172a, #052e16);
    color: white;
    box-shadow: 0 18px 40px rgba(15,23,42,.18);
    margin-bottom: 16px;
}
.ultra-status h3 {
    margin: 0;
    font-weight: 900;
    font-size: 18px;
}
.ultra-status p {
    margin: 6px 0 0 0;
    color: #cbd5e1;
    font-size: 13px;
}
.badge-green, .badge-red, .badge-yellow, .badge-blue {
    display: inline-block;
    padding: 6px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 900;
}
.badge-green { background:#dcfce7; color:#166534; }
.badge-red { background:#fee2e2; color:#991b1b; }
.badge-yellow { background:#fef3c7; color:#92400e; }
.badge-blue { background:#dbeafe; color:#1e40af; }
.invoice-preview-pro {
    border-radius: 28px;
    background: #ffffff;
    border: 1px solid #e2e8f0;
    box-shadow: 0 22px 55px rgba(15,23,42,.11);
    overflow: hidden;
    margin-bottom: 18px;
}
.invoice-preview-head {
    background: linear-gradient(135deg, #111827, #16a34a);
    color: #ffffff;
    padding: 18px 22px;
}
.invoice-preview-head h2 {
    margin: 0;
    font-size: 22px;
    font-weight: 900;
}
.invoice-preview-head p {
    margin: 5px 0 0 0;
    color: #dcfce7;
}
.invoice-preview-body {
    padding: 18px;
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
}
.invoice-field {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 18px;
    padding: 13px;
}
.invoice-field b {
    display: block;
    color: #64748b;
    font-size: 12px;
    text-transform: uppercase;
}
.invoice-field span {
    display: block;
    margin-top: 5px;
    color: #0f172a;
    font-size: 16px;
    font-weight: 900;
}
.approval-card {
    border-radius: 24px;
    background: #fff;
    border: 1px solid #e5e7eb;
    box-shadow: 0 16px 36px rgba(15,23,42,.08);
    padding: 18px;
    margin-bottom: 14px;
}
.approval-card h3 {
    margin: 0 0 6px 0;
    color: #111827;
    font-size: 18px;
    font-weight: 900;
}
.approval-card p {
    color: #475569;
    margin: 4px 0;
}
.admin-tab-note {
    background: #f8fafc;
    border-left: 5px solid #22c55e;
    padding: 12px 14px;
    border-radius: 14px;
    margin: 10px 0 16px 0;
    color: #334155;
    font-weight: 700;
}
@media (max-width: 900px) {
    .ultra-grid { grid-template-columns: repeat(1, minmax(0, 1fr)); }
    .invoice-preview-body { grid-template-columns: repeat(1, minmax(0, 1fr)); }
}


.cloud-excel-head {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
    background: linear-gradient(135deg, #f8fafc, #ecfdf5);
    border: 1px solid #bbf7d0;
    border-radius: 18px;
    padding: 14px;
    margin: 10px 0 16px 0;
    color: #0f172a;
    box-shadow: 0 10px 25px rgba(15,23,42,.06);
}
.cloud-excel-head div {
    background: white;
    border-radius: 14px;
    padding: 10px;
    border: 1px solid #e2e8f0;
}
[data-testid="stTabs"] button {
    font-weight: 900;
}
@media (max-width: 900px) {
    .cloud-excel-head {
        grid-template-columns: repeat(1, minmax(0, 1fr));
    }
}


/* ===== SELVA MOTORS PREMIUM DESIGN V2 ===== */
.stApp {
    background:
        radial-gradient(circle at 2% 2%, rgba(34,197,94,.17), transparent 28%),
        radial-gradient(circle at 98% 0%, rgba(239,68,68,.10), transparent 25%),
        linear-gradient(135deg, #f8fafc 0%, #eef2ff 45%, #f0fdf4 100%);
}
.block-container {
    padding-top: 1rem;
    max-width: 1450px;
}
[data-testid="stSidebar"] {
    background:
        radial-gradient(circle at 50% 0%, rgba(34,197,94,.20), transparent 35%),
        linear-gradient(180deg, #020617, #0f172a 60%, #052e16);
    border-right: 1px solid rgba(255,255,255,.08);
}
[data-testid="stSidebar"] * {
    color: #e5e7eb;
}
[data-testid="stSidebar"] .stRadio label {
    border-radius: 16px;
    margin: 6px 0;
    padding: 8px;
    background: rgba(255,255,255,.045);
    border: 1px solid rgba(255,255,255,.08);
}
[data-testid="stSidebar"] .stRadio label:hover {
    background: rgba(34,197,94,.18);
    border-color: rgba(34,197,94,.42);
}
.hero-panel {
    border-radius: 30px !important;
    box-shadow: 0 24px 60px rgba(15,23,42,.22) !important;
}
.premium-title-card {
    padding: 20px;
    border-radius: 26px;
    background: linear-gradient(135deg, #111827, #052e16);
    color: white;
    box-shadow: 0 20px 45px rgba(15,23,42,.20);
    margin-bottom: 18px;
}
.premium-title-card h2 {
    margin: 0;
    font-size: 24px;
    font-weight: 900;
}
.premium-title-card p {
    margin: 7px 0 0 0;
    color: #cbd5e1;
    font-size: 13px;
}
.erp-card-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 14px;
    margin: 15px 0 20px 0;
}
.erp-card {
    background: rgba(255,255,255,.95);
    border: 1px solid rgba(226,232,240,.95);
    border-radius: 24px;
    padding: 18px;
    box-shadow: 0 16px 38px rgba(15,23,42,.08);
    position: relative;
    overflow: hidden;
}
.erp-card:after {
    content: "";
    position: absolute;
    height: 90px;
    width: 90px;
    right: -34px;
    top: -34px;
    border-radius: 999px;
    background: rgba(34,197,94,.13);
}
.erp-card small {
    color: #64748b;
    font-size: 12px;
    font-weight: 900;
    text-transform: uppercase;
}
.erp-card h3 {
    color: #0f172a;
    font-size: 25px;
    font-weight: 900;
    margin: 7px 0 0 0;
}
.erp-card span {
    color: #16a34a;
    font-size: 12px;
    font-weight: 800;
}
.professional-panel {
    background: rgba(255,255,255,.94);
    border: 1px solid #e2e8f0;
    border-radius: 24px;
    padding: 18px;
    box-shadow: 0 14px 34px rgba(15,23,42,.08);
    margin: 12px 0 18px 0;
}
.professional-panel h3 {
    margin: 0 0 8px 0;
    font-size: 18px;
    font-weight: 900;
    color: #0f172a;
}
.status-row {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin: 10px 0;
}
.status-pill {
    padding: 7px 11px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 900;
}
.status-ok { background:#dcfce7; color:#166534; }
.status-warn { background:#fef3c7; color:#92400e; }
.status-danger { background:#fee2e2; color:#991b1b; }
.status-info { background:#dbeafe; color:#1e40af; }
.cloud-excel-head {
    background: linear-gradient(135deg, #ffffff, #ecfdf5) !important;
    border: 1px solid #bbf7d0 !important;
    box-shadow: 0 18px 44px rgba(15,23,42,.09) !important;
}
.stButton > button {
    border-radius: 15px !important;
    font-weight: 900 !important;
    min-height: 42px;
}
.stDownloadButton > button {
    border-radius: 15px !important;
    font-weight: 900 !important;
}
[data-testid="stDataFrame"] {
    border-radius: 20px;
    overflow: hidden;
    box-shadow: 0 12px 32px rgba(15,23,42,.08);
}
[data-testid="stTabs"] button {
    font-weight: 900 !important;
    border-radius: 12px 12px 0 0 !important;
}
@media (max-width: 900px) {
    .erp-card-grid { grid-template-columns: repeat(1, minmax(0, 1fr)); }
}


/* ===== SELVA MOTORS PRO ERP UI V3 ===== */
.pro-alert-bar {
    display:grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap:12px;
    margin: 10px 0 18px 0;
}
.pro-alert {
    padding:14px;
    border-radius:20px;
    background: rgba(255,255,255,.95);
    border: 1px solid #e2e8f0;
    box-shadow: 0 14px 34px rgba(15,23,42,.08);
}
.pro-alert b { color:#0f172a; display:block; font-size:15px; }
.pro-alert span { color:#64748b; font-size:12px; font-weight:800; }
.quick-action-grid {
    display:grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap:14px;
    margin:16px 0;
}
.quick-action {
    background: linear-gradient(135deg, #ffffff, #f0fdf4);
    border: 1px solid #bbf7d0;
    border-radius: 24px;
    padding: 18px;
    box-shadow: 0 16px 38px rgba(15,23,42,.08);
}
.quick-action h3 {
    margin:0;
    font-size:18px;
    font-weight:900;
    color:#0f172a;
}
.quick-action p {
    margin:7px 0 0 0;
    color:#64748b;
    font-size:13px;
    font-weight:700;
}
.stepper {
    display:flex;
    gap:8px;
    flex-wrap:wrap;
    margin: 12px 0 18px 0;
}
.step {
    padding:9px 12px;
    border-radius:999px;
    background:#e2e8f0;
    color:#334155;
    font-size:12px;
    font-weight:900;
}
.step.active { background:#dcfce7; color:#166534; }
.step.warn { background:#fef3c7; color:#92400e; }
.timeline {
    display:flex;
    gap:8px;
    flex-wrap:wrap;
    margin: 10px 0;
}
.timeline span {
    padding:8px 11px;
    border-radius:999px;
    background:#dbeafe;
    color:#1e40af;
    font-size:12px;
    font-weight:900;
}
.theme-note {
    padding: 14px;
    border-radius: 20px;
    background: linear-gradient(135deg, #020617, #052e16);
    color: white;
    margin-bottom: 14px;
    box-shadow: 0 16px 36px rgba(15,23,42,.18);
}
.print-card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 24px;
    padding: 16px;
    box-shadow: 0 14px 32px rgba(15,23,42,.08);
    margin: 12px 0;
}
@media (max-width: 900px) {
    .pro-alert-bar, .quick-action-grid {
        grid-template-columns: repeat(1, minmax(0, 1fr));
    }
}


.gps-refresh-card {
    background: rgba(255,255,255,.96);
    border: 1px solid #dbeafe;
    border-radius: 18px;
    padding: 14px;
    box-shadow: 0 10px 24px rgba(15,23,42,.08);
    animation: gpsPulse 1.4s infinite;
    margin: 12px 0;
}
@keyframes gpsPulse {
    0% { transform: scale(1); box-shadow: 0 10px 24px rgba(15,23,42,.08); }
    50% { transform: scale(1.01); box-shadow: 0 16px 34px rgba(37,99,235,.15); }
    100% { transform: scale(1); box-shadow: 0 10px 24px rgba(15,23,42,.08); }
}


.service-type-panel {
    background: rgba(255,255,255,.94);
    border: 1px solid #bbf7d0;
    border-radius: 18px;
    padding: 14px;
    margin: 10px 0 14px 0;
    box-shadow: 0 12px 28px rgba(15,23,42,.07);
}
.service-type-panel b {
    color: #0f172a;
}


/* ============================================================
   HERO PROFESSIONAL PORTAL DESIGN PATCH - DESIGN ONLY
   Red / Black / White premium showroom style
   ============================================================ */
:root {
    --hero-red-main: #e31837;
    --hero-red-dark: #b00020;
    --hero-black: #070707;
    --hero-charcoal: #111827;
    --hero-soft: #fff5f5;
    --hero-border-red: rgba(227,24,55,.22);
}
.stApp {
    background:
        radial-gradient(circle at 6% 2%, rgba(227,24,55,.16), transparent 26%),
        radial-gradient(circle at 95% 4%, rgba(0,0,0,.13), transparent 25%),
        linear-gradient(135deg, #fff7f7 0%, #ffffff 45%, #f8fafc 100%) !important;
}
.block-container {
    padding-top: 1rem !important;
    max-width: 1480px !important;
}
[data-testid="stSidebar"] {
    background:
        radial-gradient(circle at 50% 0%, rgba(227,24,55,.30), transparent 35%),
        linear-gradient(180deg, #050505 0%, #111111 52%, #3a0009 130%) !important;
    border-right: 1px solid rgba(227,24,55,.22) !important;
    box-shadow: 18px 0 45px rgba(0,0,0,.10);
}
[data-testid="stSidebar"] * {
    color: #ffffff !important;
}
[data-testid="stSidebar"] .stRadio label {
    background: rgba(255,255,255,.055) !important;
    border: 1px solid rgba(255,255,255,.10) !important;
    border-radius: 16px !important;
    margin: 7px 0 !important;
    padding: 9px 9px !important;
    transition: all .18s ease !important;
}
[data-testid="stSidebar"] .stRadio label:hover {
    background: rgba(227,24,55,.25) !important;
    border-color: rgba(227,24,55,.56) !important;
    transform: translateX(4px);
    box-shadow: 0 12px 26px rgba(227,24,55,.13);
}
.hero-panel {
    background:
        radial-gradient(circle at 96% 2%, rgba(227,24,55,.36), transparent 35%),
        linear-gradient(135deg, #050505 0%, #111827 55%, #7f0016 145%) !important;
    color: #fff !important;
    border-radius: 32px !important;
    border: 1px solid rgba(227,24,55,.26) !important;
    box-shadow: 0 26px 70px rgba(17,24,39,.22), 0 0 0 1px rgba(255,255,255,.05) inset !important;
}
.hero-panel h1 {
    font-size: 33px !important;
    letter-spacing: -1px !important;
}
.status-chip {
    background: rgba(227,24,55,.18) !important;
    color: #fecdd3 !important;
    border: 1px solid rgba(248,113,113,.28) !important;
}
.login-wrap {
    min-height: 78vh !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}
.login-hero {
    max-width: 560px !important;
    padding: 34px !important;
    border-radius: 34px !important;
    background:
        radial-gradient(circle at 0% 0%, rgba(227,24,55,.20), transparent 42%),
        linear-gradient(145deg, rgba(255,255,255,.98), rgba(255,245,245,.92)) !important;
    border: 1px solid rgba(227,24,55,.18) !important;
    box-shadow: 0 34px 95px rgba(17,24,39,.22), 0 0 70px rgba(227,24,55,.12) !important;
    backdrop-filter: blur(18px);
}
.login-hero:before {
    background: rgba(227,24,55,.14) !important;
}
.feature-pill {
    background: #fff1f2 !important;
    color: #be123c !important;
    border: 1px solid #fecdd3 !important;
}
.metric-card {
    background:
        radial-gradient(circle at 100% 0%, rgba(255,255,255,.18), transparent 30%),
        linear-gradient(135deg, #060606 0%, #111827 58%, #e31837 145%) !important;
    box-shadow: 0 20px 50px rgba(227,24,55,.15) !important;
    border: 1px solid rgba(227,24,55,.18) !important;
}
.glow-card, .quick-card, .bill-preview, .approval-card, .professional-panel,
.erp-card, .ultra-card, .cloud-excel-head {
    border: 1px solid rgba(227,24,55,.12) !important;
    box-shadow: 0 18px 45px rgba(17,24,39,.08), 0 0 36px rgba(227,24,55,.045) !important;
}
.quick-card {
    background: linear-gradient(135deg, #ffffff, #fff1f2) !important;
    border-color: rgba(227,24,55,.16) !important;
}
.stButton>button {
    background: linear-gradient(135deg, #e31837, #111827) !important;
    color: white !important;
    border-radius: 16px !important;
    font-weight: 900 !important;
    box-shadow: 0 14px 32px rgba(227,24,55,.20) !important;
    border: 1px solid rgba(255,255,255,.10) !important;
}
.stButton>button:hover {
    filter: brightness(1.06);
    transform: translateY(-1px);
}
.stDownloadButton>button {
    background: linear-gradient(135deg, #111827, #e31837) !important;
    color: white !important;
    border-radius: 16px !important;
    font-weight: 900 !important;
    box-shadow: 0 14px 32px rgba(227,24,55,.18) !important;
}
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
textarea,
.stSelectbox div[data-baseweb="select"] > div {
    border-radius: 16px !important;
    border: 1px solid rgba(227,24,55,.22) !important;
    box-shadow: 0 8px 22px rgba(17,24,39,.04) !important;
}
[data-testid="stMetric"] {
    background: rgba(255,255,255,.95) !important;
    border: 1px solid rgba(227,24,55,.13) !important;
    border-radius: 20px !important;
    box-shadow: 0 14px 32px rgba(17,24,39,.07) !important;
}
[data-testid="stDataFrame"] {
    border-radius: 22px !important;
    overflow: hidden !important;
    box-shadow: 0 16px 38px rgba(17,24,39,.09) !important;
    border: 1px solid rgba(227,24,55,.10) !important;
}
.invoice-preview-pro,
.bill-preview {
    border-top: 6px solid var(--hero-red-main) !important;
}
.invoice-preview-head {
    background: linear-gradient(135deg, #060606, #e31837) !important;
}
.admin-tab-note {
    border-left: 5px solid var(--hero-red-main) !important;
    background: #fff7f7 !important;
}
.hero-login-logo-img {
    max-width: 185px;
    width: 100%;
    display: block;
    margin: 0 auto 18px auto;
    filter: drop-shadow(0 14px 24px rgba(227,24,55,.20));
}
.hero-connect-title {
    font-size: 42px;
    line-height: 1;
    text-align: center;
    font-weight: 800;
    color: #2f3542;
    margin: 8px 0 22px 0;
    letter-spacing: -1px;
}
.hero-login-panel {
    background: rgba(255,255,255,.92);
    border: 1px solid rgba(227,24,55,.14);
    border-radius: 28px;
    padding: 28px;
    box-shadow: 0 22px 58px rgba(17,24,39,.13), 0 0 55px rgba(227,24,55,.08);
}
.hero-login-note {
    text-align: center;
    color: #6b7280;
    font-size: 12px;
    margin-top: 12px;
}
@media (max-width: 768px) {
    .hero-connect-title { font-size: 34px; }
    .login-hero { padding: 24px !important; border-radius: 28px !important; }
    .hero-panel h1 { font-size: 25px !important; }
}


/* ============================================================
   SELVA MOTORS OPTIMAL V4 PATCH
   Added: 1 Speed UI, 3 OCR UX, 4 PDF logo support, 5 Role UI,
   6 Mobile view, 7 Admin filters, 8 Sync status, 9 Duplicate UX, 10 Login UX
   ============================================================ */
.optimal-v4-note {
    background: linear-gradient(135deg, #fff, #fff1f2);
    border: 1px solid rgba(227,24,55,.16);
    border-radius: 18px;
    padding: 13px 15px;
    box-shadow: 0 12px 28px rgba(17,24,39,.06);
    margin: 10px 0 14px 0;
    color: #374151;
    font-size: 13px;
}
.optimal-v4-note b {
    color: #111827;
}
.mobile-action-card {
    background: #ffffff;
    border: 1px solid rgba(227,24,55,.14);
    border-radius: 20px;
    padding: 16px;
    box-shadow: 0 12px 30px rgba(17,24,39,.08);
    margin-bottom: 10px;
}
.mobile-action-card h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 900;
    color: #111827;
}
.mobile-action-card p {
    color: #6b7280;
    margin: 5px 0 0 0;
    font-size: 13px;
}
.sync-status-box {
    border-radius: 20px;
    padding: 14px;
    border: 1px solid rgba(37,99,235,.18);
    background: linear-gradient(135deg, #eff6ff, #fff);
    box-shadow: 0 12px 28px rgba(17,24,39,.06);
    margin: 10px 0 16px 0;
}
.duplicate-compare-box {
    border-radius: 20px;
    padding: 14px;
    border: 1px solid rgba(245,158,11,.25);
    background: linear-gradient(135deg, #fffbeb, #fff);
    box-shadow: 0 12px 28px rgba(17,24,39,.06);
    margin: 10px 0 16px 0;
}
@media (max-width: 768px) {
    .block-container {
        padding-left: .75rem !important;
        padding-right: .75rem !important;
    }
    .hero-panel {
        padding: 18px !important;
        border-radius: 24px !important;
    }
    .hero-panel h1 {
        font-size: 23px !important;
    }
    .metric-card, .glow-card, .quick-card, .bill-preview, .approval-card {
        border-radius: 18px !important;
        padding: 14px !important;
    }
    [data-testid="stHorizontalBlock"] {
        gap: .55rem !important;
    }
    .stButton>button, .stDownloadButton>button {
        width: 100% !important;
        min-height: 44px !important;
    }
    [data-testid="stDataFrame"] {
        font-size: 12px !important;
    }
}


/* ===== SELVA MOTORS EXTREME REPORT CENTER UI ===== */
.report-center-wrap {
    background: radial-gradient(circle at 0% 0%, rgba(227,24,55,.12), transparent 34%),
                linear-gradient(135deg, rgba(255,255,255,.96), rgba(255,241,242,.82));
    border: 1px solid rgba(227,24,55,.15);
    border-radius: 28px;
    padding: 18px;
    box-shadow: 0 20px 55px rgba(17,24,39,.10), 0 0 44px rgba(227,24,55,.05);
    margin-bottom: 18px;
}
.report-center-wrap h2 { margin:0; font-size:24px; font-weight:900; color:#111827; }
.report-center-wrap p { margin:7px 0 0 0; color:#64748b; font-size:13px; font-weight:700; }
.report-badge-row { display:flex; gap:8px; flex-wrap:wrap; margin-top:12px; }
.report-badge { background:#fff1f2; color:#be123c; border:1px solid #fecdd3; border-radius:999px; padding:7px 11px; font-size:12px; font-weight:900; }
.report-control-panel { background:#fff; border:1px solid rgba(226,232,240,.98); border-radius:24px; padding:18px; box-shadow:0 16px 38px rgba(17,24,39,.08); margin:12px 0 18px 0; }
.report-control-panel h3 { margin:0 0 8px 0; font-size:18px; font-weight:900; color:#111827; }
.report-summary-grid { display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:12px; margin:12px 0 18px 0; }
.report-summary-card { background:linear-gradient(135deg,#fff,#fff7f7); border:1px solid rgba(227,24,55,.12); border-radius:20px; padding:14px; box-shadow:0 12px 28px rgba(17,24,39,.07); }
.report-summary-card small { display:block; color:#64748b; font-size:11px; font-weight:900; text-transform:uppercase; }
.report-summary-card b { display:block; margin-top:5px; color:#111827; font-size:22px; font-weight:900; }
.report-summary-card span { color:#e31837; font-size:12px; font-weight:800; }
@media (max-width:900px){ .report-summary-grid{grid-template-columns:repeat(1,minmax(0,1fr));} .report-center-wrap{border-radius:22px;padding:14px;} }


/* ============================================================
   SELVA MOTORS HERO MOVING ANIMATION PATCH
   CSS only - app logic not affected
   ============================================================ */

.hero-login-logo-img {
    animation: heroLogoFloat 3.2s ease-in-out infinite;
    transform-origin: center;
}

@keyframes heroLogoFloat {
    0% { transform: translateY(0px) scale(1); filter: drop-shadow(0 12px 20px rgba(227,24,55,.18)); }
    50% { transform: translateY(-9px) scale(1.045); filter: drop-shadow(0 20px 34px rgba(227,24,55,.36)); }
    100% { transform: translateY(0px) scale(1); filter: drop-shadow(0 12px 20px rgba(227,24,55,.18)); }
}

.login-hero {
    position: relative;
    overflow: hidden;
}

.login-hero::after {
    content: "";
    position: absolute;
    width: 230px;
    height: 230px;
    border-radius: 999px;
    background: radial-gradient(circle, rgba(227,24,55,.22), transparent 66%);
    top: -80px;
    right: -80px;
    z-index: 0;
    animation: heroRedGlowMove 4.4s ease-in-out infinite;
}

.login-hero::before {
    content: "";
    position: absolute;
    width: 260px;
    height: 260px;
    border-radius: 999px;
    background: radial-gradient(circle, rgba(17,24,39,.12), transparent 70%);
    bottom: -105px;
    left: -105px;
    z-index: 0;
    animation: heroDarkGlowMove 5.2s ease-in-out infinite;
}

.login-hero > * {
    position: relative;
    z-index: 1;
}

@keyframes heroRedGlowMove {
    0% { transform: translate(0,0) scale(1); opacity: .55; }
    50% { transform: translate(-34px, 42px) scale(1.25); opacity: .86; }
    100% { transform: translate(0,0) scale(1); opacity: .55; }
}

@keyframes heroDarkGlowMove {
    0% { transform: translate(0,0) scale(1); opacity: .40; }
    50% { transform: translate(38px,-34px) scale(1.18); opacity: .70; }
    100% { transform: translate(0,0) scale(1); opacity: .40; }
}

.hero-connect-title {
    animation: heroTitleSlide 650ms ease-out both;
}

@keyframes heroTitleSlide {
    from { opacity: 0; transform: translateY(12px) scale(.98); }
    to { opacity: 1; transform: translateY(0) scale(1); }
}

[data-testid="stSidebar"] img {
    animation: sidebarLogoFloat 3.8s ease-in-out infinite;
}

@keyframes sidebarLogoFloat {
    0% { transform: translateY(0px); }
    50% { transform: translateY(-5px); }
    100% { transform: translateY(0px); }
}

.stApp::before {
    content: "";
    position: fixed;
    width: 420px;
    height: 420px;
    top: -180px;
    right: -180px;
    border-radius: 999px;
    background: radial-gradient(circle, rgba(227,24,55,.13), transparent 70%);
    z-index: 0;
    pointer-events: none;
    animation: appRedAura 7s ease-in-out infinite;
}

@keyframes appRedAura {
    0% { transform: translate(0,0) scale(1); opacity: .50; }
    50% { transform: translate(-80px,70px) scale(1.18); opacity: .84; }
    100% { transform: translate(0,0) scale(1); opacity: .50; }
}

.hero-panel {
    position: relative;
    overflow: hidden;
}

.hero-panel::before {
    content: "";
    position: absolute;
    top: 0;
    left: -120%;
    width: 55%;
    height: 100%;
    background: linear-gradient(110deg, transparent, rgba(255,255,255,.16), transparent);
    animation: heroPanelShine 5.8s ease-in-out infinite;
}

@keyframes heroPanelShine {
    0% { left: -120%; }
    45% { left: 130%; }
    100% { left: 130%; }
}

.stButton > button,
.stDownloadButton > button {
    transition: transform .18s ease, box-shadow .18s ease, filter .18s ease !important;
    animation: heroButtonSoftGlow 3.3s ease-in-out infinite;
}

.stButton > button:hover,
.stDownloadButton > button:hover {
    transform: translateY(-2px) scale(1.01) !important;
    filter: brightness(1.06) !important;
}

@keyframes heroButtonSoftGlow {
    0% { box-shadow: 0 10px 24px rgba(227,24,55,.16); }
    50% { box-shadow: 0 16px 38px rgba(227,24,55,.32); }
    100% { box-shadow: 0 10px 24px rgba(227,24,55,.16); }
}

.metric-card,
.quick-card,
.glow-card,
.erp-card,
.ultra-card,
.report-summary-card,
.report-control-panel,
.invoice-preview-pro,
.bill-preview,
.approval-card,
.professional-panel {
    transition: transform .22s ease, box-shadow .22s ease, border-color .22s ease !important;
}

.metric-card:hover,
.quick-card:hover,
.glow-card:hover,
.erp-card:hover,
.ultra-card:hover,
.report-summary-card:hover,
.report-control-panel:hover,
.invoice-preview-pro:hover,
.bill-preview:hover,
.approval-card:hover,
.professional-panel:hover {
    transform: translateY(-5px) scale(1.006);
    box-shadow: 0 24px 58px rgba(17,24,39,.13), 0 0 44px rgba(227,24,55,.10) !important;
    border-color: rgba(227,24,55,.28) !important;
}

.report-badge,
.feature-pill,
.status-chip {
    animation: badgeSoftPulse 3.6s ease-in-out infinite;
}

@keyframes badgeSoftPulse {
    0% { box-shadow: 0 0 0 rgba(227,24,55,0); }
    50% { box-shadow: 0 0 18px rgba(227,24,55,.16); }
    100% { box-shadow: 0 0 0 rgba(227,24,55,0); }
}

.hero-panel::after {
    animation: bikeGhostMove 4.6s ease-in-out infinite !important;
}

@keyframes bikeGhostMove {
    0% { transform: translateX(0) scale(1); opacity: .08; }
    50% { transform: translateX(-18px) scale(1.04); opacity: .15; }
    100% { transform: translateX(0) scale(1); opacity: .08; }
}

[data-testid="stDataFrame"] {
    animation: tableFadeIn .32s ease-out both;
}

@keyframes tableFadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}

@media (prefers-reduced-motion: reduce) {
    .hero-login-logo-img,
    .login-hero::after,
    .login-hero::before,
    .hero-connect-title,
    [data-testid="stSidebar"] img,
    .stApp::before,
    .hero-panel::before,
    .stButton > button,
    .stDownloadButton > button,
    .report-badge,
    .feature-pill,
    .status-chip,
    .hero-panel::after,
    [data-testid="stDataFrame"] {
        animation: none !important;
    }
}


/* ============================================================
   HERO LOGIN PREMIUM CORNER LIGHT / CROP DESIGN PATCH
   CSS only - app logic not affected
   ============================================================ */

/* Main login card: premium glass + corner lights */
.login-hero {
    max-width: 590px !important;
    padding: 36px !important;
    border-radius: 36px !important;
    background:
        radial-gradient(circle at 0% 0%, rgba(227,24,55,.24), transparent 38%),
        radial-gradient(circle at 100% 0%, rgba(255,255,255,.90), transparent 34%),
        linear-gradient(145deg, rgba(255,255,255,.98), rgba(255,241,242,.92)) !important;
    border: 1px solid rgba(227,24,55,.22) !important;
    box-shadow:
        0 38px 100px rgba(17,24,39,.24),
        0 0 80px rgba(227,24,55,.13),
        inset 0 1px 0 rgba(255,255,255,.70) !important;
}

/* Top-right corner crop light */
.login-hero .hero-login-panel {
    position: relative;
    overflow: hidden;
    border-radius: 32px !important;
    background:
        radial-gradient(circle at 92% 8%, rgba(227,24,55,.17), transparent 28%),
        linear-gradient(145deg, rgba(255,255,255,.96), rgba(255,248,248,.91)) !important;
    border: 1px solid rgba(227,24,55,.16) !important;
    box-shadow:
        0 25px 65px rgba(17,24,39,.14),
        inset 0 1px 0 rgba(255,255,255,.82) !important;
}

/* Decorative red cropped corner */
.hero-login-panel::before {
    content: "";
    position: absolute;
    width: 170px;
    height: 170px;
    top: -82px;
    right: -82px;
    border-radius: 42px;
    background:
        linear-gradient(135deg, rgba(227,24,55,.95), rgba(127,0,22,.88));
    transform: rotate(18deg);
    box-shadow: 0 22px 55px rgba(227,24,55,.25);
    animation: cornerCropPulse 4.5s ease-in-out infinite;
    z-index: 0;
}

/* White glass shine from corner */
.hero-login-panel::after {
    content: "";
    position: absolute;
    width: 160px;
    height: 360px;
    top: -115px;
    right: 38px;
    background: linear-gradient(105deg, transparent, rgba(255,255,255,.45), transparent);
    transform: rotate(28deg);
    animation: cornerLightSweep 4.8s ease-in-out infinite;
    z-index: 0;
}

@keyframes cornerCropPulse {
    0% { transform: rotate(18deg) scale(1); opacity: .72; }
    50% { transform: rotate(24deg) scale(1.10); opacity: .92; }
    100% { transform: rotate(18deg) scale(1); opacity: .72; }
}

@keyframes cornerLightSweep {
    0% { transform: translateX(140px) rotate(28deg); opacity: 0; }
    35% { opacity: .55; }
    60% { transform: translateX(-310px) rotate(28deg); opacity: .18; }
    100% { transform: translateX(-310px) rotate(28deg); opacity: 0; }
}

/* Logo becomes premium crop badge */
.hero-login-logo-img {
    position: relative;
    z-index: 2;
    max-width: 205px !important;
    padding: 14px 18px;
    border-radius: 24px;
    background: rgba(255,255,255,.95);
    border: 1px solid rgba(227,24,55,.15);
    box-shadow:
        0 18px 42px rgba(227,24,55,.20),
        0 0 0 7px rgba(255,241,242,.80),
        inset 0 1px 0 rgba(255,255,255,.85);
    animation: premiumLogoFloat 3.6s ease-in-out infinite !important;
}

/* Crop-like half shadow around logo */
.hero-login-logo-img::selection {
    background: transparent;
}

@keyframes premiumLogoFloat {
    0% {
        transform: translateY(0px) scale(1);
        filter: drop-shadow(0 12px 20px rgba(227,24,55,.18));
    }
    50% {
        transform: translateY(-10px) scale(1.055);
        filter: drop-shadow(0 24px 40px rgba(227,24,55,.34));
    }
    100% {
        transform: translateY(0px) scale(1);
        filter: drop-shadow(0 12px 20px rgba(227,24,55,.18));
    }
}

/* Login title premium */
.hero-connect-title {
    position: relative;
    z-index: 2;
    font-size: 44px !important;
    font-weight: 900 !important;
    color: #111827 !important;
    letter-spacing: -1.2px;
    text-shadow: 0 12px 28px rgba(17,24,39,.10);
}

.hero-connect-title::after {
    content: "";
    display: block;
    width: 86px;
    height: 4px;
    border-radius: 999px;
    margin: 14px auto 0 auto;
    background: linear-gradient(90deg, transparent, #e31837, transparent);
    animation: titleLineGlow 2.8s ease-in-out infinite;
}

@keyframes titleLineGlow {
    0% { width: 60px; opacity: .45; }
    50% { width: 108px; opacity: 1; }
    100% { width: 60px; opacity: .45; }
}

/* Feature pills over light corner */
.hero-login-panel .feature-strip {
    position: relative;
    z-index: 2;
}

.hero-login-panel .feature-pill {
    background: rgba(255,255,255,.88) !important;
    backdrop-filter: blur(10px);
    border: 1px solid rgba(227,24,55,.20) !important;
    color: #be123c !important;
    box-shadow: 0 10px 28px rgba(227,24,55,.08);
}

/* Login inputs premium focus */
[data-testid="stTextInput"] input:focus {
    border-color: rgba(227,24,55,.55) !important;
    box-shadow:
        0 0 0 4px rgba(227,24,55,.10),
        0 14px 30px rgba(17,24,39,.06) !important;
}

/* Animated login button stronger */
.stButton > button[kind="primary"],
.stButton > button {
    position: relative;
    overflow: hidden;
}

.stButton > button::before {
    content: "";
    position: absolute;
    inset: 0;
    left: -120%;
    width: 70%;
    background: linear-gradient(110deg, transparent, rgba(255,255,255,.28), transparent);
    animation: buttonShineMove 4s ease-in-out infinite;
}

@keyframes buttonShineMove {
    0% { left: -120%; }
    45% { left: 130%; }
    100% { left: 130%; }
}

/* Login note style */
.hero-login-note {
    padding: 9px 12px;
    border-radius: 999px;
    background: rgba(255,255,255,.76);
    border: 1px solid rgba(227,24,55,.10);
    box-shadow: 0 10px 24px rgba(17,24,39,.05);
}

/* Mobile login adjustments */
@media (max-width: 768px) {
    .login-hero {
        padding: 22px !important;
        border-radius: 28px !important;
    }
    .hero-login-panel {
        padding: 22px !important;
        border-radius: 24px !important;
    }
    .hero-login-logo-img {
        max-width: 175px !important;
        padding: 11px 14px;
    }
    .hero-connect-title {
        font-size: 35px !important;
    }
    .hero-login-panel::before {
        width: 135px;
        height: 135px;
        top: -72px;
        right: -72px;
    }
}


.hero-login-status-badge {
    position: relative;
    z-index: 2;
    text-align: center;
    margin: -8px auto 18px auto;
    display: table;
    padding: 7px 13px;
    border-radius: 999px;
    background: linear-gradient(135deg, #111827, #e31837);
    color: #fff;
    font-size: 11px;
    font-weight: 900;
    letter-spacing: .8px;
    box-shadow: 0 14px 30px rgba(227,24,55,.18);
    animation: badgeSlideIn 700ms ease-out both;
}
@keyframes badgeSlideIn {
    from { opacity: 0; transform: translateY(8px) scale(.96); }
    to { opacity: 1; transform: translateY(0) scale(1); }
}


/* ============================================================
   ATTENDANCE MAP + KM DISTANCE PATCH
   CSS only + Attendance UI enhancement
   ============================================================ */
.att-map-card {
    background:
        radial-gradient(circle at 100% 0%, rgba(34,197,94,.16), transparent 32%),
        linear-gradient(135deg, #ffffff, #f0fdf4);
    border: 1px solid rgba(34,197,94,.25);
    border-radius: 24px;
    padding: 18px;
    box-shadow: 0 18px 44px rgba(15,23,42,.09);
    margin: 14px 0 18px 0;
}
.att-map-card h3 { margin: 0; font-size: 19px; font-weight: 900; color: #0f172a; }
.att-map-card p { color: #475569; font-size: 13px; margin: 8px 0 0 0; font-weight: 700; }
.att-map-actions { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 14px; }
.att-map-btn {
    display: inline-block;
    padding: 10px 14px;
    border-radius: 14px;
    background: linear-gradient(135deg, #16a34a, #111827);
    color: #ffffff !important;
    text-decoration: none !important;
    font-weight: 900;
    font-size: 13px;
    box-shadow: 0 12px 28px rgba(22,163,74,.18);
}
.att-map-btn.secondary { background: linear-gradient(135deg, #e31837, #111827); }
.att-distance-chip {
    display:inline-block;
    padding: 7px 11px;
    border-radius: 999px;
    background:#dcfce7;
    color:#166534;
    font-weight:900;
    font-size:12px;
    margin-top:10px;
}
@media (max-width: 768px) {
    .att-map-actions { flex-direction: column; }
    .att-map-btn { text-align:center; width:100%; }
}


/* ============================================================
   SELVA MOTORS MONTHLY ATTENDANCE + ADMIN BIG DATA PATCH
   Logic safe patch
   ============================================================ */
.monthly-att-panel, .bigdata-panel, .password-reset-panel {
    background: linear-gradient(135deg, #ffffff, #fff7f7);
    border: 1px solid rgba(227,24,55,.14);
    border-radius: 24px;
    padding: 16px;
    box-shadow: 0 16px 38px rgba(17,24,39,.08);
    margin: 12px 0 18px 0;
}
.monthly-att-panel h3, .bigdata-panel h3, .password-reset-panel h3 {
    margin: 0 0 6px 0;
    color: #111827;
    font-size: 18px;
    font-weight: 900;
}
.monthly-att-panel p, .bigdata-panel p, .password-reset-panel p {
    margin: 0;
    color: #64748b;
    font-size: 13px;
    font-weight: 700;
}
.bigdata-warning {
    background: #fffbeb;
    border: 1px solid #fde68a;
    color: #92400e;
    padding: 12px 14px;
    border-radius: 16px;
    font-weight: 800;
    margin: 10px 0 14px 0;
}


/* ============================================================
   GOOGLE SHEET TO CLOUD EXCEL PULL SYNC PATCH
   ============================================================ */
.pull-sync-panel {
    background: linear-gradient(135deg, #ffffff, #eff6ff);
    border: 1px solid rgba(37,99,235,.18);
    border-radius: 24px;
    padding: 16px;
    box-shadow: 0 16px 38px rgba(15,23,42,.08);
    margin: 12px 0 18px 0;
}
.pull-sync-panel h3 {
    margin: 0 0 6px 0;
    color: #0f172a;
    font-size: 18px;
    font-weight: 900;
}
.pull-sync-panel p {
    margin: 0;
    color: #475569;
    font-size: 13px;
    font-weight: 700;
}
.pull-sync-warning {
    background: #fff7ed;
    border: 1px solid #fed7aa;
    color: #9a3412;
    border-radius: 16px;
    padding: 12px 14px;
    font-weight: 800;
    margin: 10px 0 14px 0;
}


/* ============================================================
   CLOUD EXCEL VIEW ONLY PATCH
   ============================================================ */
.cloud-view-panel {
    background: linear-gradient(135deg, #ffffff, #eff6ff);
    border: 1px solid rgba(37,99,235,.18);
    border-radius: 24px;
    padding: 16px;
    box-shadow: 0 16px 38px rgba(15,23,42,.08);
    margin: 12px 0 18px 0;
}
.cloud-view-panel h3 { margin:0 0 6px 0; color:#0f172a; font-size:18px; font-weight:900; }
.cloud-view-panel p { margin:0; color:#475569; font-size:13px; font-weight:700; }

</style>
""", unsafe_allow_html=True)



def get_hero_logo_base64():
    """
    Robust Hero logo loader.
    Priority:
    1. assets/hero_logo.jpg
    2. hero_logo.jpg in root
    3. Hero logo common filenames
    4. Embedded base64 logo inside app.py
    """
    possible_paths = [
        Path("assets") / "hero_logo.jpg",
        Path("assets") / "hero_logo.png",
        Path("hero_logo.jpg"),
        Path("hero_logo.png"),
        Path("Hero.png"),
        Path("hero.png"),
        Path("logo.jpg"),
        Path("logo.png"),
    ]

    for p in possible_paths:
        try:
            if p.exists():
                return base64.b64encode(p.read_bytes()).decode("utf-8")
        except Exception:
            pass

    try:
        return EMBEDDED_HERO_LOGO_B64
    except Exception:
        return ""


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
        "Invoice Number", "Job Card Number", "Registration Number", "Bike Model", "Service Type",
        "Labour Amount", "Spare Parts Count", "Spare Amount", "Oil Change Status",
        "Total Amount", "Entry Type", "Status"
    ],
    "delete_requests": [
        "Request ID", "Date", "Time", "Entry ID", "Technician Name",
        "User ID", "Reason", "Request Status", "Admin Action Date"
    ],
    "pending_invoice_requests": [
        "Request ID", "Date", "Time", "Technician Name", "User ID",
        "Invoice Number", "Job Card Number", "Registration Number", "Bike Model", "Service Type",
        "Labour Amount", "Spare Parts Count", "Spare Amount", "Oil Change Status",
        "Total Amount", "Entry Type", "Request Status", "Admin Action Date"
    ],
    "manual_invoices": [
        "Manual Bill ID", "Date", "Technician Name", "User ID",
        "Customer Name", "Registration Number", "Bike Model", "Service Type",
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
    ["prathisha", "prathisha", "Prathisha", "Prathisha / System Staff", "Active"]]


def today_str():
    return app_now().strftime("%d-%m-%Y")


def time_str():
    return app_now().strftime("%I:%M:%S %p")


def now_stamp():
    return app_now().strftime("%d-%m-%Y %I:%M:%S %p")


def create_excel_if_missing():
    if not EXCEL_FILE.exists():
        with pd.ExcelWriter(EXCEL_FILE, engine="openpyxl") as writer:
            for sheet, cols in SHEETS.items():
                df = pd.DataFrame(columns=cols)

                if sheet == "employees":
                    df = pd.DataFrame(DEFAULT_EMPLOYEES, columns=cols)

                if sheet == "settings":
                    version = VERSION_TEXT if "VERSION_TEXT" in globals() else "Excel Storage Version"
                    df = pd.DataFrame([
                        ["Storage Type", "Excel Only"],
                        ["Version", version],
                        ["Excel File Path", str(EXCEL_FILE)],
                        ["Company Latitude", str(COMPANY_LAT)],
                        ["Company Longitude", str(COMPANY_LON)],
                        ["Allowed Radius Meter", str(ALLOWED_RADIUS_METER)]], columns=cols)

                df.to_excel(writer, sheet_name=sheet, index=False)
        return

    # Existing Excel file: add missing sheets/columns without data loss
    try:
        existing = pd.read_excel(EXCEL_FILE, sheet_name=None, engine="openpyxl")
    except Exception:
        existing = {}

    changed = False
    for sheet, cols in SHEETS.items():
        if sheet not in existing:
            existing[sheet] = pd.DataFrame(columns=cols)
            changed = True

        for col in cols:
            if col not in existing[sheet].columns:
                existing[sheet][col] = ""
                changed = True

        existing[sheet] = existing[sheet][cols].fillna("")

    if changed:
        with pd.ExcelWriter(EXCEL_FILE, engine="openpyxl", mode="w") as writer:
            for name, df in existing.items():
                df.to_excel(writer, sheet_name=name, index=False)


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
            temp = temp.astype("object").fillna("")
            all_sheets[name] = temp[SHEETS[name]]
        else:
            all_sheets[name] = read_sheet(name)

    with pd.ExcelWriter(EXCEL_FILE, engine="openpyxl", mode="w") as writer:
        for name, data in all_sheets.items():
            data.to_excel(writer, sheet_name=name, index=False)

    # Fast mode:
    # Save to Excel now, mark changed sheet for Google Sheet sync after 3 minutes.
    try:
        if "mark_sheet_dirty" in globals():
            mark_sheet_dirty(sheet_name)
    except Exception:
        pass


def append_row(sheet_name, row_dict):
    df = read_sheet(sheet_name)
    clean_row = {col: row_dict.get(col, "") for col in SHEETS[sheet_name]}
    df = pd.concat([df, pd.DataFrame([clean_row])], ignore_index=True)
    write_sheet(sheet_name, df)


create_excel_if_missing()




def pull_single_google_sheet_to_excel(sheet_name):
    """
    Pull one Google worksheet into local Cloud Excel sheet.
    Useful when user edits/deletes rows directly in Google Sheet and wants app Excel to match.
    """
    if not is_google_auto_sync_enabled():
        return False, "Google Sheet secrets not configured."

    try:
        sheet_id = st.secrets.get("SHEET_ID", "")
        client, err = google_sheet_client()
        if client is None:
            return False, err

        spreadsheet = client.open_by_key(sheet_id)
        try:
            ws = spreadsheet.worksheet(sheet_name)
        except Exception:
            return False, f"Google Sheet worksheet not found: {sheet_name}"

        values = ws.get_all_values()
        if not values:
            new_df = pd.DataFrame(columns=SHEETS[sheet_name])
        else:
            headers = [str(h).strip() for h in values[0]]
            rows = values[1:]
            new_df = pd.DataFrame(rows, columns=headers)

        for col in SHEETS[sheet_name]:
            if col not in new_df.columns:
                new_df[col] = ""

        new_df = new_df[SHEETS[sheet_name]].astype("object").fillna("")
        write_sheet(sheet_name, new_df)

        try:
            state = load_google_sync_state()
            dirty = set(state.get("dirty_sheets", []))
            if sheet_name in dirty:
                dirty.remove(sheet_name)
            state["dirty_sheets"] = sorted(list(dirty))
            state["last_sync_status"] = "Pulled from Google Sheet"
            state["last_sync_time"] = app_now().strftime("%d-%m-%Y %I:%M:%S %p")
            state["last_sync_message"] = f"{sheet_name} pulled from Google Sheet to Cloud Excel"
            save_sync_state(state)
        except Exception:
            pass

        return True, f"{sheet_name} pulled from Google Sheet to Cloud Excel. Rows: {len(new_df)}"
    except Exception as e:
        return False, str(e)


def pull_all_google_sheets_to_excel():
    """
    Pull all worksheets from Google Sheet into Cloud Excel.
    This overwrites matching Excel sheets with Google Sheet data.
    """
    if not is_google_auto_sync_enabled():
        return False, "Google Sheet secrets not configured."

    pulled = []
    failed = []

    for sheet_name in SHEETS.keys():
        ok, msg = pull_single_google_sheet_to_excel(sheet_name)
        if ok:
            pulled.append(sheet_name)
        else:
            failed.append(f"{sheet_name}: {msg}")

    if failed:
        return False, "; ".join(failed)[:700]

    return True, "Pulled all Google Sheet data to Cloud Excel: " + ", ".join(pulled)



# ============================================================
# GOOGLE SHEET BACKUP SYNC
# Primary storage is still Excel. Google Sheet is only backup/sync.
# ============================================================
def google_sheet_client():
    if gspread is None or Credentials is None:
        return None, "gspread/google-auth not installed. Add gspread and google-auth in requirements.txt"

    try:
        if "gcp_service_account" not in st.secrets:
            return None, "Streamlit secrets missing: gcp_service_account"

        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=scope
        )
        client = gspread.authorize(creds)
        return client, ""
    except Exception as e:
        return None, str(e)


def get_or_create_worksheet(spreadsheet, sheet_name, rows=1000, cols=30):
    try:
        return spreadsheet.worksheet(sheet_name)
    except Exception:
        return spreadsheet.add_worksheet(title=sheet_name, rows=rows, cols=cols)


def dataframe_to_sheet_values(df):
    clean_df = df.copy().fillna("")
    clean_df = clean_df.astype(str)
    return [clean_df.columns.tolist()] + clean_df.values.tolist()



def is_google_auto_sync_enabled():
    """
    Google Sheet auto store will work only when Streamlit secrets are configured.
    Excel remains primary storage, Google Sheet is automatic cloud copy.
    """
    return bool(st.secrets.get("SHEET_ID", "")) and ("gcp_service_account" in st.secrets)


def sync_single_excel_sheet_to_google_sheet(sheet_name):
    """
    Sync only the changed Excel sheet to Google Sheet immediately after saving.
    This is faster than syncing all sheets after every entry.
    """
    if not is_google_auto_sync_enabled():
        return False, "Google Sheet secrets not configured"

    try:
        sheet_id = st.secrets.get("SHEET_ID", "")
        client, err = google_sheet_client()
        if client is None:
            return False, err

        spreadsheet = client.open_by_key(sheet_id)
        df = read_sheet(sheet_name)

        ws = get_or_create_worksheet(
            spreadsheet,
            sheet_name,
            rows=max(len(df) + 20, 100),
            cols=max(len(df.columns) + 5, 20)
        )

        ws.clear()
        values = dataframe_to_sheet_values(df)
        if values:
            ws.update(values)

        return True, f"{sheet_name} synced to Google Sheet"
    except Exception as e:
        return False, str(e)




def load_google_sync_state():
    try:
        if SYNC_STATE_FILE.exists():
            return json.loads(SYNC_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass

    return {
        "dirty_sheets": [],
        "last_sync_ts": 0,
        "last_sync_time": "Not yet",
        "last_sync_status": "Not yet",
        "last_sync_message": "",
        "last_change_time": "Not yet"
    }


def save_sync_state(state):
    try:
        SYNC_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception:
        pass


def mark_sheet_dirty(sheet_name):
    state = load_google_sync_state()
    dirty = set(state.get("dirty_sheets", []))
    dirty.add(sheet_name)
    state["dirty_sheets"] = sorted(list(dirty))
    state["last_change_time"] = app_now().strftime("%d-%m-%Y %I:%M:%S %p")
    save_sync_state(state)


def sync_changed_sheets_to_google():
    state = load_google_sync_state()
    dirty_sheets = state.get("dirty_sheets", [])

    if not dirty_sheets:
        return True, "No changed sheets to sync."

    if not is_google_auto_sync_enabled():
        return False, "Google Sheet secrets not configured."

    synced = []
    failed = []

    for sheet_name in dirty_sheets:
        ok, msg = sync_single_excel_sheet_to_google_sheet(sheet_name)
        if ok:
            synced.append(sheet_name)
        else:
            failed.append(f"{sheet_name}: {msg}")

    now = app_now()

    if failed:
        state["last_sync_status"] = "Failed"
        state["last_sync_message"] = "; ".join(failed)[:500]
        state["last_sync_time"] = now.strftime("%d-%m-%Y %I:%M:%S %p")
        save_sync_state(state)
        return False, state["last_sync_message"]

    state["dirty_sheets"] = []
    state["last_sync_ts"] = now.timestamp()
    state["last_sync_time"] = now.strftime("%d-%m-%Y %I:%M:%S %p")
    state["last_sync_status"] = "Success"
    state["last_sync_message"] = "Synced sheets: " + ", ".join(synced)
    save_sync_state(state)

    return True, state["last_sync_message"]



def get_google_next_sync_wait_text():
    """
    Returns readable waiting time for next 3-minute Google Sheet sync.
    """
    try:
        state = load_google_sync_state()
        dirty_sheets = state.get("dirty_sheets", [])

        if not dirty_sheets:
            return "No pending sync"

        last_sync_ts = float(state.get("last_sync_ts", 0) or 0)
        now_ts = app_now().timestamp()
        interval = 3 * 60

        if last_sync_ts == 0:
            return "Ready to sync now"

        remaining = int(interval - (now_ts - last_sync_ts))

        if remaining <= 0:
            return "Ready to sync now"

        minutes = remaining // 60
        seconds = remaining % 60
        return f"{minutes} min {seconds} sec remaining"

    except Exception:
        return "Waiting time not available"


def get_sync_status_badge_text():
    state = load_google_sync_state()
    dirty_sheets = state.get("dirty_sheets", [])
    status = state.get("last_sync_status", "Not yet")

    if dirty_sheets:
        return "Waiting for Google Sheet update"

    if status == "Success":
        return "Updated to Google Sheet"

    return status


def auto_sync_google_sheet_3min():
    """
    Excel save is instant and fast.
    Google Sheet sync runs only once every 3 minutes when app opens/reruns.
    """
    try:
        state = load_google_sync_state()
        dirty_sheets = state.get("dirty_sheets", [])

        if not dirty_sheets:
            return

        now_ts = app_now().timestamp()
        last_sync_ts = float(state.get("last_sync_ts", 0) or 0)
        sync_interval = 3 * 60

        if now_ts - last_sync_ts < sync_interval:
            return

        sync_changed_sheets_to_google()

    except Exception:
        pass



def sync_all_excel_to_google():
    """
    Copies all local Excel sheets to Google Sheet.
    This does not replace Excel storage. It is only a manual cloud backup.
    """
    if not EXCEL_FILE.exists():
        return False, "Excel file not found. Save some data first."

    sheet_id = st.secrets.get("SHEET_ID", "")
    if not sheet_id:
        return False, "Streamlit secrets missing: SHEET_ID"

    client, err = google_sheet_client()
    if client is None:
        return False, err

    try:
        spreadsheet = client.open_by_key(sheet_id)

        synced = []
        for sheet_name in SHEETS.keys():
            df = read_sheet(sheet_name)
            ws = get_or_create_worksheet(
                spreadsheet,
                sheet_name,
                rows=max(len(df) + 20, 100),
                cols=max(len(df.columns) + 5, 20)
            )

            ws.clear()
            values = dataframe_to_sheet_values(df)
            if values:
                ws.update(values)

            synced.append(f"{sheet_name} ({len(df)} rows)")

        return True, "Synced to Google Sheet: " + ", ".join(synced)

    except Exception as e:
        return False, str(e)




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


def reg_no_or_fr(value):
    """
    If Registration Number is missing in OCR, save as FR.
    """
    reg = clean_reg_no(value)
    return reg if reg else "FR"


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


def auto_save_attendance_from_gps(lat, lon):
    user_id = st.session_state["user_id"]
    name = st.session_state["employee_name"]
    user_role = st.session_state["role"]

    dist = distance_meter(lat, lon, COMPANY_LAT, COMPANY_LON)

    if dist > ALLOWED_RADIUS_METER:
        return False, dist

    append_row("attendance", {
        "Date": today_str(),
        "Time": time_str(),
        "User ID": user_id,
        "Technician Name": name,
        "Role": user_role,
        "Attendance Status": "Present",
        "Latitude": lat,
        "Longitude": lon,
        "Distance Meter": dist,
        "Selfie Saved": "No"
    })

    return True, dist



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
        # "2 SPDMCYL09SS-HERO 4T ..."
        # Avoid continuation like "10W30..." because digit+letter has no word boundary.
        if re.match(r"^\d+\b", line) and not re.match(r"^\d{4,}", line):
            count += 1

    return count



def extract_genuine_spare_details(text):
    """
    Extract spare item descriptions from Genuine Parts section for preview/debug only.
    Not saved into Excel to avoid unwanted data.
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
    Detect oil internally but do not save/show oil item names.
    Supports:
    SPDMCYL09SS-HERO 4T PLUS 10W30 SL MA2(1000 ML)
    SPDSCOT01SS-HERO 4T PLUS 10W30 SL MB(800 ML)
    """
    if not text:
        return 0, "-"

    flat = re.sub(r"\s+", " ", text).upper()
    oil_patterns = [
        r"HERO\s*4T\s*PLUS",
        r"SPDMCYL09SS\s*-\s*HERO\s*4T",
        r"SPDSCOT01SS\s*-\s*HERO\s*4T",
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
        "Registration Number": reg_no_or_fr(reg_no),
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


def duplicate_exists(job_card_no, reg_no=None, total_amount=None):
    """
    Upload duplicate blocking removed.
    Manager will find and delete duplicate Job Card uploads later.
    """
    return False


def get_existing_jobcards_list():
    """
    Admin/debug use only: returns clean existing jobcards from invoices sheet.
    """
    try:
        inv = read_sheet("invoices")
        if inv.empty or "Job Card Number" not in inv.columns:
            return []
        existing = inv["Job Card Number"].astype(str).apply(normalize_invoice_jobcard_no)
        return existing[existing.astype(str).str.len() > 0].tolist()
    except Exception:
        return []


def create_pending_invoice_request(data):
    """
    Store duplicate invoice entry as Admin approval request.
    It will not be saved into invoices until Admin approves.
    """
    request_id = "PIR-" + uuid.uuid4().hex[:8].upper()
    append_row("pending_invoice_requests", {
        "Request ID": request_id,
        "Date": today_str(),
        "Time": time_str(),
        "Technician Name": st.session_state.get("employee_name", ""),
        "User ID": st.session_state.get("user_id", ""),
        "Invoice Number": data.get("Invoice Number", ""),
        "Job Card Number": data.get("Job Card Number", ""),
        "Registration Number": reg_no_or_fr(data.get("Registration Number", "")),
        "Bike Model": clean_bike_model(data.get("Bike Model", "")),
        "Service Type": data.get("Service Type", strong_detect_service_type(str(data))),
        "Labour Amount": data.get("Labour Amount", 0),
        "Spare Parts Count": data.get("Spare Parts Count", 0),
        "Spare Amount": data.get("Spare Amount", 0),
        "Oil Change Status": data.get("Oil Change Status", "No"),
        "Total Amount": data.get("Total Amount", 0),
        "Entry Type": "Duplicate Approval Request",
        "Request Status": "Pending",
        "Admin Action Date": ""
    })
    return request_id


def save_invoice_entry_from_data(data, entry_type="OCR Upload"):
    entry_id = "E-" + uuid.uuid4().hex[:8].upper()
    append_row("invoices", {
        "Entry ID": entry_id,
        "Date": today_str(),
        "Technician Name": st.session_state.get("employee_name", data.get("Technician Name", "")),
        "User ID": st.session_state.get("user_id", data.get("User ID", "")),
        "Invoice Number": data.get("Invoice Number", ""),
        "Job Card Number": data.get("Job Card Number", ""),
        "Registration Number": reg_no_or_fr(data.get("Registration Number", "")),
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
    return entry_id



def processing_wait_3s(message="Processing entry"):
    box = st.empty()
    for sec in [3, 2, 1]:
        box.info(f"{message}... Please wait {sec} seconds.")
        time_module.sleep(1)
    box.empty()



def generate_daily_technician_report_pdf(df, report_date, technician_name="All Technicians"):
    """
    Extreme professional daily technician service report PDF.
    Circle Hero logo + clean SELVA MOTORS placement.
    Shows Total Labour Amount only; Total Amount hidden as requested.
    """
    safe_tech = re.sub(r"[^A-Za-z0-9_-]", "_", str(technician_name or "All"))
    safe_date = re.sub(r"[^0-9-]", "_", str(report_date))
    pdf_path = PDF_DIR / f"daily_technician_service_report_{safe_tech}_{safe_date}.pdf"

    total_entries = len(df)
    total_labour = pd.to_numeric(df.get("Labour Amount", pd.Series([])), errors="coerce").fillna(0).sum() if not df.empty else 0

    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    w, h = A4
    page_no = 1

    draw_pdf_header(
        c, w, h,
        title="Daily Technician Report",
        subtitle="Professional Service Report",
        right_line1=f"Date: {report_date}",
        right_line2=f"Technician: {technician_name}"
    )

    y = h - 145

    # Summary boxes
    pdf_label_value_box(c, 38, y, 160, "Vehicle Entries", total_entries, "#F8FAFC")
    pdf_label_value_box(c, 218, y, 180, "Total Labour Amount", f"Rs.{total_labour:.2f}", "#FFF1F2")
    pdf_label_value_box(c, 418, y, 135, "Report Type", "Daily", "#F8FAFC")

    y -= 70

    c.setFillColor(PDF_TEXT_DARK)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(38, y, "Entry Details")
    y -= 20

    # Table setup - no Total Amount column
    headers = ["S.No", "Technician", "Job Card", "Reg No", "Bike Model", "Service", "Labour"]
    widths = [32, 72, 112, 75, 88, 75, 60]
    x_positions = [38]
    for width in widths[:-1]:
        x_positions.append(x_positions[-1] + width)

    c.setFillColor(PDF_TEXT_DARK)
    c.roundRect(38, y - 6, sum(widths), 22, 7, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 7)

    for i, head in enumerate(headers):
        c.drawString(x_positions[i] + 3, y, head)

    y -= 24
    c.setFont("Helvetica", 7)
    c.setFillColor(PDF_TEXT_DARK)

    if df.empty:
        c.setFillColor(colors.HexColor("#64748B"))
        c.setFont("Helvetica", 9)
        c.drawString(38, y, "No service entries found.")
    else:
        show_df = df.copy().reset_index(drop=True)
        for idx, row in show_df.iterrows():
            if y < 70:
                draw_pdf_footer(c, w, page_no)
                c.showPage()
                page_no += 1
                draw_pdf_header(c, w, h, "Daily Technician Report", "Professional Service Report", f"Date: {report_date}", f"Technician: {technician_name}")
                y = h - 145

                c.setFillColor(PDF_TEXT_DARK)
                c.roundRect(38, y - 6, sum(widths), 22, 7, fill=True, stroke=False)
                c.setFillColor(colors.white)
                c.setFont("Helvetica-Bold", 7)
                for i, head in enumerate(headers):
                    c.drawString(x_positions[i] + 3, y, head)
                y -= 24
                c.setFont("Helvetica", 7)
                c.setFillColor(PDF_TEXT_DARK)

            if idx % 2 == 0:
                c.setFillColor(PDF_ROW_ALT)
                c.roundRect(38, y - 6, sum(widths), 17, 4, fill=True, stroke=False)
                c.setFillColor(PDF_TEXT_DARK)

            vals = [
                str(idx + 1),
                str(row.get("Technician Name", ""))[:13],
                str(row.get("Job Card Number", ""))[:24],
                str(row.get("Registration Number", ""))[:12],
                str(row.get("Bike Model", ""))[:15],
                str(row.get("Service Type", ""))[:13],
                f"Rs.{to_float(row.get('Labour Amount', 0)):.0f}",
            ]

            for i, val in enumerate(vals):
                c.drawString(x_positions[i] + 3, y, val)

            y -= 17

    draw_pdf_footer(c, w, page_no)
    c.save()

    return str(pdf_path)



def report_center_header():
    st.markdown("""
    <div class="report-center-wrap">
        <h2>📑 Selva Motors Professional Report Center</h2>
        <p>Service Report, Daily Technician Report and Attendance Report ellam separate professional tabs-la generate panna mudiyum.</p>
        <div class="report-badge-row">
            <span class="report-badge">All / Particular View</span>
            <span class="report-badge">PDF Download</span>
            <span class="report-badge">Attendance Report</span>
            <span class="report-badge">Technician Wise</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def report_control_panel(title, body):
    st.markdown(
        '<div class="report-control-panel">'
        f'<h3>{title}</h3>'
        f'<p style="color:#64748b;margin:0;font-size:13px;font-weight:700;">{body}</p>'
        '</div>',
        unsafe_allow_html=True
    )


def report_summary_cards(items):
    html = '<div class="report-summary-grid">'
    for label, value, note in items:
        html += (
            '<div class="report-summary-card">'
            f'<small>{label}</small>'
            f'<b>{value}</b>'
            f'<span>{note}</span>'
            '</div>'
        )
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def generate_attendance_report_pdf(df, title, file_name):
    pdf_path = PDF_DIR / file_name
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    w, h = A4

    draw_pdf_reference_outer_look(
        c, w, h,
        title="Attendance Report",
        subtitle="SELVA MOTORS",
        right_line1=f"Generated: {today_str()}",
        right_line2=""
    )

    try:
        draw_pdf_header(c, w, h, title="Attendance Report", subtitle="Professional Attendance Summary", right_line1=f"Generated: {today_str()}", right_line2=title[:35])
    except Exception:
        c.setFillColor(PDF_TEXT_DARK)
        c.rect(0, h - 90, w, 90, fill=True, stroke=False)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(38, h - 42, "SELVA MOTORS")
        c.drawRightString(w - 38, h - 42, "Attendance Report")

    y = h - 140
    total_rows = len(df)
    present_count = 0
    if not df.empty and "Attendance Status" in df.columns:
        present_count = len(df[df["Attendance Status"].astype(str).str.lower() == "present"])

    try:
        pdf_label_value_box(c, 38, y, 155, "Total Records", total_rows, "#F8FAFC")
        pdf_label_value_box(c, 213, y, 155, "Present Count", present_count, "#FFF1F2")
        pdf_label_value_box(c, 388, y, 165, "Report", title[:20], "#F8FAFC")
    except Exception:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(38, y, f"Total Records: {total_rows}  |  Present: {present_count}")

    y -= 72
    c.setFillColor(PDF_TEXT_DARK)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(38, y, "Attendance Details")
    y -= 20

    headers = ["S.No", "Date", "Time", "User ID", "Name", "Role", "Status", "Distance"]
    widths = [32, 70, 70, 62, 85, 82, 62, 58]
    x_positions = [38]
    for width in widths[:-1]:
        x_positions.append(x_positions[-1] + width)

    def draw_table_header(y_pos):
        c.setFillColor(PDF_TEXT_DARK)
        c.roundRect(38, y_pos - 6, sum(widths), 22, 7, fill=True, stroke=False)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 7)
        for i, head in enumerate(headers):
            c.drawString(x_positions[i] + 3, y_pos, head)

    draw_table_header(y)
    y -= 24
    page_no = 1

    if df.empty:
        c.setFillColor(colors.HexColor("#64748B"))
        c.setFont("Helvetica", 9)
        c.drawString(38, y, "No attendance records found.")
    else:
        show_df = df.copy().reset_index(drop=True)
        c.setFont("Helvetica", 7)
        c.setFillColor(colors.black)
        for idx, row in show_df.iterrows():
            if y < 70:
                try:
                    draw_pdf_footer(c, w, page_no)
                except Exception:
                    pass
                c.showPage()
                page_no += 1
                try:
                    draw_pdf_header(c, w, h, "Attendance Report", "Professional Attendance Summary", f"Generated: {today_str()}", title[:35])
                except Exception:
                    pass
                y = h - 145
                draw_table_header(y)
                y -= 24
                c.setFont("Helvetica", 7)
                c.setFillColor(colors.black)

            if idx % 2 == 0:
                c.setFillColor(PDF_ROW_ALT)
                c.roundRect(38, y - 6, sum(widths), 17, 4, fill=True, stroke=False)
                c.setFillColor(colors.black)

            vals = [
                str(idx + 1),
                str(row.get("Date", ""))[:10],
                str(row.get("Time", ""))[:12],
                str(row.get("User ID", ""))[:10],
                str(row.get("Technician Name", ""))[:14],
                str(row.get("Role", ""))[:14],
                str(row.get("Attendance Status", ""))[:10],
                str(row.get("Distance Meter", ""))[:8],
            ]
            for i, val in enumerate(vals):
                c.drawString(x_positions[i] + 3, y, val)
            y -= 17

    try:
        draw_pdf_footer(c, w, page_no)
    except Exception:
        pass
    c.save()
    return str(pdf_path)




def generate_monthly_attendance_report_pdf(df, month_key, selected_user="All Users"):
    """
    Monthly Attendance Report PDF.
    Today report removed; monthly report only.
    """
    safe_user = re.sub(r"[^A-Za-z0-9_-]", "_", str(selected_user or "All"))
    safe_month = re.sub(r"[^0-9-]", "_", str(month_key or "month"))
    pdf_path = PDF_DIR / f"monthly_attendance_report_{safe_user}_{safe_month}.pdf"

    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    w, h = A4

    draw_pdf_reference_outer_look(
        c, w, h,
        title="Attendance Report",
        subtitle="SELVA MOTORS",
        right_line1=f"Generated: {today_str()}",
        right_line2=""
    )

    draw_pdf_light_hero_header(
        c, w, h,
        title="Monthly Attendance Report",
        subtitle="SELVA MOTORS",
        right_line1=f"Month: {month_key}" if "month_key" in locals() else "",
        right_line2=f"Generated: {today_str()}"
    )

    try:
        draw_pdf_header(
            c, w, h,
            title="Monthly Attendance Report",
            subtitle="Selva Motors Attendance Summary",
            right_line1=f"Month: {month_key}",
            right_line2=f"User: {selected_user}"
        )
    except Exception:
        c.setFillColor(PDF_TEXT_DARK)
        c.rect(0, h - 90, w, 90, fill=True, stroke=False)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(38, h - 42, "SELVA MOTORS")
        c.drawRightString(w - 38, h - 42, "Monthly Attendance Report")

    y = h - 140

    total_rows = len(df)
    present_count = 0
    if not df.empty and "Attendance Status" in df.columns:
        present_count = len(df[df["Attendance Status"].astype(str).str.lower() == "present"])

    unique_users = df["Technician Name"].astype(str).nunique() if not df.empty and "Technician Name" in df.columns else 0

    try:
        pdf_label_value_box(c, 38, y, 150, "Total Records", total_rows, "#F8FAFC")
        pdf_label_value_box(c, 208, y, 150, "Present Count", present_count, "#FFF1F2")
        pdf_label_value_box(c, 378, y, 175, "Users", unique_users, "#F8FAFC")
    except Exception:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(38, y, f"Total Records: {total_rows} | Present: {present_count} | Users: {unique_users}")

    y -= 72
    c.setFillColor(PDF_TEXT_DARK)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(38, y, "Attendance Details")
    y -= 20

    headers = ["S.No", "Date", "Time", "User ID", "Name", "Role", "Status", "Distance"]
    widths = [32, 70, 70, 62, 85, 82, 62, 58]
    xs = [38]
    for width in widths[:-1]:
        xs.append(xs[-1] + width)

    def table_header(ypos):
        c.setFillColor(PDF_TEXT_DARK)
        c.roundRect(38, ypos - 6, sum(widths), 22, 7, fill=True, stroke=False)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 7)
        for i, head in enumerate(headers):
            c.drawString(xs[i] + 3, ypos, head)

    table_header(y)
    y -= 24
    page_no = 1

    if df.empty:
        c.setFillColor(colors.HexColor("#64748B"))
        c.setFont("Helvetica", 9)
        c.drawString(38, y, "No attendance records found for this month.")
    else:
        c.setFont("Helvetica", 7)
        c.setFillColor(PDF_TEXT_DARK)
        for idx, row in df.reset_index(drop=True).iterrows():
            if y < 70:
                try:
                    draw_pdf_footer(c, w, page_no)
                except Exception:
                    pass
                c.showPage()
                page_no += 1
                try:
                    draw_pdf_header(c, w, h, "Monthly Attendance Report", "Selva Motors Attendance Summary", f"Month: {month_key}", f"User: {selected_user}")
                except Exception:
                    pass
                y = h - 145
                table_header(y)
                y -= 24
                c.setFont("Helvetica", 7)
                c.setFillColor(PDF_TEXT_DARK)

            if idx % 2 == 0:
                c.setFillColor(PDF_ROW_ALT)
                c.roundRect(38, y - 6, sum(widths), 17, 4, fill=True, stroke=False)
                c.setFillColor(PDF_TEXT_DARK)

            vals = [
                str(idx + 1),
                str(row.get("Date", ""))[:10],
                str(row.get("Time", ""))[:12],
                str(row.get("User ID", ""))[:10],
                str(row.get("Technician Name", ""))[:14],
                str(row.get("Role", ""))[:14],
                str(row.get("Attendance Status", ""))[:10],
                str(row.get("Distance Meter", ""))[:8],
            ]
            for i, val in enumerate(vals):
                c.drawString(xs[i] + 3, y, val)
            y -= 17

    try:
        draw_pdf_footer(c, w, page_no)
    except Exception:
        pass
    c.save()
    return str(pdf_path)




# ============================================================
# PDF PRINT FRIENDLY LIGHT HERO STYLE
# ============================================================
PDF_LIGHT_HEADER = colors.white
PDF_LIGHT_HEADER_STROKE = colors.HexColor("#D1D5DB")
PDF_HERO_RED = colors.black
PDF_TEXT_DARK = colors.black
PDF_TEXT_MUTED = colors.HexColor("#4B5563")
PDF_TABLE_HEADER = colors.HexColor("#F3F4F6")
PDF_ROW_ALT = colors.HexColor("#FAFAFA")



def draw_pdf_reference_outer_look(c, w, h, title, subtitle="", right_line1="", right_line2=""):
    """
    Reference-photo style report look:
    white document, top-right Hero text, thin outer frame and footer.
    """
    c.setFillColor(colors.white)
    c.rect(0, 0, w, h, fill=True, stroke=False)

    c.setFillColor(colors.HexColor("#DC2626"))
    c.setFont("Helvetica-Bold", 27)
    c.drawRightString(w - 54, h - 44, "Hero")

    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(54, h - 82, str(title))

    c.setFillColor(colors.HexColor("#4B5563"))
    c.setFont("Helvetica", 8)
    if subtitle:
        c.drawString(54, h - 96, str(subtitle))

    if right_line1:
        c.drawRightString(w - 54, h - 82, str(right_line1))
    if right_line2:
        c.drawRightString(w - 54, h - 96, str(right_line2))

    c.setStrokeColor(colors.HexColor("#6B7280"))
    c.setLineWidth(0.7)
    c.rect(42, 78, w - 84, h - 185, fill=False, stroke=True)

    c.setFillColor(colors.HexColor("#DC2626"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(42, 48, "Selva Motors")

    c.setFillColor(colors.black)
    c.setFont("Helvetica", 7.2)
    c.drawString(42, 36, "Katchanam Main Road, Kilvelur | Professional Service ERP")
    c.drawString(42, 25, "Generated by Selva Motors ERP")

    c.setStrokeColor(colors.HexColor("#D1D5DB"))
    c.setLineWidth(0.5)
    c.line(42, 66, w - 42, 66)


def set_pdf_reference_table_header(c, x, y, width, height=20):
    c.setFillColor(colors.HexColor("#F9FAFB"))
    c.rect(x, y, width, height, fill=True, stroke=False)
    c.setStrokeColor(colors.HexColor("#6B7280"))
    c.setLineWidth(0.6)
    c.rect(x, y, width, height, fill=False, stroke=True)
    c.setFillColor(colors.black)



def draw_pdf_light_hero_header(c, w, h, title, subtitle="", right_line1="", right_line2=""):
    """
    Black & white print-friendly PDF header.
    No colour block. White background. HERO text neat size.
    """
    # White header area with only thin border line
    c.setFillColor(colors.white)
    c.rect(0, h - 105, w, 105, fill=True, stroke=False)

    c.setStrokeColor(PDF_LIGHT_HEADER_STROKE)
    c.setLineWidth(0.7)
    c.line(36, h - 96, w - 36, h - 96)
    c.line(36, h - 25, w - 36, h - 25)

    # HERO text logo - neat, not over-big, print friendly
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(42, h - 52, "HERO")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(42, h - 72, "SELVA MOTORS")

    c.setFillColor(PDF_TEXT_MUTED)
    c.setFont("Helvetica", 8)
    c.drawString(42, h - 86, "Professional Service ERP")

    # Report title
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 13)
    c.drawRightString(w - 42, h - 52, str(title))

    c.setFillColor(PDF_TEXT_MUTED)
    c.setFont("Helvetica", 8.5)
    if subtitle:
        c.drawRightString(w - 42, h - 67, str(subtitle))
    if right_line1:
        c.drawRightString(w - 42, h - 81, str(right_line1))
    if right_line2:
        c.drawRightString(w - 42, h - 93, str(right_line2))


def set_pdf_light_table_header(c, x, y, width, height=20):
    """
    Black & white print-friendly table header.
    Light grey only, no dark colour block.
    """
    c.setFillColor(PDF_TABLE_HEADER)
    c.rect(x, y, width, height, fill=True, stroke=False)
    c.setStrokeColor(PDF_LIGHT_HEADER_STROKE)
    c.setLineWidth(0.5)
    c.rect(x, y, width, height, fill=False, stroke=True)
    c.setFillColor(colors.black)



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
            ("BACKGROUND", (0, 0), (-1, 0), PDF_TABLE_HEADER),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 8)]))
        elements.append(s_table)
        elements.append(Spacer(1, 14))

        detail_cols = [
            "Technician Name", "Date", "Job Card Number", "Registration Number",
            "Bike Model", "Service Type", "Labour Amount", "Total Amount", "Entry Type", "Status"
        ]
        show_cols = [c for c in detail_cols if c in df.columns]
        details = df[show_cols].copy().astype(str)

        elements.append(Paragraph("<b>Entry Details</b>", styles["Heading2"]))
        d_table = Table([details.columns.tolist()] + details.values.tolist(), repeatRows=1)
        d_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PDF_TABLE_HEADER),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
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


def generate_manual_bill_pdf(customer_name, reg_no, bike_model, spare_rows, labour_amount, service_type):
    bill_id = "MB-" + app_now().strftime("%Y%m%d%I%M%S%p")
    pdf_path = PDF_DIR / f"{bill_id}.pdf"

    technician_name = st.session_state.get("manual_bill_selected_technician", st.session_state.get("employee_name", ""))
    service_type = st.session_state.get("manual_bill_service_type", "")

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
    c.setFillColor(PDF_TEXT_DARK)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(38, y, "Spare Parts Details")
    y -= 20

    # Table header
    table_x = 38
    table_w = w - 76
    c.setFillColor(PDF_TEXT_DARK)
    c.roundRect(table_x, y - 6, table_w, 22, 7, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 8)

    col_x = [48, 92, 330, 390, 465]
    headers = ["S.No", "Spare Name", "Qty", "Rate", "Amount"]
    for head, x in zip(headers, col_x):
        c.drawString(x, y, head)

    y -= 24
    c.setFont("Helvetica", 8)
    c.setFillColor(PDF_TEXT_DARK)

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
            c.setFillColor(PDF_ROW_ALT)
            c.roundRect(table_x, y - 6, table_w, 17, 4, fill=True, stroke=False)
            c.setFillColor(PDF_TEXT_DARK)

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

    c.setFillColor(PDF_TEXT_DARK)
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
    c.setFillColor(PDF_TEXT_DARK)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(160, 105, "Customer Signature")
    c.setStrokeColor(PDF_TEXT_DARK)
    c.line(145, 88, 305, 88)
    c.setFillColor(colors.HexColor("#64748B"))
    c.setFont("Helvetica", 8)
    c.drawString(170, 73, "Customer Acknowledgement")

    # Signature
    c.setFillColor(PDF_TEXT_DARK)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(385, 105, "For SELVA MOTORS")
    c.setStrokeColor(PDF_TEXT_DARK)
    c.line(365, 88, 525, 88)
    c.setFillColor(colors.HexColor("#64748B"))
    c.setFont("Helvetica", 8)
    c.drawString(392, 73, "Authorised Signatory")

    draw_pdf_footer(c, w, page_no)
    c.save()

    append_row("manual_invoices", {
        "Manual Bill ID": bill_id,
        "Date": today_str(),
        "Technician Name": technician_name,
        "User ID": st.session_state.get("user_id", ""),
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

    return str(pdf_path)


# ============================================================
# LOGIN
# ============================================================
def page_login():
    logo_b64 = get_hero_logo_base64()
    logo_html = f'<img class="hero-login-logo-img" src="data:image/jpeg;base64,{logo_b64}" />' if logo_b64 else '<div style="font-size:42px;text-align:center;font-weight:900;color:#e31837;">HERO</div>'

    st.markdown(f"""
    <div class="login-wrap">
        <div class="login-hero">
            <div class="hero-login-panel">
                {logo_html}
                <div class="hero-connect-title">Hero Connect</div>
                <div class="hero-login-status-badge">SELVA MOTORS ERP • SECURE ACCESS</div>
                <div class="feature-strip" style="justify-content:center;margin-bottom:18px;">
                    <div class="feature-pill">Excel Storage</div>
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


def menu_page():
    sidebar_logo_b64 = get_hero_logo_base64()
    sidebar_logo_html = f'<img src="data:image/jpeg;base64,{sidebar_logo_b64}" style="width:150px;max-width:100%;background:#fff;border-radius:18px;padding:8px;box-shadow:0 16px 32px rgba(227,24,55,.22);" />' if sidebar_logo_b64 else '<div style="font-size:28px;font-weight:900;color:#fff;">HERO</div>'
    st.sidebar.markdown(f"""
    <div style="padding:12px 4px 10px 4px;text-align:center;">
        {sidebar_logo_html}
        <div style="font-size:27px;font-weight:900;color:#fff;line-height:1;margin-top:13px;">HERO CONNECT</div>
        <div style="font-size:12px;font-weight:900;letter-spacing:3px;color:#fb7185;">SELVA MOTORS ERP</div>
        <div style="height:1px;background:rgba(255,255,255,.12);margin:15px 0;"></div>
    </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown(
        f"""
        <div style="background:rgba(255,255,255,.075);border:1px solid rgba(255,255,255,.10);
        padding:14px;border-radius:20px;margin-bottom:12px;">
            <div style="font-size:13px;color:#94a3b8;font-weight:800;">Logged in as</div>
            <div style="font-size:17px;font-weight:900;color:#fff;">{st.session_state.get('employee_name')}</div>
            <div style="display:inline-block;margin-top:7px;padding:5px 10px;border-radius:999px;
            background:rgba(34,197,94,.14);color:#bbf7d0;font-size:12px;font-weight:900;">
            {st.session_state.get('role')}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    if is_admin():
        pages = [
            "Dashboard", "Reports", "Search",
            "Customer Service History", "Admin Panel"
        ]
    elif is_manager():
        pages = [
            "Dashboard", "Attendance", "Upload Invoice", "Reports", "Search",
            "Customer Service History", "Manual Invoice Generator", "Duplicate Upload Finder"
        ]
    elif is_technician():
        pages = [
            "Dashboard", "Attendance", "Upload Invoice",
            "Customer Service History",
            "Delete Invoice Request"
        ]
    elif is_prathisha():
        pages = ["Dashboard", "Attendance"]
    else:
        pages = ["Dashboard"]

    icons = {
        "Dashboard": "📊",
        "Attendance": "📍",
        "Upload Invoice": "📄",
        "Reports": "📑",
        "Search": "🔍",
        "Customer Service History": "🧾",
        "Manual Invoice Generator": "🧾",
        "Admin Panel": "⚙️",
        "Duplicate Upload Finder": "🔁",
        "Delete Invoice Request": "🗑️",
    }
    labels = [f"{icons.get(p, '•')} {p}" for p in pages]
    selected_label = st.sidebar.radio("Menu", labels, label_visibility="collapsed")
    selected_page = selected_label.split(" ", 1)[1]

    st.sidebar.markdown("""
    <div style="margin-top:18px;padding:16px;border-radius:22px;background:rgba(34,197,94,.10);
    border:1px solid rgba(34,197,94,.22);">
        <div style="font-weight:900;color:#fff;">Hero Service Style</div>
        <div style="font-size:12px;color:#cbd5e1;margin-top:4px;">Fast entry • Clean reports • Smart approval</div>
    </div>
    """, unsafe_allow_html=True)

    return selected_page

def metric_card(title, value, caption=""):
    st.markdown(f"""
    <div class="metric-card">
        <p>{title}</p>
        <h2>{value}</h2>
        <small>{caption}</small>
    </div>
    """, unsafe_allow_html=True)



# ============================================================
# HERO EXTREME UI HELPERS
# ============================================================
def hero_badge(text):
    return f"<span class='status-chip'>⚡ {text}</span>" if text else ""


def page_hero(title, subtitle, chip=""):
    st.markdown(f"""
    <div class="hero-panel">
        {hero_badge(chip)}
        <h1>{title}</h1>
        <p>{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)


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
    Unified professional PDF header for Manual Bill and Daily Technician Report.
    Correct SELVA MOTORS placement + circular Hero logo.
    """
    # Top red/black gradient-like blocks
    c.setFillColor(colors.HexColor("#111827"))
    c.rect(0, h - 112, w, 112, fill=True, stroke=False)
    c.setFillColor(colors.HexColor("#E31837"))
    c.rect(0, h - 112, 14, 112, fill=True, stroke=False)
    c.setFillColor(colors.HexColor("#7F0016"))
    c.rect(w - 135, h - 112, 135, 112, fill=True, stroke=False)

    # Circle logo
    logo_path = make_circle_hero_logo_for_pdf()
    if logo_path:
        c.drawImage(logo_path, 32, h - 98, width=68, height=68, mask="auto")
    else:
        c.setFillColor(colors.white)
        c.circle(66, h - 64, 34, fill=True, stroke=False)
        c.setFillColor(colors.HexColor("#E31837"))
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(66, h - 69, "HERO")

    # Company block - single clean placement
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(115, h - 45, "SELVA MOTORS")

    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#E5E7EB"))
    c.drawString(115, h - 61, "KATCHANAM MAIN ROAD, KILVELUR")
    c.drawString(115, h - 76, subtitle or "Authorised Hero Service Document")

    # Title right side
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 15)
    c.drawRightString(w - 36, h - 42, title)
    c.setFont("Helvetica", 8)
    if right_line1:
        c.drawRightString(w - 36, h - 60, right_line1)
    if right_line2:
        c.drawRightString(w - 36, h - 76, right_line2)

    # Divider
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
def page_dashboard():
    page_hero("Service Control Dashboard", "Role-based Selva Motors ERP command center with clean revenue, service entries and approvals.", st.session_state.get("role", ""))

    invoices_for_alert = read_sheet("invoices")
    delete_for_alert = read_sheet("delete_requests")
    pending_delete_count = 0
    if not delete_for_alert.empty and "Request Status" in delete_for_alert.columns:
        pending_delete_count = len(delete_for_alert[delete_for_alert["Request Status"].astype(str) == "Pending"])
    today_count = 0
    if not invoices_for_alert.empty and "Date" in invoices_for_alert.columns:
        today_count = len(invoices_for_alert[invoices_for_alert["Date"].astype(str) == today_str()])

    st.markdown("<div class='theme-note'><b>Pro ERP Notification Center</b><br>Live service alerts, today entries and approval status.</div>", unsafe_allow_html=True)
    pro_alert_bar([
        ("Today Vehicles", str(today_count)),
        ("Pending Delete Requests", str(pending_delete_count)),
        ("Google Sync", "3 min auto sync"),
        ("Storage", "Cloud Excel")
    ])

    if is_technician():
        quick_action_grid([
            ("Mark Attendance", "GPS auto attendance", "📍"),
            ("Upload Invoice", "OCR upload and preview", "📄"),
            ("Today Entries", "View your entries", "🧾"),
            ("Delete Request", "Request admin approval", "🗑️")
        ])

    service_timeline()


    optimal_v4_note("Optimal V4 Role Access", "Role-wise pages are kept clean. Mobile view has larger buttons and compact layout.")
    invoices = read_sheet("invoices")
    attendance = read_sheet("attendance")
    delete_req = read_sheet("delete_requests")

    invoices["Total Amount"] = pd.to_numeric(invoices["Total Amount"], errors="coerce").fillna(0)
    invoices["Labour Amount"] = pd.to_numeric(invoices["Labour Amount"], errors="coerce").fillna(0)

    today = today_str()
    user_id = st.session_state.get("user_id", "")

    if is_technician():
        view_df = invoices[
            (invoices["User ID"].astype(str) == user_id) &
            (invoices["Date"].astype(str) == today)
        ]
        pending_req = delete_req[
            (delete_req["User ID"].astype(str) == user_id) &
            (delete_req["Request Status"].astype(str) == "Pending")
        ]

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            metric_card("Today Revenue", f"₹{view_df['Total Amount'].sum():,.0f}", "Your entries only")
        with c2:
            metric_card("Vehicle Entries", len(view_df), "Today completed")
        with c3:
            metric_card("Labour Amount", f"₹{view_df['Labour Amount'].sum():,.0f}", "Today labour")
        with c4:
            metric_card("Delete Requests", len(pending_req), "Pending approval")

        st.markdown("<div class='section-title'>Technician Quick Actions</div>", unsafe_allow_html=True)
        m1, m2, m3 = st.columns(3)
        with m1:
            mobile_action_card("Upload Invoice", "OCR + Service Type + Excel save", "📄")
        with m2:
            mobile_action_card("Manual Bill", "PDF + Excel manual_invoices save", "🧾")
        with m3:
            mobile_action_card("Delete Request", "Admin approval workflow", "🗑️")
        q1, q2, q3 = st.columns(3)
        with q1:
            quick_card("Upload Invoice", "OCR upload and view-only preview before entry.", "📄")
        with q2:
            quick_card("Manual Bill", "Generate Professional bill with technician name.", "🧾")
        with q3:
            quick_card("Delete Request", "Request Admin approval for invoice deletion.", "🗑️")

        st.markdown("<div class='section-title'>My Today Entries</div>", unsafe_allow_html=True)
        st.dataframe(view_df, use_container_width=True)
        return

    if is_prathisha():
        today_att = attendance[attendance["Date"].astype(str) == today]
        c1, c2, c3 = st.columns(3)
        with c1:
            metric_card("Today Attendance", len(today_att), "System staff view")
        with c2:
            metric_card("Role Access", "Limited", "Attendance only")
        with c3:
            metric_card("Storage", "Excel", "Secure local sheet")

        st.markdown("<div class='section-title'>Today Attendance List</div>", unsafe_allow_html=True)
        st.dataframe(today_att, use_container_width=True)
        return

    if is_admin():
        month_key = app_now().strftime("%m-%Y")
        temp = invoices.copy()
        temp["Month"] = pd.to_datetime(temp["Date"], format="%d-%m-%Y", errors="coerce").dt.strftime("%m-%Y")
        month_df = temp[temp["Month"] == month_key]
        today_df = invoices[invoices["Date"].astype(str) == today]
        pending_req = delete_req[delete_req["Request Status"].astype(str) == "Pending"]

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            metric_card("Monthly Revenue", f"₹{month_df['Total Amount'].sum():,.0f}", "Admin only")
        with c2:
            metric_card("Today Revenue", f"₹{today_df['Total Amount'].sum():,.0f}", "All technicians")
        with c3:
            metric_card("Today Entries", len(today_df), "All vehicles")
        with c4:
            metric_card("Delete Requests", len(pending_req), "Need action")

        st.markdown("<div class='section-title'>Admin Command Shortcuts</div>", unsafe_allow_html=True)
        q1, q2, q3 = st.columns(3)
        with q1:
            quick_card("Reports", "Generate all or particular technician PDF report.", "📑")
        with q2:
            quick_card("Approvals", "Approve or reject technician delete requests.", "✅")
        with q3:
            quick_card("Employee Control", "Add or update employees from Admin Panel.", "👥")

        st.markdown("<div class='section-title'>Technician-wise Revenue</div>", unsafe_allow_html=True)
        if not invoices.empty:
            tech = invoices.groupby("Technician Name", dropna=False)["Total Amount"].sum().reset_index()
            st.dataframe(tech, use_container_width=True)

        st.markdown("<div class='section-title'>Recent Service Entries</div>", unsafe_allow_html=True)
        st.dataframe(invoices.tail(20), use_container_width=True)
        return

    if is_manager():
        today_df = invoices[invoices["Date"].astype(str) == today]
        c1, c2, c3 = st.columns(3)
        with c1:
            metric_card("Today Revenue", f"₹{today_df['Total Amount'].sum():,.0f}", "Manager view")
        with c2:
            metric_card("Today Entries", len(today_df), "All technicians")
        with c3:
            metric_card("Edit Access", "Protected", "Password required")

        st.markdown("<div class='section-title'>Manager Quick Actions</div>", unsafe_allow_html=True)
        q1, q2, q3 = st.columns(3)
        with q1:
            quick_card("Reports", "View all or particular technician entries.", "📑")
        with q2:
            quick_card("Update status with password protection.", "✏️")
        with q3:
            quick_card("Customer History", "Search service history by registration.", "🔍")

        st.markdown("<div class='section-title'>Today Entries</div>", unsafe_allow_html=True)
        st.dataframe(today_df, use_container_width=True)



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
def page_attendance():
    st.caption("Attendance time: India Time • 12-hour AM/PM format")
    page_hero("Smart Attendance", "GPS auto attendance only. Inside company radius irundha automatic mark aagum.", "Auto GPS")

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

    st.markdown("<div class='section-title'>GPS Auto Attendance</div>", unsafe_allow_html=True)

    st.info("Browser location permission Allow pannunga. Manual location and selfie removed.")

    if get_geolocation is None:
        st.error("GPS component not available. requirements.txt la streamlit-js-eval irukkanum.")
        st.code("pip install streamlit-js-eval")
        return

    loc = get_geolocation()

    if not loc:
        gps_refresh_box()
        return

    lat, lon, accuracy = extract_gps_from_browser_location(loc)

    if lat is None or lon is None:
        gps_refresh_box()
        with st.expander("Browser location response"):
            st.write(loc)
        return

    dist = distance_meter(lat, lon, COMPANY_LAT, COMPANY_LON)
    bearing = bearing_to_company(lat, lon)
    direction = compass_direction(bearing)
    hint = direction_hint(direction)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Your Latitude", f"{lat:.6f}")
    c2.metric("Your Longitude", f"{lon:.6f}")
    c3.metric("Distance", format_distance_km(dist))
    c4.metric("Direction", direction)

    if accuracy:
        st.caption(f"GPS Accuracy: {accuracy} meter approx.")

    if dist <= ALLOWED_RADIUS_METER:
        ok, saved_dist = auto_save_attendance_from_gps(lat, lon)
        if ok:
            st.success(f"Attendance auto-marked successfully. Distance: {format_distance_km(saved_dist)}.")
            st.rerun()
        else:
            st.error("Attendance auto-save failed.")
    else:
        st.error("You are outside company location radius. Attendance not marked.")
        attendance_map_card(lat, lon, dist, direction, hint, show_embed=True)
        st.markdown(f"""
        <div class="glow-card">
            <h3 style="margin:0;color:#991b1b;">Direction Guide</h3>
            <p style="margin:8px 0 0 0;color:#334155;">
                Company location is approximately <b>{format_distance_km(dist)}</b> away.
                Move towards <b>{direction}</b>. {hint}
            </p>
        </div>
        """, unsafe_allow_html=True)


# ============================================================
# UPLOAD INVOICE
# ============================================================
def page_upload_invoice():
    page_hero("AI Invoice OCR Upload", "Upload invoice, verify clean view-only preview, then proceed the entry.", "OCR")
    ocr_stepper("Upload")
    st.caption("OCR Preview is view-only. Duplicate blocking removed. Manager can find/delete duplicates later.")

    st.markdown("<div class='service-type-panel'><b>Service Type Required</b><br><span style='color:#64748b;font-size:13px;'>Upload invoice entry-ku service type select pannunga. This will save in Excel and show in PDF reports.</span></div>", unsafe_allow_html=True)
    upload_service_type = st.selectbox("Service Type", ["FSC", "Paid Service", "General", "Joyride", "Accident", "ON SALE"], key="upload_service_type")

    uploaded = st.file_uploader("Upload Invoice PDF / Image", type=["pdf", "jpg", "jpeg", "png", "webp"], key="invoice_uploader")

    if uploaded:
        file_path = save_uploaded_file(uploaded)
        text = extract_invoice_text(file_path)

        # Source file should not be kept after OCR parse
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
    data["Registration Number"] = reg_no_or_fr(data.get("Registration Number", ""))
    data["Service Type"] = upload_service_type
    st.session_state["ocr_preview"] = data

    ocr_stepper("Preview")
    st.markdown("<div class='section-title'>View Only OCR Preview</div>", unsafe_allow_html=True)

    dup_text = "Duplicate Check Pending"
    dup_badge = status_badge("Ready", "green")
    if duplicate_exists(data.get("Invoice Number", "")):
        dup_text = "Duplicate invoice/job card exists"
        dup_badge = status_badge("Duplicate", "red")

    st.markdown(f"""
    <div class="invoice-preview-pro">
        <div class="invoice-preview-head">
            <h2>OCR Entry Preview {dup_badge}</h2>
            <p>View-only clean data. Spare item names and oil item names are hidden. Excel save happens only after proceed / Admin approval.</p>
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
        "Registration Number": reg_no_or_fr(data.get("Registration Number", "")),
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
    for col in ["Job Card Number", "Bike Model"]:
        if not str(data.get(col, "")).strip():
            missing.append(col)

    if missing:
        st.warning("Missing detected values: " + ", ".join(missing))
        st.info("Preview is view-only as per requirement. Upload a clearer invoice if values are missing.")

    job_card_clean = normalize_invoice_jobcard_no(data.get("Job Card Number", ""))
    duplicate = False

    st.caption("Excel Job Card Check: App checks existing invoices sheet first. Duplicate shows only if same full Job Card Number already exists.")

    if False and duplicate:
        st.markdown(f"""
        <div class="approve-box">
            <h3 style="margin:0;color:#991b1b;">Duplicate Job Card Detected</h3>
            <p style="margin:8px 0 0 0;color:#334155;">
                Same Job Card Number already exists in Excel: <b>{job_card_clean}</b><br>
                This entry will not be saved directly. Admin approval request will be created.
            </p>
        </div>
        """, unsafe_allow_html=True)


    if st.button("Click to Proceed the Entry", use_container_width=True):
        if missing:
            st.error("Required values missing. Cannot proceed.")
            return

        with st.spinner("Please wait... Entry processing. Do not upload another file."):
            final_job_card_no = normalize_invoice_jobcard_no(data.get("Job Card Number", ""))
            final_duplicate = False

            if final_duplicate:
                request_id = create_pending_invoice_request(data)
                processing_wait_3s("Please wait, Excel entry processing")
                st.session_state.pop("ocr_preview", None)
                st.warning(f"Duplicate detected. Admin approval request sent. Request ID: {request_id}")
                st.info("Invoice will be stored in Excel only after Admin approves.")
                st.rerun()
            else:
                save_invoice_entry_from_data(data, entry_type="OCR Upload")
                processing_wait_3s("Please wait, Excel entry processing")
                st.session_state.pop("ocr_preview", None)
                st.success("Entry saved to Excel. Upload preview cleared.")
                st.rerun()


# ============================================================
# REPORTS
# ============================================================
def page_reports():
    page_hero("Reports", "Professional report center for service entries, daily technician report and attendance report.", "Report Center")
    report_center_header()

    invoices = read_sheet("invoices")
    attendance_df = read_sheet("attendance")

    if "Total Amount" in invoices.columns:
        invoices["Total Amount"] = pd.to_numeric(invoices["Total Amount"], errors="coerce").fillna(0)
    else:
        invoices["Total Amount"] = 0

    if "Labour Amount" in invoices.columns:
        invoices["Labour Amount"] = pd.to_numeric(invoices["Labour Amount"], errors="coerce").fillna(0)
    else:
        invoices["Labour Amount"] = 0

    tabs = st.tabs(["📑 Service Reports", "🏍️ Daily Technician Report", "📍 Monthly Attendance Report"])

    with tabs[0]:
        report_control_panel("Service Report Control", "All technicians or particular technician select pannitu service report generate pannalam.")

        if invoices.empty:
            st.info("No invoice entries found.")
        else:
            service_df = invoices.copy()

            if is_technician():
                service_df = service_df[
                    (service_df["User ID"].astype(str) == st.session_state.get("user_id", "")) &
                    (service_df["Date"].astype(str) == today_str())
                ]
                st.info("Technician view: only today’s own entries are shown.")
                selected_view = "My Today Entries"
            else:
                selected_view = st.radio("Report View Type", ["All Technicians", "Particular Technician"], horizontal=True, key="service_report_view_type")
                if selected_view == "Particular Technician":
                    tech_names = sorted([x for x in service_df["Technician Name"].astype(str).unique().tolist() if x.strip()])
                    selected_tech = st.selectbox("Select Technician", tech_names, key="service_report_tech")
                    service_df = service_df[service_df["Technician Name"].astype(str) == selected_tech]

                c1, c2, c3 = st.columns(3)
                with c1:
                    date_filter = st.text_input("Date Filter DD-MM-YYYY", value="", key="service_report_date")
                with c2:
                    reg_filter = st.text_input("Registration Number Filter", value="", key="service_report_reg")
                with c3:
                    service_type_filter = st.selectbox("Service Type Filter", ["All", "FSC", "Paid Service", "General", "Joyride", "Accident"], key="service_report_type")

                if date_filter.strip():
                    service_df = service_df[service_df["Date"].astype(str) == date_filter.strip()]
                if reg_filter.strip():
                    reg_clean = clean_reg_no(reg_filter)
                    service_df = service_df[service_df["Registration Number"].astype(str).str.upper() == reg_clean]
                if service_type_filter != "All" and "Service Type" in service_df.columns:
                    service_df = service_df[service_df["Service Type"].astype(str) == service_type_filter]

            total_entries = len(service_df)
            total_revenue = service_df["Total Amount"].sum() if "Total Amount" in service_df.columns else 0
            total_labour = service_df["Labour Amount"].sum() if "Labour Amount" in service_df.columns else 0
            total_spare = pd.to_numeric(service_df.get("Spare Amount", pd.Series([])), errors="coerce").fillna(0).sum() if not service_df.empty else 0

            report_summary_cards([
                ("Vehicle Entries", total_entries, "Selected report"),
                ("Total Revenue", f"₹{total_revenue:,.0f}", "Service entries"),
                ("Labour Amount", f"₹{total_labour:,.0f}", "Labour total"),
                ("Spare Amount", f"₹{total_spare:,.0f}", "Genuine parts total"),
            ])

            show_cols = ["Technician Name", "Date", "Job Card Number", "Registration Number", "Bike Model", "Service Type", "Spare Amount", "Labour Amount", "Total Amount", "Entry Type", "Status"]
            existing_show_cols = [c for c in show_cols if c in service_df.columns]
            st.dataframe(service_df[existing_show_cols] if existing_show_cols else service_df, use_container_width=True)

            if st.button("Generate Service PDF Report", use_container_width=True, key="generate_service_pdf_report"):
                pdf = generate_report_pdf(service_df, f"Selva Motors Service Report - {selected_view}", "selva_motors_service_report.pdf")
                st.session_state["generated_report_pdf"] = pdf
                st.success("Service PDF report generated.")

            if st.session_state.get("generated_report_pdf"):
                pdf_path = st.session_state["generated_report_pdf"]
                if Path(pdf_path).exists():
                    with open(pdf_path, "rb") as f:
                        st.download_button("Download Service PDF Report", f, file_name=Path(pdf_path).name, mime="application/pdf", use_container_width=True, key="download_service_pdf_report")

    with tabs[1]:
        report_control_panel("Daily Technician Report", "Daily report-ku date and technician select pannunga. Total Amount hide; Total Labour Amount mattum PDF-la show aagum.")

        daily_df_base = invoices.copy()
        if is_technician():
            report_date = today_str()
            selected_daily_tech = st.session_state.get("employee_name", "")
            daily_df = daily_df_base[
                (daily_df_base["Date"].astype(str) == report_date) &
                (daily_df_base["User ID"].astype(str) == st.session_state.get("user_id", ""))
            ]
            st.info("Technician view: today own daily report only.")
        else:
            c1, c2, c3 = st.columns(3)
            with c1:
                report_date = st.text_input("Daily Report Date DD-MM-YYYY", value=today_str(), key="daily_report_date")
            daily_df = daily_df_base[daily_df_base["Date"].astype(str) == report_date]

            tech_options = ["All Technicians"]
            if not daily_df.empty and "Technician Name" in daily_df.columns:
                tech_options += sorted([x for x in daily_df["Technician Name"].astype(str).unique().tolist() if x.strip()])
            with c2:
                selected_daily_tech = st.selectbox("Select Technician", tech_options, key="daily_report_tech")
            with c3:
                daily_service_type = st.selectbox("Service Type", ["All", "FSC", "Paid Service", "General", "Joyride", "Accident"], key="daily_report_service_type")

            if selected_daily_tech != "All Technicians":
                daily_df = daily_df[daily_df["Technician Name"].astype(str) == selected_daily_tech]
            if daily_service_type != "All" and "Service Type" in daily_df.columns:
                daily_df = daily_df[daily_df["Service Type"].astype(str) == daily_service_type]

        daily_entries = len(daily_df)
        daily_labour = pd.to_numeric(daily_df.get("Labour Amount", pd.Series([])), errors="coerce").fillna(0).sum() if not daily_df.empty else 0
        daily_spare = pd.to_numeric(daily_df.get("Spare Amount", pd.Series([])), errors="coerce").fillna(0).sum() if not daily_df.empty else 0

        report_summary_cards([
            ("Daily Entries", daily_entries, "Selected date"),
            ("Total Labour Amount", f"₹{daily_labour:,.0f}", "PDF shows this"),
            ("Spare Amount", f"₹{daily_spare:,.0f}", "Preview only"),
            ("Technician", selected_daily_tech, "Selected view"),
        ])

        daily_show_cols = ["Technician Name", "Date", "Job Card Number", "Registration Number", "Bike Model", "Service Type", "Labour Amount", "Status"]
        daily_existing_cols = [c for c in daily_show_cols if c in daily_df.columns]
        st.dataframe(daily_df[daily_existing_cols] if daily_existing_cols else daily_df, use_container_width=True)

        if st.button("Generate Daily Technician Report PDF", use_container_width=True, key="generate_daily_tech_report"):
            daily_pdf = generate_daily_technician_report_pdf(daily_df, report_date, selected_daily_tech)
            st.session_state["daily_technician_report_pdf"] = daily_pdf
            st.success("Daily technician service report PDF generated.")

        if st.session_state.get("daily_technician_report_pdf"):
            daily_pdf_path = st.session_state["daily_technician_report_pdf"]
            if Path(daily_pdf_path).exists():
                with open(daily_pdf_path, "rb") as f:
                    st.download_button("Download Daily Technician Service Report PDF", f, file_name=Path(daily_pdf_path).name, mime="application/pdf", use_container_width=True, key="download_daily_tech_report")

    with tabs[2]:
        report_control_panel("Monthly Attendance Report", "Today attendance report removed. Month-wise attendance report mattum generate pannalam.")

        if attendance_df.empty:
            st.info("No attendance entries found.")
        else:
            att_df = attendance_df.copy()

            st.markdown("""
            <div class="monthly-att-panel">
                <h3>📍 Monthly Attendance Control</h3>
                <p>Month select pannunga. All users or particular user monthly attendance report PDF download pannalam.</p>
            </div>
            """, unsafe_allow_html=True)

            if is_technician() or is_prathisha():
                selected_att_user = st.session_state.get("employee_name", "")
                att_df = att_df[att_df["User ID"].astype(str) == st.session_state.get("user_id", "")]
                st.info("User view: your own monthly attendance only.")
            else:
                att_view_type = st.radio(
                    "Monthly Attendance View Type",
                    ["All Users", "Particular User"],
                    horizontal=True,
                    key="monthly_attendance_view_type"
                )

                selected_att_user = "All Users"
                if att_view_type == "Particular User":
                    users = sorted([x for x in att_df["Technician Name"].astype(str).unique().tolist() if x.strip()])
                    selected_att_user = st.selectbox("Select User", users, key="monthly_attendance_user")
                    att_df = att_df[att_df["Technician Name"].astype(str) == selected_att_user]

            current_month = app_now().strftime("%m-%Y")
            month_key = st.text_input("Month Filter MM-YYYY", value=current_month, key="monthly_attendance_month")

            if month_key and "Date" in att_df.columns:
                att_dates = pd.to_datetime(att_df["Date"], format="%d-%m-%Y", errors="coerce")
                att_df = att_df[att_dates.dt.strftime("%m-%Y") == month_key]

            att_status_filter = st.selectbox("Attendance Status", ["All", "Present", "Absent", "Half Day"], key="monthly_attendance_status")
            if att_status_filter != "All" and "Attendance Status" in att_df.columns:
                att_df = att_df[att_df["Attendance Status"].astype(str) == att_status_filter]

            present_count = len(att_df[att_df["Attendance Status"].astype(str).str.lower() == "present"]) if "Attendance Status" in att_df.columns else 0
            report_summary_cards([
                ("Monthly Rows", len(att_df), "Selected month"),
                ("Present Count", present_count, "GPS marked"),
                ("Selected User", selected_att_user, "Monthly view"),
                ("Month", month_key, "Report month"),
            ])

            att_cols = ["Date", "Time", "User ID", "Technician Name", "Role", "Attendance Status", "Distance Meter", "Selfie Saved"]
            att_existing_cols = [c for c in att_cols if c in att_df.columns]
            st.dataframe(att_df[att_existing_cols] if att_existing_cols else att_df, use_container_width=True)

            if st.button("Generate Monthly Attendance PDF Report", use_container_width=True, key="generate_monthly_attendance_pdf_report"):
                att_pdf = generate_monthly_attendance_report_pdf(att_df, month_key, selected_att_user)
                st.session_state["monthly_attendance_report_pdf"] = att_pdf
                st.success("Monthly Attendance PDF report generated.")

            if st.session_state.get("monthly_attendance_report_pdf"):
                att_pdf_path = st.session_state["monthly_attendance_report_pdf"]
                if Path(att_pdf_path).exists():
                    with open(att_pdf_path, "rb") as f:
                        st.download_button(
                            "Download Monthly Attendance PDF Report",
                            f,
                            file_name=Path(att_pdf_path).name,
                            mime="application/pdf",
                            use_container_width=True,
                            key="download_monthly_attendance_pdf_report"
                        )


# ============================================================
# SEARCH
# ============================================================
def page_search():
    page_hero("Smart Search", "Search invoice entries by registration number, invoice number or technician.", "Search")

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
        "Spare Parts Count", "Oil Change Status", "Total Amount",
        "Entry Type", "Status"
    ]
    existing_cols = [c for c in safe_cols if c in result.columns]
    if existing_cols:
        st.dataframe(result[existing_cols], use_container_width=True)
    else:
        st.dataframe(result, use_container_width=True)


# ============================================================
# CUSTOMER SERVICE HISTORY
# ============================================================
def page_customer_service_history():
    page_hero("Customer Service History", "Today service entries and registration-number based history search.", "History")

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

    st.markdown("<div class='section-title'>Today’s Service Entry History</div>", unsafe_allow_html=True)
    st.dataframe(today_entries, use_container_width=True)

    st.markdown("<div class='section-title'>Registration Number Search</div>", unsafe_allow_html=True)
    reg = st.text_input("Enter Registration Number", placeholder="TN51AT6661")
    if reg:
        reg_clean = clean_reg_no(reg)
        result = invoices[invoices["Registration Number"].astype(str).str.upper() == reg_clean]
        st.dataframe(result, use_container_width=True)


# ============================================================
# MANUAL INVOICE GENERATOR
# ============================================================
def page_manual_invoice():
    if not is_manager():
        st.error("Manual Bill is available for Manager only.")
        return
    page_hero("Manual Bill", "Generate professional manual service bill PDF with serial numbered spare rows.", "PDF Bill")
    st.caption("Professional manual bill PDF. Manager can select technician / ON SALE.")

    selected_bill_technician = st.selectbox(
        "Select Technician / Sale Type",
        ["Mohan", "Ajay", "Vengadesh", "ON SALE"],
        key="manual_bill_selected_technician_widget"
    )
    st.session_state["manual_bill_selected_technician"] = selected_bill_technician


    c1, c2 = st.columns(2)
    customer_name = c1.text_input("Customer Name")
    reg_no = c2.text_input("Registration Number")
    bike_model = c1.text_input("Bike Model")
    service_type = c2.selectbox("Service Type", ["FSC", "Paid Service", "General", "Joyride", "Accident", "ON SALE"])

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

        pdf = generate_manual_bill_pdf(customer_name, reg_no, bike_model, spare_rows, labour_amount, service_type)
        st.success("Manual Bill PDF generated with zoom Hero logo and saved to Excel manual_invoices sheet.")

        with open(pdf, "rb") as f:
            st.download_button("Download Manual Bill PDF", f, file_name=Path(pdf).name, mime="application/pdf")


# ============================================================
# DELETE INVOICE REQUEST
# ============================================================
def page_delete_invoice_request():
    page_hero("Delete Invoice Request", "Technicians can request deletion; Admin approves or rejects.", "Approval")

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
# ADMIN EXCEL DATA MANAGER
# ============================================================


# ============================================================
# GOOGLE SHEET 3-MIN AUTO SYNC HELPERS
# ============================================================
def is_google_sync_configured():
    return bool(st.secrets.get("SHEET_ID", "")) and ("gcp_service_account" in st.secrets)


def google_sync_state_default():
    return {
        "dirty_sheets": [],
        "last_sync_ts": 0,
        "last_sync_time": "Not yet",
        "last_sync_status": "Not yet",
        "last_sync_message": "",
        "last_change_time": "Not yet"
    }


def load_google_sync_state():
    try:
        if SYNC_STATE_FILE.exists():
            import json
            return json.loads(SYNC_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return google_sync_state_default()


def save_google_sync_state(state):
    try:
        import json
        SYNC_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception:
        pass


def mark_google_sheet_dirty(sheet_name):
    state = load_google_sync_state()
    dirty = set(state.get("dirty_sheets", []))
    dirty.add(sheet_name)
    state["dirty_sheets"] = sorted(list(dirty))
    state["last_change_time"] = app_now().strftime("%d-%m-%Y %I:%M:%S %p")
    save_google_sync_state(state)


def get_google_next_sync_wait_text():
    state = load_google_sync_state()
    dirty_sheets = state.get("dirty_sheets", [])
    if not dirty_sheets:
        return "No pending sync"

    last_sync_ts = float(state.get("last_sync_ts", 0) or 0)
    if last_sync_ts == 0:
        return "Ready to sync now"

    now_ts = app_now().timestamp()
    interval = 3 * 60
    remaining = int(interval - (now_ts - last_sync_ts))
    if remaining <= 0:
        return "Ready to sync now"

    minutes = remaining // 60
    seconds = remaining % 60
    return f"{minutes} min {seconds} sec remaining"


def google_sheet_client_for_sync():
    if gspread is None or Credentials is None:
        return None, "gspread/google-auth missing in requirements.txt"

    if not is_google_sync_configured():
        return None, "SHEET_ID or gcp_service_account missing in Streamlit Secrets"

    try:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=scope
        )
        client = gspread.authorize(creds)
        return client, ""
    except Exception as e:
        return None, str(e)


def get_or_create_google_worksheet(spreadsheet, sheet_name, rows=1000, cols=30):
    try:
        return spreadsheet.worksheet(sheet_name)
    except Exception:
        return spreadsheet.add_worksheet(title=sheet_name, rows=rows, cols=cols)


def sync_one_sheet_to_google(sheet_name):
    client, err = google_sheet_client_for_sync()
    if client is None:
        return False, err

    try:
        spreadsheet = client.open_by_key(st.secrets["SHEET_ID"])
        df = read_sheet(sheet_name).fillna("").astype(str)
        ws = get_or_create_google_worksheet(
            spreadsheet,
            sheet_name,
            rows=max(len(df) + 20, 100),
            cols=max(len(df.columns) + 5, 20)
        )
        ws.clear()
        values = [df.columns.tolist()] + df.values.tolist()
        ws.update(values)
        return True, f"{sheet_name} synced"
    except Exception as e:
        return False, str(e)


def sync_changed_sheets_to_google():
    state = load_google_sync_state()
    dirty_sheets = state.get("dirty_sheets", [])

    if not dirty_sheets:
        return True, "No changed sheets to sync."

    if not is_google_sync_configured():
        return False, "Google Sheet secrets not configured."

    synced = []
    failed = []

    for sheet_name in dirty_sheets:
        ok, msg = sync_one_sheet_to_google(sheet_name)
        if ok:
            synced.append(sheet_name)
        else:
            failed.append(f"{sheet_name}: {msg}")

    now = app_now()
    if failed:
        state["last_sync_status"] = "Failed"
        state["last_sync_message"] = "; ".join(failed)[:500]
        state["last_sync_time"] = now.strftime("%d-%m-%Y %I:%M:%S %p")
        save_google_sync_state(state)
        return False, state["last_sync_message"]

    state["dirty_sheets"] = []
    state["last_sync_ts"] = now.timestamp()
    state["last_sync_time"] = now.strftime("%d-%m-%Y %I:%M:%S %p")
    state["last_sync_status"] = "Success"
    state["last_sync_message"] = "Synced sheets: " + ", ".join(synced)
    save_google_sync_state(state)
    return True, state["last_sync_message"]


def sync_all_excel_to_google():
    if not is_google_sync_configured():
        return False, "Google Sheet secrets not configured."

    synced = []
    failed = []
    for sheet_name in SHEETS.keys():
        ok, msg = sync_one_sheet_to_google(sheet_name)
        if ok:
            synced.append(sheet_name)
        else:
            failed.append(f"{sheet_name}: {msg}")

    state = load_google_sync_state()
    now = app_now()
    if failed:
        state["last_sync_status"] = "Failed"
        state["last_sync_message"] = "; ".join(failed)[:500]
        state["last_sync_time"] = now.strftime("%d-%m-%Y %I:%M:%S %p")
        save_google_sync_state(state)
        return False, state["last_sync_message"]

    state["dirty_sheets"] = []
    state["last_sync_ts"] = now.timestamp()
    state["last_sync_time"] = now.strftime("%d-%m-%Y %I:%M:%S %p")
    state["last_sync_status"] = "Success"
    state["last_sync_message"] = "Full sync: " + ", ".join(synced)
    save_google_sync_state(state)
    return True, state["last_sync_message"]


def auto_sync_google_sheet_3min():
    try:
        state = load_google_sync_state()
        dirty_sheets = state.get("dirty_sheets", [])
        if not dirty_sheets:
            return

        last_sync_ts = float(state.get("last_sync_ts", 0) or 0)
        now_ts = app_now().timestamp()
        interval = 3 * 60

        if last_sync_ts == 0 or now_ts - last_sync_ts >= interval:
            sync_changed_sheets_to_google()
    except Exception:
        pass



def render_cloud_excel_view_only():
    st.markdown("""
    <div class="cloud-view-panel">
        <h3>☁️ Cloud Excel Sheet View Only</h3>
        <p>Admin Panel-kulla view only. Edit/Delete options illa. Google Sheet edit/delete panna Pull Google Sheet → Cloud Excel use pannunga.</p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("Refresh Cloud Excel View", use_container_width=True, key="cloud_view_refresh_admin_tab"):
        st.rerun()

    selected_sheet = st.selectbox("Select Sheet to View", list(SHEETS.keys()), key="cloud_view_sheet_admin_tab")
    try:
        df = read_sheet(selected_sheet).reset_index(drop=True)
    except Exception as e:
        st.error(f"Unable to read sheet: {e}")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Sheet", selected_sheet)
    c2.metric("Rows", len(df))
    c3.metric("Columns", len(df.columns))

    search_text = st.text_input("Search in selected sheet", key="cloud_view_search_admin_tab")
    view_df = df.copy()
    if search_text:
        q = str(search_text).lower()
        view_df = view_df[
            view_df.astype(str).apply(
                lambda row: row.str.lower().str.contains(q, na=False).any(),
                axis=1
            )
        ]

    st.caption("View-only mode. No edit/delete buttons.")
    st.dataframe(view_df, use_container_width=True, height=520)


def page_cloud_excel_view_only():
    render_cloud_excel_view_only()


# ============================================================
# ADMIN PANEL
# ============================================================
def page_admin_panel():
    page_hero("Admin Panel", "Cloud Excel control center: revenue, employees, delete requests, data manager and settings.", "Admin")

    premium_panel("Admin Control Center", "Clean admin access: reports, customer history, cloud Excel manager, employee control and settings.")

    invoices = read_sheet("invoices")
    if "Total Amount" in invoices.columns:
        invoices["Total Amount"] = pd.to_numeric(invoices["Total Amount"], errors="coerce").fillna(0)
    else:
        invoices["Total Amount"] = 0

    tabs = st.tabs([
        "📊 Revenue",
        "👥 Employees",
        "🗑️ Delete Requests",
        "☁️ Sync Google",
        "☁️ Cloud Excel View Only",
        "⚙️ Settings"
    ])

    with tabs[0]:
        st.markdown("<div class='admin-tab-note'>Admin revenue overview. Duplicate approval and manual invoice generator are hidden for Admin.</div>", unsafe_allow_html=True)

        month_key = app_now().strftime("%m-%Y")
        temp = invoices.copy()
        temp["Month"] = pd.to_datetime(temp["Date"], format="%d-%m-%Y", errors="coerce").dt.strftime("%m-%Y")
        month_df = temp[temp["Month"] == month_key] if "Month" in temp.columns else invoices
        active_df = invoices[invoices["Status"].astype(str) == "Active"] if "Status" in invoices.columns else invoices

        c1, c2, c3 = st.columns(3)
        with c1:
            ultra_card("Monthly Revenue", f"₹{month_df['Total Amount'].sum():,.0f}", "Admin only", "💰")
        with c2:
            ultra_card("Active Entries", len(active_df), "Stored invoices", "🏍️")
        with c3:
            ultra_card("Total Revenue", f"₹{invoices['Total Amount'].sum():,.0f}", "All entries", "📈")

        st.markdown("<div class='section-title'>Technician-wise Revenue</div>", unsafe_allow_html=True)
        if not invoices.empty and "Technician Name" in invoices.columns:
            tech = invoices.groupby("Technician Name", dropna=False)["Total Amount"].sum().reset_index()
            st.dataframe(tech, use_container_width=True)
        else:
            st.info("No invoice data.")

    with tabs[1]:
        st.markdown("<div class='admin-tab-note'>Add or update employee login details and roles.</div>", unsafe_allow_html=True)
        employees = read_sheet("employees")
        st.dataframe(employees, use_container_width=True)

        st.markdown("""
        <div class="password-reset-panel">
            <h3>🔐 Admin Password Reset / Update</h3>
            <p>Employee password reset panna User ID select pannitu new password save pannunga.</p>
        </div>
        """, unsafe_allow_html=True)

        if not employees.empty:
            reset_user = st.selectbox(
                "Select User ID for Password Reset",
                employees["User ID"].astype(str).tolist(),
                key="admin_password_reset_user"
            )
            new_reset_pwd = st.text_input("New Password", type="password", key="admin_password_reset_new")
            if st.button("Update Password", use_container_width=True, key="admin_password_reset_btn"):
                if not new_reset_pwd.strip():
                    st.error("New password required.")
                else:
                    emp_df = read_sheet("employees")
                    idxs = emp_df[emp_df["User ID"].astype(str) == str(reset_user)].index
                    if len(idxs) > 0:
                        emp_df.loc[idxs[0], "Password"] = new_reset_pwd.strip()
                        write_sheet("employees", emp_df)
                        try:
                            add_audit_log("Password Reset", "employees", str(reset_user), "", "Password updated by Admin")
                        except Exception:
                            pass
                        st.success(f"{reset_user} password updated successfully.")
                        st.rerun()
                    else:
                        st.error("Selected user not found.")


        with st.expander("Add / Edit Employee", expanded=False):
            user_id = st.text_input("User ID")
            password = st.text_input("Password")
            emp_name = st.text_input("Employee Name")
            emp_role = st.selectbox("Role", ["Admin", "Manager", "Technician", "Prathisha / System Staff"])
            status = st.selectbox("Status", ["Active", "Inactive"])

            if st.button("Save Employee", use_container_width=True):
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
                    st.cache_data.clear()
                    st.rerun()

    with tabs[2]:
        st.markdown("<div class='admin-tab-note'>Technician delete requests. Invoice deletes only after Admin approval.</div>", unsafe_allow_html=True)

        req = read_sheet("delete_requests")
        pending = req[req["Request Status"].astype(str) == "Pending"] if not req.empty and "Request Status" in req.columns else pd.DataFrame()

        if pending.empty:
            st.success("No pending delete requests.")
        else:
            for idx, row in pending.iterrows():
                st.markdown(f"""
                <div class="approval-card">
                    <h3>Delete Request {status_badge("Pending", "yellow")}</h3>
                    <p><b>Request ID:</b> {row['Request ID']} | <b>Entry ID:</b> {row['Entry ID']}</p>
                    <p><b>Technician:</b> {row['Technician Name']}</p>
                    <p><b>Reason:</b> {row['Reason']}</p>
                </div>
                """, unsafe_allow_html=True)

                c1, c2 = st.columns(2)
                if c1.button("Approve Delete", key=f"approve_{idx}", use_container_width=True):
                    inv = read_sheet("invoices")
                    inv_idx = inv[inv["Entry ID"].astype(str) == str(row["Entry ID"])].index if "Entry ID" in inv.columns else []
                    if len(inv_idx) > 0:
                        inv = inv.drop(inv_idx).reset_index(drop=True)
                        write_sheet("invoices", inv)

                    req.loc[idx, "Request Status"] = "Approved"
                    req.loc[idx, "Admin Action Date"] = now_stamp()
                    write_sheet("delete_requests", req)
                    st.cache_data.clear()
                    st.success("Request approved and invoice deleted.")
                    st.rerun()

                if c2.button("Reject Request", key=f"reject_{idx}", use_container_width=True):
                    req.loc[idx, "Request Status"] = "Rejected"
                    req.loc[idx, "Admin Action Date"] = now_stamp()
                    write_sheet("delete_requests", req)
                    st.cache_data.clear()
                    st.warning("Request rejected.")
                    st.rerun()

    with tabs[3]:
        st.markdown("<div class='admin-tab-note'>Sync Google: Excel data Google Sheet-ku auto sync 3 minutes once. Manual sync button also available.</div>", unsafe_allow_html=True)

        state = load_google_sync_state()
        dirty_sheets = state.get("dirty_sheets", [])
        wait_text = get_google_next_sync_wait_text()

        st.markdown(f"""
        <div class="sync-status-box">
            <b>Google Sync Status</b><br>
            Waiting Sheets: {len(dirty_sheets)}<br>
            Next Sync: {wait_text}<br>
            Last Sync: {state.get("last_sync_time", "Not yet")}
        </div>
        """, unsafe_allow_html=True)

        if is_google_sync_configured():
            st.success("Google Sheet sync configured.")
        else:
            st.warning("Google Sheet sync OFF. SHEET_ID and gcp_service_account secrets required.")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Auto Sync", "3 mins")
        c2.metric("Waiting Sheets", len(dirty_sheets))
        c3.metric("Next Sync", wait_text)
        c4.metric("Last Sync", state.get("last_sync_time", "Not yet"))

        if dirty_sheets:
            st.caption("Waiting sheets: " + ", ".join(dirty_sheets))
        else:
            st.caption("No pending changes. Google Sheet is updated or no changes made.")

        st.caption("Last status: " + str(state.get("last_sync_status", "Not yet")))
        if state.get("last_sync_message"):
            st.caption("Last message: " + str(state.get("last_sync_message", "")))


        st.markdown("""
        <div class="pull-sync-panel">
            <h3>🔄 Pull Google Sheet → Cloud Excel</h3>
            <p>Google Sheet-la direct edit/delete pannina, indha option use pannina app Cloud Excel file update aagum.</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="pull-sync-warning">
            Warning: Pull pannina selected Cloud Excel sheet Google Sheet data-kku match aagum.
            Google Sheet-la delete pannina rows Cloud Excel-layum delete aagum.
        </div>
        """, unsafe_allow_html=True)

        pull_sheet = st.selectbox(
            "Select Sheet to Pull from Google Sheet",
            list(SHEETS.keys()),
            key="pull_google_sheet_name"
        )

        c_pull1, c_pull2 = st.columns(2)
        if c_pull1.button("Pull Selected Google Sheet to Cloud Excel", use_container_width=True):
            with st.spinner("Pulling selected Google Sheet data to Cloud Excel..."):
                ok, msg = pull_single_google_sheet_to_excel(pull_sheet)
            if ok:
                st.success(msg)
            else:
                st.error(msg)
            st.rerun()

        if c_pull2.button("Pull ALL Google Sheets to Cloud Excel", use_container_width=True):
            confirm_pull = st.session_state.get("confirm_pull_all_google_to_excel", False)
            if not confirm_pull:
                st.session_state["confirm_pull_all_google_to_excel"] = True
                st.warning("Click same button again to confirm full pull. This overwrites Cloud Excel sheets with Google Sheet data.")
            else:
                with st.spinner("Pulling all Google Sheet data to Cloud Excel..."):
                    ok, msg = pull_all_google_sheets_to_excel()
                st.session_state["confirm_pull_all_google_to_excel"] = False
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)
                st.rerun()


        st.caption("Manual sync removed. Google Sheet edit/delete panna Pull Google Sheet → Cloud Excel use pannunga.")


    with tabs[4]:
        render_cloud_excel_view_only()

    with tabs[5]:
        st.markdown("<div class='admin-tab-note'>Settings and password-protected cloud Excel download.</div>", unsafe_allow_html=True)

        settings = read_sheet("settings")
        st.dataframe(settings, use_container_width=True)

        st.subheader("PDF Logo Cache")
        st.caption("Hero logo zoom/circle format refresh panna use pannunga. PDF design issue irundha indha button click pannunga.")
        if st.button("Clear PDF Logo Cache", use_container_width=True):
            ok = clear_pdf_logo_cache()
            if ok:
                st.success("PDF logo cache cleared. Next PDF will regenerate zoom logo.")
            else:
                st.warning("Cache clear panna mudiyala. But app continue work aagum.")




# ============================================================
# MANAGER EDIT
# ============================================================

# ============================================================
# BACKUP OPTIONAL
# ============================================================
def make_backup_zip():
    name = f"selva_backup_{app_now().strftime('%Y%m%d_%H%M%S')}.zip"
    path = BACKUP_DIR / name

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        if EXCEL_FILE.exists():
            z.write(EXCEL_FILE, EXCEL_FILE.name)
        for pdf in PDF_DIR.glob("*.pdf"):
            z.write(pdf, f"generated_reports/{pdf.name}")

    return path



def page_duplicate_upload_finder():
    page_hero("Duplicate Upload Finder", "Manager can view duplicate Job Card uploads and delete selected duplicate row.", "Manager")

    invoices = read_sheet("invoices")
    if invoices.empty:
        st.info("No invoice entries found.")
        return

    if "Job Card Number" not in invoices.columns:
        st.warning("Job Card Number column not found.")
        st.dataframe(invoices, use_container_width=True)
        return

    temp = invoices.copy().reset_index(drop=True)
    temp["Clean Job Card"] = temp["Job Card Number"].astype(str).apply(normalize_invoice_jobcard_no)
    dup_mask = temp["Clean Job Card"].duplicated(keep=False) & (temp["Clean Job Card"].astype(str).str.len() > 0)
    dup_rows = temp[dup_mask].copy()

    if dup_rows.empty:
        st.success("No duplicate Job Card uploads found.")
        return

    st.warning(f"Duplicate Job Card rows found: {len(dup_rows)}")
    show_cols = [
        "Entry ID", "Date", "Technician Name", "User ID", "Invoice Number",
        "Job Card Number", "Registration Number", "Bike Model",
        "Labour Amount", "Spare Parts Count", "Spare Amount",
        "Oil Change Status", "Total Amount", "Entry Type", "Status"
    ]
    show_cols = [c for c in show_cols if c in dup_rows.columns]
    dup_rows["Original Row Number"] = dup_rows.index + 1
    st.dataframe(dup_rows[["Original Row Number"] + show_cols], use_container_width=True)

    selected_row_no = st.selectbox(
        "Select duplicate row number to delete",
        dup_rows["Original Row Number"].astype(int).tolist(),
        format_func=lambda x: f"Row {x}",
        key="duplicate_delete_row_no"
    )
    selected_index = int(selected_row_no) - 1
    st.dataframe(invoices.loc[[selected_index], show_cols], use_container_width=True)

    confirm = st.text_input("Type DELETE to confirm direct Excel delete", key="manager_duplicate_delete_confirm")
    if st.button("Delete Selected Duplicate Row", use_container_width=True, key="delete_duplicate_row_btn"):
        if confirm != "DELETE":
            st.error("Type DELETE exactly to confirm.")
            return
        df = read_sheet("invoices").reset_index(drop=True)
        df = df.drop(index=selected_index).reset_index(drop=True)
        write_sheet("invoices", df)
        st.success("Selected duplicate row deleted directly from Excel.")
        st.rerun()


# ============================================================
# MAIN
# ============================================================
def main():
    if not st.session_state.get("logged_in"):
        page_login()
        return


    auto_sync_google_sheet_3min()

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
        if is_manager():
            page_manual_invoice()
        else:
            st.error("Manager access only.")
    elif page == "Delete Invoice Request":
        page_delete_invoice_request()
    elif page == "Admin Panel":
        if is_admin():
            page_admin_panel()
        else:
            st.error("Admin access only.")
    elif page == "Duplicate Upload Finder":
        if is_manager():
            page_duplicate_upload_finder()
        else:
            st.error("Manager access only.")


if __name__ == "__main__":
    main()
