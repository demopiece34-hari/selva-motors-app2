import unittest

import pandas as pd

from report_engine import (
    build_monthly_bundle,
    calculate_expense_totals,
    calculate_missing_jobcards,
    create_excel_report,
    create_missing_jobcard_workbook,
    technician_detail,
)


PREFIX = "67381-03-RJC-1126-"


def row(entry, date, jc, tech="Arun", labour=100, spare=200, oil=25, total=325, status="Active"):
    return {
        "Entry ID": entry,
        "Date": date,
        "Technician Name": tech,
        "User ID": "TECH01",
        "Job Card Number": jc,
        "Registration Number": "TN50AB1234",
        "Bike Model": "Splendor",
        "Service Type": "Paid Service",
        "Labour Amount": labour,
        "Spare Parts Count": 2,
        "Spare Amount": spare,
        "Oil Change Status": "Yes" if oil else "No",
        "Oil Amount": oil,
        "Total Amount": total,
        "Entry Type": "OCR Upload",
        "Status": status,
    }


class ReportEngineTests(unittest.TestCase):
    def test_month_filter_and_duplicate_jobcard_handling(self):
        rows = [
            row("E1", "01-11-2026", PREFIX + "1289", labour=100, spare=200, oil=25, total=325),
            row("E1-copy", "01-11-2026", PREFIX + "1289", labour=100, spare=200, oil=25, total=325),
            row("E2", "02-11-2026", PREFIX + "1290", tech="Bala", labour=300, spare=400, oil=50, total=750, status="Completed"),
            row("E3", "01-10-2026", PREFIX + "1291", labour=999, spare=999, oil=0, total=1998),
        ]
        bundle = build_monthly_bundle(pd.DataFrame(rows), 11, 2026)
        self.assertEqual(bundle["totals"]["jobcards"], 2)
        self.assertEqual(bundle["totals"]["labour"], 400)
        self.assertEqual(bundle["totals"]["spare"], 600)
        self.assertEqual(bundle["totals"]["oil"], 75)
        self.assertEqual(bundle["meta"]["duplicate_rows"], 1)
        self.assertEqual(len(bundle["jobcard_details"]), 2)

    def test_conflicting_duplicate_excluded_from_amount_totals(self):
        rows = [
            row("E1", "01-11-2026", PREFIX + "1289", labour=100),
            row("E2", "01-11-2026", PREFIX + "1289", labour=500),
            row("E3", "02-11-2026", PREFIX + "1290", labour=50),
        ]
        bundle = build_monthly_bundle(pd.DataFrame(rows), 11, 2026)
        self.assertEqual(bundle["meta"]["conflicting_jobcards"], 1)
        self.assertEqual(bundle["totals"]["labour"], 50)

    def test_missing_sequence_inclusive_and_series_isolated(self):
        records = pd.DataFrame([
            row("E1", "01-10-2026", PREFIX + "1289"),
            row("E2", "01-10-2026", PREFIX + "1290"),
            row("E3", "01-10-2026", PREFIX + "1290"),
            row("E4", "01-10-2026", PREFIX + "1292"),
            row("E5", "01-10-2026", "OTHER-SERIES-1291"),
        ])
        result = calculate_missing_jobcards(records, PREFIX + "1289", PREFIX + "1292")
        self.assertEqual(result["expected_count"], 4)
        self.assertEqual(result["found_count"], 3)
        self.assertEqual(result["missing_count"], 1)
        self.assertEqual(result["missing_numbers"], [PREFIX + "1291"])
        self.assertEqual(result["duplicate_count"], 1)
        self.assertTrue(result["verification"].startswith("VERIFIED"))

    def test_missing_sequence_validates_prefix_and_order(self):
        frame = pd.DataFrame([row("E1", "01-11-2026", PREFIX + "1289")])
        with self.assertRaisesRegex(ValueError, "different prefixes"):
            calculate_missing_jobcards(frame, PREFIX + "1289", "OTHER-1299")
        with self.assertRaisesRegex(ValueError, "less than or equal"):
            calculate_missing_jobcards(frame, PREFIX + "1290", PREFIX + "1289")

    def test_incomplete_source_is_not_reported_as_verified(self):
        frame = pd.DataFrame([
            row("E1", "01-11-2026", PREFIX + "1289"),
            row("E2", "01-11-2026", ""),
            row("E3", "01-11-2026", "BAD-JC"),
        ])
        result = calculate_missing_jobcards(frame, PREFIX + "1289", PREFIX + "1289")
        self.assertTrue(result["verification"].startswith("INCOMPLETE"))
        self.assertEqual(len(result["invalid_records"]), 2)

    def test_expense_calculation_and_negative_balance(self):
        expenses = [
            {"name": "Technician Salary", "amount": 10000},
            {"name": "Electricity", "amount": 1500},
            {"name": "Other Expenses", "amount": 500},
        ]
        totals = calculate_expense_totals(30000, expenses)
        self.assertEqual(totals["total_expenses"], 12000)
        self.assertEqual(totals["technician_salary"], 10000)
        self.assertEqual(totals["other_expenses"], 2000)
        self.assertEqual(totals["net_remaining"], 18000)
        self.assertEqual(calculate_expense_totals(100, [{"name": "Rent", "amount": 125}])["net_remaining"], -25)

    def test_empty_source_and_incomplete_audit(self):
        empty = pd.DataFrame(columns=["Entry ID", "Date", "Job Card Number"])
        bundle = build_monthly_bundle(empty, 11, 2026)
        self.assertEqual(bundle["totals"]["jobcards"], 0)
        self.assertEqual(bundle["totals"]["labour"], 0)
        audit = calculate_missing_jobcards(empty, PREFIX + "1289", PREFIX + "1290")
        self.assertTrue(audit["verification"].startswith("INCOMPLETE"))
        self.assertEqual(audit["expected_count"], 2)

    def test_technician_amounts_only_include_jobcard_linked_records(self):
        rows = [
            row("E1", "01-11-2026", PREFIX + "1289", tech="Arun", labour=100, spare=200),
            row("E2", "01-11-2026", "", tech="Arun", labour=500, spare=300),
        ]
        bundle = build_monthly_bundle(pd.DataFrame(rows), 11, 2026)
        detail = technician_detail(bundle, "All Technicians")
        self.assertEqual(bundle["totals"]["labour"], 600)
        self.assertEqual(detail["labour"], 100)
        self.assertEqual(detail["spare"], 200)
        self.assertEqual(bundle["technician_summary"].iloc[0]["Labour Collection"], 100)

    def test_excel_exports_are_valid_workbooks(self):
        bundle = build_monthly_bundle(pd.DataFrame([row("E1", "01-11-2026", PREFIX + "1289")]), 11, 2026)
        audit = calculate_missing_jobcards(bundle["source"], PREFIX + "1289", PREFIX + "1290")
        xlsx = create_excel_report(bundle, [{"name": "Rent", "amount": 500}], audit)
        audit_xlsx = create_missing_jobcard_workbook(audit)
        self.assertTrue(xlsx[:2] == b"PK")
        self.assertTrue(audit_xlsx[:2] == b"PK")


if __name__ == "__main__":
    unittest.main()
