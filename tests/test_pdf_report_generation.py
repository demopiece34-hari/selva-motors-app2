from pathlib import Path

import pandas as pd
import pdfplumber

from pdf_generator import generate_professional_report_pdf


def _read_pdf(path: Path):
    with pdfplumber.open(path) as pdf:
        return pdf, "\n".join(page.extract_text() or "" for page in pdf.pages)


def test_branded_pdf_contains_logo_location_currency_and_tamil(tmp_path):
    path = Path(generate_professional_report_pdf(
        pd.DataFrame(),
        "Technician Daily Report",
        tmp_path / "technician_daily.pdf",
        metadata={"Technician": "முருகன்", "Report Date": "21-11-2026"},
        kpis=[("Total Job Cards", 3), ("Labour Amount", 1350.0)],
        sections=[("Job Card Details", pd.DataFrame([
            {"Job Card Number": "RJC-1126-1001", "Technician": "முருகன்", "Labour Amount": 450.0}
        ]))],
    ))
    pdf, text = _read_pdf(path)
    assert path.exists() and path.stat().st_size > 1000
    assert "SELVA MOTORS" in text
    assert "Near Bypass, Kilvelur" in text
    assert "₹1,350.00" in text
    assert "முருகன்" in text
    assert "Page 1 of 1" in text
    assert pdf.pages[0].images, "Hero logo should be embedded in the PDF header"


def test_multipage_pdf_repeats_table_headers_and_total_page_numbers(tmp_path):
    details = pd.DataFrame([
        {
            "Date": "21-11-2026",
            "Job Card Number": f"RJC-1126-{index:04d}",
            "Technician Name": "Technician A",
            "Service Type": "Paid Service",
            "Spare Parts Amount": 1250.5,
            "Oil Amount": 550.0,
            "Labour Amount": 450.0,
            "Status": "Completed",
        }
        for index in range(1, 121)
    ])
    path = Path(generate_professional_report_pdf(
        pd.DataFrame(),
        "Monthly Job Card Report",
        tmp_path / "monthly_job_cards.pdf",
        metadata={"Report Period": "11-2026"},
        sections=[("Job Card Details", details)],
    ))
    pdf, _ = _read_pdf(path)
    assert len(pdf.pages) > 1
    for index, page in enumerate(pdf.pages, start=1):
        text = page.extract_text() or ""
        assert f"Page {index} of {len(pdf.pages)}" in text
        assert "SELVA MOTORS" in text
        assert "Monthly Job Card Report" in text
        assert "Near Bypass, Kilvelur" in text
        assert page.images, "Hero logo should repeat on every page"
    assert "Job Card Number" in (pdf.pages[1].extract_text() or "")


def test_empty_report_has_professional_no_records_message(tmp_path):
    path = Path(generate_professional_report_pdf(
        pd.DataFrame(),
        "FSC Report",
        tmp_path / "empty_fsc.pdf",
        metadata={"Report Period": "11-2026"},
        sections=[("FSC Details", pd.DataFrame())],
    ))
    _, text = _read_pdf(path)
    assert "No records matched the selected filters." in text


def test_reports_module_exposes_pdf_only_download_controls():
    source = Path(__file__).resolve().parents[1] / "report_center.py"
    text = source.read_text(encoding="utf-8")
    assert "DOWNLOAD {title.upper()} (PDF)" in text
    assert "application/pdf" in text
    assert "application/vnd.openxmlformats-officedocument" not in text
    assert ".xlsx" not in text
    assert "(EXCEL)" not in text
