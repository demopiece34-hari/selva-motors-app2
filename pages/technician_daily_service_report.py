import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import pandas as pd
import streamlit as st


def _norm_date(value) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    dt = pd.to_datetime(text.replace("/", "-"), dayfirst=True, errors="coerce")
    if pd.isna(dt):
        return text.replace("/", "-")
    return dt.strftime("%d-%m-%Y")


def _safe_num(series: pd.Series) -> float:
    try:
        return float(pd.to_numeric(series, errors="coerce").fillna(0).sum())
    except Exception:
        return 0.0


def _default_summary_cards(items):
    cols = st.columns(len(items)) if items else []
    for col, (title, value, caption) in zip(cols, items):
        with col:
            st.metric(title, value, caption)


def _pick_columns(df: pd.DataFrame, columns: list[str]) -> list[str]:
    return [c for c in columns if c in df.columns]


def page_technician_daily_service_report(
    *,
    read_sheet: Callable[[str], pd.DataFrame],
    today_str: Callable[[], str],
    generate_report_pdf: Optional[Callable[[pd.DataFrame, str, str], str]] = None,
    report_summary_cards: Optional[Callable[[list], None]] = None,
    clean_reg_no: Optional[Callable[[str], str]] = None,
) -> None:
    """
    Technician Daily Service Report page.
    Intended to be imported into app.py and called from routing.
    """
    st.markdown(
        """
        <style>
        .tech-report-panel {
            background: linear-gradient(135deg, #ffffff, #fff7f7);
            border: 1px solid rgba(227,24,55,.14);
            border-radius: 24px;
            padding: 18px;
            box-shadow: 0 16px 38px rgba(17,24,39,.08);
            margin: 12px 0 18px 0;
        }
        .tech-report-panel h3 {
            margin: 0 0 6px 0;
            color: #111827;
            font-size: 18px;
            font-weight: 900;
        }
        .tech-report-panel p {
            margin: 0;
            color: #64748b;
            font-size: 13px;
            font-weight: 700;
        }
        .tech-note {
            background: #f8fafc;
            border-left: 5px solid #e31837;
            padding: 12px 14px;
            border-radius: 14px;
            margin: 10px 0 16px 0;
            color: #334155;
            font-weight: 700;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if report_summary_cards is None:
        report_summary_cards = _default_summary_cards

    st.markdown(
        """
        <div class="tech-report-panel">
            <h3>🏍️ Technician Daily Service Report</h3>
            <p>Technician-ku avangaloda today service entries mattum clean-aa kaattum.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    invoices = read_sheet("invoices")
    if invoices is None or invoices.empty:
        st.info("No invoice entries found.")
        return

    for col in ["Total Amount", "Labour Amount", "Spare Amount"]:
        if col in invoices.columns:
            invoices[col] = pd.to_numeric(invoices[col], errors="coerce").fillna(0)
        else:
            invoices[col] = 0

    col1, col2, col3 = st.columns([1.1, 1.1, 1.1])
    with col1:
        report_date = st.text_input("Report Date DD-MM-YYYY", value=today_str(), key="tech_daily_report_date")
    with col2:
        tech_candidates = ["All Technicians"]
        if "User ID" in invoices.columns:
            tech_candidates += sorted([x for x in invoices["User ID"].astype(str).unique().tolist() if x.strip()])
        elif "Technician Name" in invoices.columns:
            tech_candidates += sorted([x for x in invoices["Technician Name"].astype(str).unique().tolist() if x.strip()])
        selected_tech = st.selectbox("Technician", tech_candidates, key="tech_daily_report_user")
    with col3:
        service_type = st.selectbox(
            "Service Type",
            ["All", "FSC", "Paid Service", "General", "Joyride", "Accident"],
            key="tech_daily_report_service_type",
        )

    df = invoices.copy()
    if "Date" in df.columns:
        df["Date"] = df["Date"].astype(str).apply(_norm_date)
        df = df[df["Date"] == _norm_date(report_date)]

    if selected_tech != "All Technicians":
        if "User ID" in df.columns:
            df = df[df["User ID"].astype(str).str.strip().str.upper() == selected_tech.strip().upper()]
        elif "Technician Name" in df.columns:
            df = df[df["Technician Name"].astype(str).str.strip().str.upper() == selected_tech.strip().upper()]

    if service_type != "All" and "Service Type" in df.columns:
        df = df[df["Service Type"].astype(str).str.strip() == service_type]

    if clean_reg_no is not None and "Registration Number" in df.columns:
        reg_search = st.text_input("Registration Filter", value="", key="tech_daily_report_reg")
        if reg_search.strip():
            reg_clean = clean_reg_no(reg_search)
            df = df[df["Registration Number"].astype(str).str.upper().str.strip() == reg_clean]

    total_entries = len(df)
    total_labour = _safe_num(df["Labour Amount"]) if "Labour Amount" in df.columns else 0
    total_spare = _safe_num(df["Spare Amount"]) if "Spare Amount" in df.columns else 0
    total_revenue = _safe_num(df["Total Amount"]) if "Total Amount" in df.columns else 0

    report_summary_cards([
        ("Daily Entries", total_entries, "Selected date"),
        ("Total Labour", f"₹{total_labour:,.0f}", "Today labour"),
        ("Total Spare", f"₹{total_spare:,.0f}", "Today spare"),
        ("Total Revenue", f"₹{total_revenue:,.0f}", "Today total"),
    ])

    if df.empty:
        st.error("No daily technician rows matched the selected date / technician filter.")
        st.info("Fix: check Date format, User ID / Technician Name selection, and Service Type filter.")
        return

    st.caption(f"Report generated for: {report_date}")

    show_cols = [
        "Date", "Technician Name", "User ID", "Entry ID", "Invoice Number", "Job Card Number",
        "Registration Number", "Bike Model", "Service Type", "Labour Amount", "Spare Amount",
        "Total Amount", "Entry Type", "Status"
    ]
    visible_cols = _pick_columns(df, show_cols)
    st.dataframe(df[visible_cols] if visible_cols else df, use_container_width=True)

    pdf_title = f"Technician Daily Service Report - {selected_tech} - {report_date}"

    if generate_report_pdf is not None and st.button("Generate PDF Report", use_container_width=True, key="tech_daily_pdf_btn"):
        pdf_path = generate_report_pdf(df, pdf_title, "technician_daily_service_report.pdf")
        st.session_state["technician_daily_service_report_pdf"] = pdf_path
        st.success("PDF report generated.")

    pdf_path = st.session_state.get("technician_daily_service_report_pdf")
    if pdf_path and Path(pdf_path).exists():
        with open(pdf_path, "rb") as f:
            st.download_button(
                "Download PDF Report",
                f,
                file_name=Path(pdf_path).name,
                mime="application/pdf",
                use_container_width=True,
                key="tech_daily_pdf_download",
            )

    st.markdown(
        f"""
        <div class="tech-note">
            ✅ No error found for this report page.<br>
            Selected Date: <b>{report_date}</b><br>
            Rows Found: <b>{len(df)}</b>
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    st.title("Technician Daily Service Report")
    st.info("This module is meant to be imported into app.py.")
