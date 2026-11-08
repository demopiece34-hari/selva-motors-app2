# SELVA MOTORS ERP — Google Sheets API Call Audit

## Access policy implemented

| Workflow / operation | Permission | Notes |
|---|---|---|
| Login authentication | ALLOWED READ | Reads only `employees` columns A:E. It is called only after the user presses Login. Password values are used for verification and are not put into the authenticated session or UI. |
| Normal business-data read | BLOCKED | Gateway `read_sheet(..., purpose=None)` fails closed. |
| Dashboard / Search / Customer History | BLOCKED | Removed from navigation; direct page functions show a disabled notice and do not read Sheets. |
| Google Sheet / Excel view pages | BLOCKED | No viewer routes remain. |
| Duplicate Upload Finder | BLOCKED | No business-data read is permitted on the page. |
| Reports page open | ALLOWED, zero data reads | Filters and buttons render without calling `read_report_sheet`. |
| Service Report generation | ALLOWED READ | Reads only `invoices`; selected columns are fetched with one `batch_get` for B:C, F:J, L:L, N:N and P:P. |
| Daily Technician Report generation | ALLOWED READ | Reads only `invoices`; selected columns are fetched with one `batch_get` for B:D and F:J. `Total Amount` is not included in the daily PDF. |
| Monthly Attendance Report generation | ALLOWED READ | Reads only `attendance`; selected columns are fetched with one `batch_get` for A:F and I:J, including the existing `Selfie Saved` detail. |
| Attendance save | ALLOWED WRITE | Direct `append_row`; no attendance worksheet content is read first. |
| OCR / invoice save | ALLOWED WRITE | Direct `append_row`; no invoice worksheet content is read first. |
| Manual bill record | ALLOWED WRITE | Direct append to `manual_invoices`. PDF rendering is local. |
| Extra Fittings | No Sheets call | The supplied module is a PDF estimate/print workflow with session-only UI state; it had no Google Sheets worksheet write in the original project, so its existing behavior is retained without inventing a new schema. |
| Delete request submission | ALLOWED WRITE | Direct append to `delete_requests`. |
| Employee creation / password update | ALLOWED WRITE | Direct append or exact `B:E` / `C:E` row update; no employee list is fetched. |
| Delete approval | ALLOWED WRITE | One atomic `spreadsheet.batch_update` deletes the specified invoice row and marks the specified request row Approved; the administrator must verify both row numbers. |
| Automatic sync / periodic refresh | BLOCKED | Legacy sync functions and duplicate page routes were removed. No scheduler, timer, or auto-refresh is registered. |
| Full-sheet clear/rewrite | BLOCKED | `google_write_sheet()` and `write_sheet()` raise `PermissionError`. |

## API-call categories in the runtime audit

- `READ`: worksheet cell data read for authentication or explicit report generation.
- `WRITE`: direct append, targeted range update, row delete, or atomic spreadsheet batch update.
- `META_READ`: spreadsheet / worksheet metadata lookup (`open_by_key`, `worksheet`). These calls do not download business rows. The gateway caches the spreadsheet and worksheet handles for reuse.
- `BLOCKED_READ`: a denied attempt to read business data outside the permitted purposes.

The Admin Panel's API Call Audit tab groups the events by function, operation, sheet, purpose and reason and displays call counts plus the allowed flag. Counters are process-local, not persistent billing telemetry.

## Expected high-level call counts

| User action | Business-data reads | Data writes |
|---|---:|---:|
| Open login page without submitting | 0 | 0 |
| Submit login | 1 employee authentication read | 0 |
| Open an allowed normal write page | 0 | 0 |
| Open Reports | 0 | 0 |
| Generate Service Report | 1 invoice read request | 0 |
| Generate Daily Technician Report | 1 invoice read request | 0 |
| Generate Monthly Attendance Report | 1 attendance read request | 0 |
| Download an already generated report | 0 | 0 |
| Save attendance / invoice / delete request | 0 | 1 append write |
| Create employee | 0 | 1 append write |
| Update employee | 0 | 1 targeted update write |
| Approve delete request | 0 | 1 atomic batch write spanning the invoice and delete-request worksheets |

The batch ranges within each report are sent using a single `batch_get` request when supported by gspread. A metadata lookup may also occur the first time a worksheet is used by a process; it is not a business-row read and the resulting handle is cached. Missing worksheets are not auto-created: the operation fails with a visible error rather than adding a tab or initializing headers unexpectedly.

## Important data-integrity trade-offs

A strict write-only normal workflow cannot verify whether a Job Card Number, invoice, attendance row, employee ID, or delete request already exists elsewhere in the spreadsheet. Google Sheets append is not a conditional unique insert. The uploaded project already contained a `duplicate_exists()` implementation that always returned `False` and an unreachable duplicate approval branch. The updated invoice workflow adds a same-browser-session idempotency guard and clearly tells the user that cross-device duplicate detection is unavailable. Attendance and delete-request retries are also guarded within the signed-in browser session. These guards do **not** guarantee uniqueness across separate devices, browser sessions, or concurrent users.

To keep the no-read policy, employee creation requires an administrator to confirm that the User ID is unique and employee updates / delete approvals require manually verified worksheet row numbers. Delete approval uses one Google Sheets `spreadsheets.batchUpdate` request containing both the invoice row deletion and request-status update, so the two changes are applied together. An administrator must still verify the exact rows before approving.

## Tests and verification scope

Run:

```bash
python -m unittest discover -s tests -v
python -m py_compile app.py google_sheet.py pdf_generator.py report_center.py
```

The tests use a mocked gspread-compatible client and a locally generated PDF. They check denied normal reads, allowed login/report reads, selected report ranges, direct append without reads, targeted writes, multipage PDF output, and removal of `Total Amount` from the daily technician PDF.

No live Google API test was performed because no Google service-account credentials or `SHEET_ID` were supplied in the uploaded project. The API Call Audit tab records gateway-level calls when deployed; it is not a network packet trace of gspread internals.
