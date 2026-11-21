from datetime import date
from io import BytesIO

import pandas as pd
from openpyxl import load_workbook

from report_engine import (
    REPORT_COLUMNS,
    build_daily_business_report,
    build_technician_daily_report,
    build_individual_monthly_report,
    create_single_report_workbook,
)


def _sample_source():
    rows = [
        {
            "Entry ID": "E-1", "Date": "21-11-2026", "Technician Name": "Tech A", "User ID": "a1",
            "Job Card Number": "JC-001", "Registration Number": "TN01AA0001", "Bike Model": "Splendor",
            "Service Type": "Paid Service", "Labour Amount": "500", "Spare Parts Count": "2",
            "Spare Amount": "1000", "Oil Change Status": "YES", "Oil Amount": "300",
            "Total Amount": "1800", "Entry Type": "OCR", "Status": "Completed",
        },
        {
            # Exact duplicate should not double count.
            "Entry ID": "E-1", "Date": "21-11-2026", "Technician Name": "Tech A", "User ID": "a1",
            "Job Card Number": "JC-001", "Registration Number": "TN01AA0001", "Bike Model": "Splendor",
            "Service Type": "Paid Service", "Labour Amount": "500", "Spare Parts Count": "2",
            "Spare Amount": "1000", "Oil Change Status": "YES", "Oil Amount": "300",
            "Total Amount": "1800", "Entry Type": "OCR", "Status": "Completed",
        },
        {
            "Entry ID": "E-2", "Date": "21-11-2026", "Technician Name": "Tech B", "User ID": "b1",
            "Job Card Number": "JC-002", "Registration Number": "TN01AA0002", "Bike Model": "HF Deluxe",
            "Service Type": "FSC", "Labour Amount": "0", "Spare Parts Count": "0",
            "Spare Amount": "0", "Oil Change Status": "NO", "Oil Amount": "0",
            "Total Amount": "0", "Entry Type": "OCR", "Status": "Pending",
        },
        {
            "Entry ID": "E-3", "Date": "20-11-2026", "Technician Name": "Tech A", "User ID": "a1",
            "Job Card Number": "JC-003", "Registration Number": "TN01AA0003", "Bike Model": "HF Deluxe",
            "Service Type": "Paid Service", "Labour Amount": "400", "Spare Parts Count": "1",
            "Spare Amount": "300", "Oil Change Status": "YES", "Oil Amount": "100",
            "Total Amount": "800", "Entry Type": "OCR", "Status": "Completed",
        },
        {
            "Entry ID": "E-4", "Date": "21-11-2026", "Technician Name": "", "User ID": "",
            "Job Card Number": "JC-004", "Registration Number": "TN01AA0004", "Bike Model": "HF Deluxe",
            "Service Type": "Other", "Labour Amount": "200", "Spare Parts Count": "0",
            "Spare Amount": "0", "Oil Change Status": "NO", "Oil Amount": "0",
            "Total Amount": "200", "Entry Type": "OCR", "Status": "Active",
        },
    ]
    frame = pd.DataFrame(rows)
    for column in REPORT_COLUMNS:
        if column not in frame:
            frame[column] = ""
    return frame[REPORT_COLUMNS]


def test_daily_business_report_date_filter_and_service_classification():
    report = build_daily_business_report(_sample_source(), date(2026, 11, 21))
    summary = report["summary"]
    assert summary["total_job_cards"] == 3
    assert summary["completed_job_cards"] == 1
    assert summary["pending_job_cards"] == 1
    assert summary["paid_service_count"] == 1
    assert summary["fsc_count"] == 1
    assert summary["spare_sales"] == 1000
    assert summary["oil_amount"] == 300
    assert summary["labour_amount"] == 700
    assert len(report["jobcard_details"]) == 3


def test_technician_daily_report_contains_only_selected_technician():
    report = build_technician_daily_report(
        _sample_source(), date(2026, 11, 21), technician_name="Tech A", user_id="a1"
    )
    assert report["summary"]["total_job_cards"] == 1
    assert report["summary"]["labour_amount"] == 500
    assert report["summary"]["spare_sales"] == 1000
    assert set(report["jobcard_details"]["Technician Name"]) == {"Tech A"}
    assert "User ID" not in report["jobcard_details"].columns


def test_daily_report_deduplicates_and_does_not_assign_unassigned_jobs():
    report = build_daily_business_report(_sample_source(), date(2026, 11, 21))
    technicians = report["technician_summary"]
    assert technicians["Total Jobs"].sum() == 2
    assert set(technicians["Technician"]) == {"Tech A", "Tech B"}
    assert report["summary"]["duplicate_rows_removed"] == 1
    assert report["summary"]["unassigned_job_cards"] == 1


def test_individual_monthly_report_only_builds_requested_report():
    report = build_individual_monthly_report(_sample_source(), 11, 2026, "fsc")
    assert report["report_type"] == "fsc"
    assert len(report["details"]) == 1
    assert report["details"].iloc[0]["Service Type"] == "FSC"


def test_daily_report_export_is_readable_xlsx():
    report = build_daily_business_report(_sample_source(), date(2026, 11, 21))
    xlsx = create_single_report_workbook("Daily Business Report", report["summary"], report["jobcard_details"], report["technician_summary"])
    assert xlsx[:2] == b"PK"
    workbook = load_workbook(BytesIO(xlsx), read_only=True)
    assert workbook.sheetnames == ["Summary", "Details", "Technicians"]
    assert workbook["Details"].max_row == len(report["jobcard_details"]) + 1


def test_daily_report_returns_clean_empty_result_for_date_without_records():
    report = build_daily_business_report(_sample_source(), date(2026, 11, 19))
    assert report["summary"]["total_job_cards"] == 0
    assert report["jobcard_details"].empty
    assert report["technician_summary"].empty
