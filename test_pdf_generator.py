import tempfile
import unittest
from pathlib import Path

import pandas as pd
import pdfplumber

from pdf_generator import format_inr, generate_professional_report_pdf


class PdfGeneratorTests(unittest.TestCase):
    def test_daily_report_omits_total_amount_and_generates_pages(self):
        frame = pd.DataFrame([
            {
                "Technician Name": "Mohan",
                "Date": "07-11-2026",
                "Job Card Number": f"JC-{index:03d}",
                "Registration Number": f"TN01AA{index:04d}",
                "Bike Model": "Hero Splendor Plus",
                "Service Type": "Paid Service",
                "Labour Amount": 300,
                "Total Amount": 1200,
            }
            for index in range(1, 100)
        ])
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "daily.pdf"
            result = generate_professional_report_pdf(
                frame,
                "SELVA MOTORS DAILY TECHNICIAN REPORT",
                path,
                metadata={"Date": "07-11-2026", "Technician": "Mohan"},
                kpis=[("Vehicle Entries", len(frame)), ("Total Labour Amount", 300 * len(frame))],
                report_kind="daily_technician",
            )
            self.assertTrue(Path(result).exists())
            with pdfplumber.open(result) as pdf:
                self.assertGreater(len(pdf.pages), 1)
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            self.assertIn("Job Card", text)
            self.assertIn("Number", text)
            self.assertIn("Total Labour Amount", text)
            self.assertNotIn("Total Amount", text)
            self.assertIn("SELVA MOTORS", text)
            self.assertIn("Page 1", text)

    def test_indian_rupee_grouping(self):
        self.assertTrue(format_inr(1234567.89).endswith("12,34,567.89"))
        self.assertTrue(format_inr(12345678.9).endswith("1,23,45,678.90"))
        self.assertTrue(format_inr(-123456.0).endswith("-1,23,456.00"))

    def test_wide_service_report_uses_landscape_a4(self):
        frame = pd.DataFrame([{
            "Technician Name": "Mohan", "Date": "07-11-2026", "Job Card Number": "JC-1001",
            "Registration Number": "TN01AB1234", "Bike Model": "Hero Splendor Plus",
            "Service Type": "Paid Service", "Labour Amount": 350, "Spare Amount": 725,
            "Total Amount": 1075, "Status": "Complete",
        }])
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "service.pdf"
            generate_professional_report_pdf(
                frame, "SELVA MOTORS SERVICE REPORT", path,
                metadata={"Technician": "All Technicians"},
                kpis=[("Vehicle Entries", 1), ("Total Revenue", 1075)],
                report_kind="service",
            )
            with pdfplumber.open(path) as pdf:
                self.assertGreater(pdf.pages[0].width, pdf.pages[0].height)
                text = pdf.pages[0].extract_text() or ""
            self.assertIn("Registration", text)
            self.assertIn("Number", text)
            self.assertIn("Total Amount", text)



if __name__ == "__main__":
    unittest.main()
