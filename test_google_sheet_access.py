import unittest

from google_sheet import (
    GoogleSheetsAccess,
    get_api_call_audit,
    get_api_call_audit_summary,
    reset_api_call_audit,
)


SCHEMAS = {
    "employees": ["User ID", "Password", "Employee Name", "Role", "Status"],
    "invoices": [
        "Entry ID", "Date", "Technician Name", "User ID", "Invoice Number",
        "Job Card Number", "Registration Number", "Bike Model", "Service Type",
        "Labour Amount", "Spare Parts Count", "Spare Amount", "Oil Change Status",
        "Total Amount", "Entry Type", "Status",
    ],
    "attendance": [
        "Date", "Time", "User ID", "Technician Name", "Role", "Attendance Status",
        "Latitude", "Longitude", "Distance Meter", "Selfie Saved",
    ],
    "delete_requests": ["Request ID", "Date", "Time", "Entry ID", "Technician Name", "User ID", "Reason", "Request Status", "Admin Action Date"],
}


class FakeWorksheet:
    def __init__(self, rows, worksheet_id=1):
        self.rows = [list(row) for row in rows]
        self.id = worksheet_id
        self.get_calls = []
        self.batch_get_calls = []
        self.append_calls = []
        self.update_calls = []
        self.delete_calls = []

    @staticmethod
    def _col_number(text):
        value = 0
        for char in text:
            value = value * 26 + (ord(char.upper()) - 64)
        return value

    def _get_range(self, range_name):
        start, end = range_name.split(":")
        start_n = self._col_number(start)
        end_n = self._col_number(end)
        return [row[start_n - 1:end_n] for row in self.rows]

    def get(self, range_name):
        self.get_calls.append(range_name)
        return self._get_range(range_name)

    def batch_get(self, ranges):
        self.batch_get_calls.append(list(ranges))
        return [self._get_range(range_name) for range_name in ranges]

    def append_row(self, values, **kwargs):
        self.append_calls.append((list(values), kwargs))
        self.rows.append(list(values))

    def update(self, range_name, values, **kwargs):
        self.update_calls.append((range_name, values, kwargs))

    def delete_rows(self, row_number):
        self.delete_calls.append(row_number)


class FakeSpreadsheet:
    def __init__(self, worksheets):
        self.worksheets = worksheets
        self.batch_update_calls = []

    def worksheet(self, name):
        return self.worksheets[name]

    def batch_update(self, body):
        self.batch_update_calls.append(body)


class FakeClient:
    def __init__(self, spreadsheet):
        self.spreadsheet = spreadsheet
        self.open_calls = []

    def open_by_key(self, key):
        self.open_calls.append(key)
        return self.spreadsheet


