"""Reusable Selva Motors Hero theme. Presentation-only; never accesses business data."""
from __future__ import annotations

import streamlit as st

_BASE_CSS = r'''

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


'''

_HERO_OVERRIDE_CSS = r'''

/* ============================================================
   SELVA MOTORS • HERO AUTOMOTIVE DESIGN SYSTEM
   Presentation only — no data access or Streamlit reruns.
   ============================================================ */
:root {
  color-scheme: dark;
  --hero-dark: #090b10;
  --hero-navy: #11151d;
  --hero-panel: #151a23;
  --hero-panel-2: #1b222d;
  --hero-red: #e31837;
  --hero-red-bright: #ff3654;
  --hero-green: #e31837;
  --hero-blue: #e31837;
  --hero-gold: #d5a34a;
  --hero-card: rgba(22, 27, 36, .94);
  --hero-border: rgba(255,255,255,.09);
  --hero-text: #f4f5f7;
  --hero-muted: #9aa4b2;
}

html, body, [class*="css"] { font-family: Inter, ui-sans-serif, system-ui, sans-serif; }
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
  color: var(--hero-text);
  background: #090b10;
}
[data-testid="stHeader"] { background: rgba(9,11,16,.92); }
[data-testid="stToolbar"] { right: 1rem; }
.block-container { max-width: 1500px; padding-top: 1.4rem; padding-bottom: 2.6rem; }
[data-testid="stMainBlockContainer"] { padding-left: clamp(1rem, 3vw, 2.5rem); padding-right: clamp(1rem, 3vw, 2.5rem); }

/* Premium navigation rail */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0b0e14 0%, #10151e 62%, #0b0e14 100%);
  border-right: 1px solid rgba(255,255,255,.08);
}
[data-testid="stSidebar"] > div:first-child { background: transparent; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: .55rem; }
[data-testid="stSidebar"] * { color: #e9edf2; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #9da8b7; }
[data-testid="stSidebar"] .stRadio [role="radiogroup"] { gap: .35rem; }
[data-testid="stSidebar"] .stRadio label {
  min-height: 42px; padding: .55rem .75rem; margin: 0;
  border: 1px solid transparent; border-radius: 11px;
  background: rgba(255,255,255,.025); transition: background .18s ease, border-color .18s ease, transform .18s ease;
}
[data-testid="stSidebar"] .stRadio label:hover {
  background: rgba(227,24,55,.12); border-color: rgba(227,24,55,.26); transform: translateX(2px);
}
[data-testid="stSidebar"] .stRadio label:has(input:checked) {
  background: linear-gradient(90deg, rgba(227,24,55,.22), rgba(227,24,55,.07));
  border-color: rgba(227,24,55,.42); box-shadow: inset 3px 0 0 var(--hero-red);
}
[data-testid="stSidebar"] [data-testid="stImage"] { margin-bottom: -.35rem; }

/* Typography and surfaces */
h1, h2, h3, h4, h5, h6 { color: #f7f8fa !important; letter-spacing: -.025em; }
p, label, [data-testid="stMarkdownContainer"] { color: #d8dee7; }
small, .subtle, [data-testid="stCaptionContainer"] { color: var(--hero-muted) !important; }
hr { border-color: rgba(255,255,255,.09) !important; }
[data-testid="stVerticalBlockBorderWrapper"], [data-testid="stExpander"] {
  background: rgba(20,25,34,.72); border: 1px solid rgba(255,255,255,.085); border-radius: 16px;
}
[data-testid="stMetric"] {
  padding: .85rem 1rem; border-radius: 14px;
  background: linear-gradient(145deg, #171d27, #11161e);
  border: 1px solid rgba(255,255,255,.08);
}
[data-testid="stMetricLabel"] { color: #aeb8c6 !important; }
[data-testid="stMetricValue"] { color: #fff !important; }

/* Inputs and forms */
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
[data-testid="stDateInput"] input, [data-testid="stTimeInput"] input,
[data-testid="stTextArea"] textarea, [data-baseweb="select"] > div {
  color: #f5f7fa !important; background: #111720 !important;
  border: 1px solid #303a48 !important; border-radius: 10px !important;
  box-shadow: none !important;
}
[data-testid="stTextInput"] input:focus, [data-testid="stNumberInput"] input:focus,
[data-testid="stTextArea"] textarea:focus { border-color: var(--hero-red) !important; box-shadow: 0 0 0 1px rgba(227,24,55,.25) !important; }
[data-testid="stTextInput"] input::placeholder, [data-testid="stTextArea"] textarea::placeholder { color: #738092 !important; }
[data-baseweb="select"] *, [role="listbox"] * { color: #f1f4f8 !important; }
[data-baseweb="popover"] [role="listbox"], [data-baseweb="menu"] { background: #171d27 !important; border: 1px solid #303a48 !important; }
[data-testid="stForm"] { background: #111720; border: 1px solid rgba(255,255,255,.09); border-radius: 16px; padding: 1rem; }
[data-testid="stFileUploader"] section {
  background: linear-gradient(145deg, rgba(227,24,55,.07), rgba(255,255,255,.02));
  border: 1px dashed rgba(227,24,55,.48); border-radius: 16px;
}
[data-testid="stFileUploader"] small { color: #9da8b7 !important; }

/* Buttons */
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] button {
  color: #fff !important; background: #242b36 !important;
  border: 1px solid #3a4554 !important; border-radius: 10px !important;
  font-weight: 750 !important; min-height: 42px;
  transition: transform .16s ease, background .16s ease, border-color .16s ease, box-shadow .16s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover, [data-testid="stFormSubmitButton"] button:hover {
  background: #303948 !important; border-color: #596779 !important; transform: translateY(-1px);
}
.stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primary"],
.stButton > button[data-testid="stBaseButton-primary"] {
  background: linear-gradient(135deg, #e31837, #b80f29) !important;
  border-color: #f0445d !important; box-shadow: 0 8px 22px rgba(227,24,55,.18);
}
.stButton > button[kind="primary"]:hover, [data-testid="stFormSubmitButton"] button[kind="primary"]:hover {
  background: linear-gradient(135deg, #f02b49, #c81431) !important; box-shadow: 0 10px 25px rgba(227,24,55,.28);
}

/* Tabs, tables, alerts and progress */
.stTabs [data-baseweb="tab-list"] { gap: .35rem; border-bottom: 1px solid rgba(255,255,255,.1); }
.stTabs [data-baseweb="tab"] { color: #aeb8c6; background: transparent; border-radius: 9px 9px 0 0; padding: .6rem .9rem; }
.stTabs [aria-selected="true"] { color: #fff !important; border-bottom: 2px solid var(--hero-red) !important; }
[data-testid="stDataFrame"], [data-testid="stTable"] { border: 1px solid rgba(255,255,255,.1); border-radius: 12px; overflow: hidden; }
[data-testid="stAlert"] { border-radius: 12px; border: 1px solid rgba(255,255,255,.1); }
[data-testid="stProgressBar"] > div > div { background: var(--hero-red) !important; }
[data-testid="stSpinner"] { color: #ff526b; }

/* Keep the app's existing semantic components, restyled for Hero */
.app-title { color: #f7f8fa; }
.subtle { color: #a5afbd; }
.hero-panel {
  background: radial-gradient(circle at 92% 0%, rgba(227,24,55,.2), transparent 34%),
              linear-gradient(120deg, #171d27 0%, #10151d 65%, #19121a 100%);
  border: 1px solid rgba(255,255,255,.1); border-left: 4px solid var(--hero-red);
  border-radius: 17px; box-shadow: 0 15px 34px rgba(0,0,0,.22);
}
.hero-panel h1 { color: #fff !important; }
.hero-panel p { color: #aeb8c6 !important; }
.status-chip, .badge-red, .status-warn { background: rgba(227,24,55,.16) !important; color: #ff7589 !important; border-color: rgba(227,24,55,.32) !important; }
.badge-green, .status-ok { background: rgba(50,180,125,.12) !important; color: #72d6a9 !important; border-color: rgba(50,180,125,.25) !important; }
.badge-blue, .status-info { background: rgba(75,140,220,.14) !important; color: #8dbaff !important; border-color: rgba(75,140,220,.25) !important; }
.quick-card, .ultra-card, .ultra-status, .erp-card, .premium-title-card,
.invoice-preview-pro, .service-type-panel, .preview-item, .gps-refresh-card, .cloud-view-panel {
  background: linear-gradient(145deg, #171d27, #11161e) !important;
  color: #eff2f6 !important; border: 1px solid rgba(255,255,255,.09) !important;
  box-shadow: 0 10px 28px rgba(0,0,0,.16) !important;
}
.quick-card h3, .ultra-status h3, .invoice-preview-head h2 { color: #fff !important; }
.quick-card p, .ultra-status p, .premium-title-card p, .invoice-preview-head p { color: #aeb8c6 !important; }
.invoice-preview-body .invoice-field { background: #10151d !important; border-color: rgba(255,255,255,.08) !important; }
.invoice-preview-body .invoice-field b { color: #9da8b7 !important; }
.invoice-preview-body .invoice-field span { color: #f4f6f8 !important; }
.section-title { color: #f4f6f8 !important; border-left-color: var(--hero-red) !important; }
.feature-pill { color: #ffd5dc !important; background: rgba(227,24,55,.13) !important; border-color: rgba(227,24,55,.24) !important; }

/* Reusable sidebar and static Home components */
.sidebar-brand-caption { text-align:center; color:#f4f6f8; font-size:10px; font-weight:850; letter-spacing:2.1px; padding:0 0 14px; }
.sidebar-brand-caption span { color:var(--hero-red-bright); padding:0 3px; }
.sidebar-user-card { padding:13px 13px 12px; margin:2px 0 10px; border-radius:13px; background:linear-gradient(140deg,rgba(227,24,55,.13),rgba(255,255,255,.035)); border:1px solid rgba(255,255,255,.09); }
.sidebar-user-name { color:#fff; font-size:14px; font-weight:800; overflow-wrap:anywhere; }
.sidebar-user-role { color:#ff8b9b; font-size:11px; font-weight:750; text-transform:uppercase; letter-spacing:1.1px; margin-top:3px; }
.sidebar-session-state { color:#8390a0; font-size:9px; font-weight:800; letter-spacing:1.25px; margin-top:12px; }
.sidebar-session-state i { display:inline-block; width:6px; height:6px; border-radius:50%; background:#3fc48a; margin-right:6px; box-shadow:0 0 8px rgba(63,196,138,.5); }
.sidebar-nav-label { color:#758294; font-size:9px; font-weight:900; letter-spacing:1.8px; padding:5px 2px 3px; }
.home-welcome-panel { margin:8px 0 25px; padding:clamp(20px,3vw,34px); border-radius:18px; background:radial-gradient(circle at 92% 0%,rgba(227,24,55,.19),transparent 34%),linear-gradient(120deg,#171d27,#10151d); border:1px solid rgba(255,255,255,.095); border-left:4px solid var(--hero-red); box-shadow:0 16px 36px rgba(0,0,0,.2); }
.home-eyebrow { color:#ff7589; font-size:10px; font-weight:900; letter-spacing:2px; }
.home-user-title { color:#fff; font-size:clamp(25px,4vw,38px); font-weight:900; letter-spacing:-1px; margin-top:7px; }
.home-role-chip { display:inline-block; margin-top:10px; padding:5px 10px; background:rgba(227,24,55,.14); border:1px solid rgba(227,24,55,.25); color:#ff9baa; border-radius:99px; font-size:10px; font-weight:850; letter-spacing:1px; text-transform:uppercase; }
.home-divider { height:1px; background:rgba(255,255,255,.09); margin:22px 0 17px; }
.home-guidance-title { color:#eef1f5; font-size:11px; font-weight:900; letter-spacing:1.4px; }
.home-guidance-copy { color:#9da8b7; font-size:13px; line-height:1.65; max-width:760px; margin-top:6px; }
.ui-section-heading { margin:8px 0 13px; }
.ui-section-heading > div { color:#f3f5f8; font-size:18px; font-weight:850; }
.ui-section-heading p { color:#909cac; font-size:12px; margin:3px 0 0; }
.home-feature-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin:10px 0 14px; }
.home-feature-card { min-height:112px; padding:17px; border:1px solid rgba(255,255,255,.085); border-radius:14px; background:linear-gradient(145deg,#171d27,#11161e); display:flex; flex-direction:column; gap:7px; }
.home-feature-card span { color:#ff687f; font-size:10px; font-weight:900; letter-spacing:1.4px; }
.home-feature-card b { color:#f7f8fa; font-size:14px; }
.home-feature-card small { color:#909cac; font-size:11px; }
@media (max-width:760px) { .home-feature-grid { grid-template-columns:1fr; gap:8px; } .home-feature-card { min-height:85px; } }

/* Login surface */
.login-wrap { min-height: 68vh; }
.login-hero {
  background: radial-gradient(circle at 95% 0%, rgba(227,24,55,.18), transparent 36%),
              linear-gradient(145deg, #171d27, #0f141c) !important;
  border: 1px solid rgba(255,255,255,.1) !important; box-shadow: 0 26px 70px rgba(0,0,0,.34) !important;
}
.hero-login-panel { color: #fff !important; }
.hero-connect-title { color: #fff !important; }
.hero-login-status-badge { color: #ff7b8d !important; }
.hero-login-note { color: #929eae !important; }

/* Mobile spacing */
@media (max-width: 760px) {
  .block-container { padding: .8rem .7rem 1.5rem .7rem; }
  [data-testid="stMainBlockContainer"] { padding-left: .75rem; padding-right: .75rem; }
  .hero-panel { padding: 17px !important; margin-bottom: 14px; }
  .hero-panel h1 { font-size: 1.55rem !important; line-height: 1.2; }
  .login-hero { padding: 20px !important; border-radius: 20px !important; }
  .stButton > button, .stDownloadButton > button { min-height: 44px; }
  [data-testid="stSidebar"] { min-width: min(82vw, 320px); }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: .01ms !important; transition-duration: .01ms !important; scroll-behavior: auto !important; }
}

'''

def apply_theme() -> None:
    """Inject the shared design system once per Streamlit page render."""
    st.markdown(f"<style>{_BASE_CSS}\n{_HERO_OVERRIDE_CSS}</style>", unsafe_allow_html=True)
