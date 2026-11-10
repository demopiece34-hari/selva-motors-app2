# Employee Management — Test Report

## Automated checks

- Python syntax compilation: `app.py`, all root modules, `ui_modules/*.py`, and `tests/*.py` — passed.
- Unit tests: **28 passed, 0 failed**.
- Salary arithmetic example: ₹18,000 / 30 = ₹600 per day; 26 payable days = ₹15,600 earned — passed.
- Salary component formula, invalid day bounds, role-based allow/deny, disabled custom role fail-closed, employee + profile atomic append request — passed.
- Existing authentication, report-read restrictions, Google Sheets access gateway, PDF generation and architecture guard tests — passed.

## Manual deployment checks still required

The build environment does not contain the target Google Sheet ID/service-account credentials or a running deployed Streamlit session. Before production use, verify:

1. All seven new worksheet tabs and exact headers are present.
2. Admin can create an employee and profile photo; a duplicate ID is rejected against the loaded employee snapshot.
3. A non-admin cannot open Employee Access Management or write employee/role/permission sheets.
4. A locked/suspended employee is denied on their next app rerun.
5. A custom role and individual permission override show only allowed modules.
6. Employee A cannot see Employee B's salary or profile photo unless photo-view access is granted.
7. A payroll-authorized user can create salary and history; an ordinary employee cannot access payroll controls.
8. Existing invoice OCR, invoice numbering, attendance, reports and PDFs still work with the live Google service account.

## Important limitations

- Google Sheets has no row-level security. The service-account spreadsheet must not be shared directly with employee accounts.
- The application reads salary worksheet data on the server and filters by the signed-in employee before rendering. Only Admin/payroll-authorized users see the company-wide salary workspace.
- Employee uniqueness can still race if two administrators create the same ID concurrently; verify employee IDs before creation.
- Employee creation and salary/history append pairs use a single Sheets batch update. Other multi-step operations (such as a profile update plus audit event) are not one transaction.
- Account and permission checks run on authenticated app reruns. A lock is enforced on the next rerun; it cannot cancel a request already executing.
- Legacy plaintext employee passwords remain accepted for compatibility until Admin resets them to PBKDF2 hashes.