class GoogleSheetsAccessTests(unittest.TestCase):
    def setUp(self):
        reset_api_call_audit()
        employees = FakeWorksheet([
            SCHEMAS["employees"],
            ["hari", "legacy-pass", "Hari", "Admin", "Active"],
        ])
        invoices = FakeWorksheet([
            SCHEMAS["invoices"],
            ["E-1", "07-11-2026", "Mohan", "mohan", "INV-1", "JC-1", "TN01AA1234", "Splendor", "Paid Service", "300", "2", "500", "Yes", "800", "OCR Upload", "Active"],
        ])
        attendance = FakeWorksheet([
            SCHEMAS["attendance"],
            ["07-11-2026", "09:00 AM", "mohan", "Mohan", "Technician", "Present", "12.0", "80.0", "20", "No"],
        ])
        delete_requests = FakeWorksheet([SCHEMAS["delete_requests"]])
        self.worksheets = {
            "employees": employees,
            "invoices": invoices,
            "attendance": attendance,
            "delete_requests": delete_requests,
        }
        self.spreadsheet = FakeSpreadsheet(self.worksheets)
        self.client = FakeClient(self.spreadsheet)
        self.gateway = GoogleSheetsAccess("FAKE-SHEET-ID", SCHEMAS, client=self.client)

    def test_normal_business_read_is_blocked_before_sheet_data_access(self):
        with self.assertRaises(PermissionError):
            self.gateway.read_sheet("invoices", purpose=None)
        self.assertEqual(self.worksheets["invoices"].get_calls, [])
        self.assertEqual(self.worksheets["invoices"].batch_get_calls, [])
        self.assertEqual(get_api_call_audit()[-1]["operation"], "BLOCKED_READ")

    def test_authentication_read_is_only_employees_and_five_columns(self):
        frame = self.gateway.read_sheet("employees", purpose="auth")
        self.assertEqual(frame.iloc[0]["User ID"], "hari")
        self.assertEqual(list(frame.columns), SCHEMAS["employees"])
        self.assertEqual(self.worksheets["employees"].get_calls, ["A:E"])
        self.assertEqual(self.worksheets["invoices"].get_calls, [])
        self.assertEqual(self.worksheets["attendance"].get_calls, [])

    def test_report_reads_only_the_selected_sheet_and_columns_in_one_batch(self):
        columns = ["Date", "Technician Name", "Job Card Number", "Labour Amount", "Total Amount"]
        frame = self.gateway.read_sheet("invoices", purpose="report", columns=columns)
        self.assertEqual(list(frame.columns), columns)
        self.assertEqual(frame.iloc[0]["Job Card Number"], "JC-1")
        self.assertEqual(len(self.worksheets["invoices"].batch_get_calls), 1)
        self.assertEqual(self.worksheets["invoices"].batch_get_calls[0], ["B:C", "F:F", "J:J", "N:N"])
        self.assertEqual(self.worksheets["attendance"].get_calls, [])
        self.assertEqual(self.worksheets["attendance"].batch_get_calls, [])

    def test_report_cannot_read_employee_or_unknown_sheet_or_default_to_full_sheet(self):
        with self.assertRaises(PermissionError):
            self.gateway.read_sheet("employees", purpose="report", columns=["User ID"])
        with self.assertRaises(PermissionError):
            self.gateway.read_sheet("manual_invoices", purpose="report", columns=["Date"])
        with self.assertRaises(PermissionError):
            self.gateway.read_sheet("invoices", purpose="report")

    def test_append_is_direct_write_without_read_or_rewrite(self):
        ok, message = self.gateway.append_row("invoices", {"Entry ID": "E-2", "Date": "07-11-2026"})
        self.assertTrue(ok, message)
        self.assertEqual(len(self.worksheets["invoices"].append_calls), 1)
        self.assertEqual(self.worksheets["invoices"].get_calls, [])
        self.assertEqual(self.worksheets["invoices"].batch_get_calls, [])
        events = get_api_call_audit()
        self.assertTrue(any(event["function"] == "append_row" and event["operation"] == "WRITE" for event in events))
        self.assertFalse(any(event["operation"] in {"worksheet.get", "worksheet.batch_get"} for event in events))

    def test_range_update_and_delete_are_write_operations(self):
        self.assertTrue(self.gateway.update_range("employees", "C2:E2", [["Hari", "Admin", "Active"]])[0])
        self.assertTrue(self.gateway.delete_row("invoices", 2)[0])
        self.assertEqual(self.worksheets["employees"].get_calls, [])
        self.assertEqual(self.worksheets["invoices"].get_calls, [])
        self.assertEqual(self.worksheets["invoices"].delete_calls, [2])
        self.assertFalse(self.gateway.update_range("invoices", "A:Z", [["overwrite"]])[0])
        self.assertFalse(self.gateway.update_range("delete_requests", "C2:E2", [["bad", "range", "target"]])[0])

    def test_delete_approval_is_one_atomic_batch_write_without_data_reads(self):
        ok, message = self.gateway.approve_delete_request(7, 5, "07-11-2026 10:30 AM")
        self.assertTrue(ok, message)
        self.assertEqual(len(self.spreadsheet.batch_update_calls), 1)
        requests = self.spreadsheet.batch_update_calls[0]["requests"]
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0]["deleteDimension"]["range"]["sheetId"], self.worksheets["invoices"].id)
        self.assertEqual(requests[0]["deleteDimension"]["range"]["startIndex"], 6)
        update = requests[1]["updateCells"]
        self.assertEqual(update["range"]["sheetId"], self.worksheets["delete_requests"].id)
        self.assertEqual(update["range"]["startColumnIndex"], 7)
        self.assertEqual(update["rows"][0]["values"][0]["userEnteredValue"]["stringValue"], "Approved")
        self.assertEqual(self.worksheets["invoices"].get_calls, [])
        self.assertEqual(self.worksheets["delete_requests"].get_calls, [])
        self.assertEqual(get_api_call_audit()[-1]["function"], "spreadsheet.batch_update")

    def test_unknown_sheet_cannot_be_written_and_row_delete_is_narrowly_allowlisted(self):
        ok, message = self.gateway.append_row("unknown", {"x": 1})
        self.assertFalse(ok)
        self.assertIn("append blocked", message.lower())
        ok, message = self.gateway.delete_row("employees", 2)
        self.assertFalse(ok)
        self.assertIn("row delete blocked", message.lower())


if __name__ == "__main__":
    unittest.main()
