from google_sheet import GoogleSheetsAccess, reset_api_call_audit, get_api_call_audit_summary


INVOICE_SCHEMA = [
    "Entry ID", "Date", "Technician Name", "User ID", "Invoice Number",
    "Job Card Number", "Registration Number", "Bike Model", "Service Type",
    "Labour Amount", "Spare Parts Count", "Spare Amount", "Oil Change Status",
    "Total Amount", "Entry Type", "Status", "Oil Amount",
]


def _column_index(label):
    value = 0
    for char in label:
        value = value * 26 + ord(char.upper()) - 64
    return value - 1


class FakeWorksheet:
    def __init__(self):
        self.batch_get_calls = 0
        self.get_calls = 0
        self.rows = [[f"v{index}" for index in range(len(INVOICE_SCHEMA))]]
        self.headers = INVOICE_SCHEMA

    def batch_get(self, ranges):
        self.batch_get_calls += 1
        result = []
        for item in ranges:
            start, end = item.split(":")
            left, right = _column_index(start), _column_index(end)
            matrix = [self.headers[left:right + 1]]
            matrix.extend([row[left:right + 1] for row in self.rows])
            result.append(matrix)
        return result

    def get(self, range_name):
        self.get_calls += 1
        return [self.headers]


class FakeSpreadsheet:
    def __init__(self, worksheet):
        self.worksheet_obj = worksheet

    def worksheet(self, name):
        assert name == "invoices"
        return self.worksheet_obj


class FakeClient:
    def __init__(self, spreadsheet):
        self.spreadsheet = spreadsheet

    def open_by_key(self, spreadsheet_id):
        assert spreadsheet_id == "test-sheet-id"
        return self.spreadsheet


def test_non_contiguous_report_columns_use_one_batch_get_request():
    worksheet = FakeWorksheet()
    client = FakeClient(FakeSpreadsheet(worksheet))
    gateway = GoogleSheetsAccess(
        spreadsheet_id="test-sheet-id",
        schemas={"invoices": INVOICE_SCHEMA},
        client=client,
    )
    selected = [
        "Entry ID", "Date", "Technician Name", "User ID", "Job Card Number",
        "Registration Number", "Service Type", "Labour Amount", "Spare Parts Count",
        "Spare Amount", "Oil Change Status", "Oil Amount", "Total Amount", "Status",
    ]
    reset_api_call_audit()
    frame = gateway.read_sheet("invoices", purpose="report", columns=selected)
    assert worksheet.batch_get_calls == 1
    assert worksheet.get_calls == 0
    assert list(frame.columns) == selected
    read_events = [entry for entry in get_api_call_audit_summary() if entry["Operation"] == "READ"]
    assert len(read_events) == 1
    assert read_events[0]["Function"] == "worksheet.batch_get"
