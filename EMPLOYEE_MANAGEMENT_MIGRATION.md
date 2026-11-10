# Selva Motors — Employee Management Migration

## Before deployment

1. Make a copy of the existing Google spreadsheet as a backup.
2. Keep the existing `employees` worksheet and its five columns unchanged:
   `User ID`, `Password`, `Employee Name`, `Role`, `Status`.
3. Create these seven new worksheet tabs using the exact names and header order shown in `migration_templates/`:
   - `employee_profiles`
   - `employee_roles`
   - `employee_permissions`
   - `employee_salary`
   - `salary_history`
   - `employee_access_logs`
   - `salary_policies`
4. Each new tab must have exactly the CSV header row as row 1. Do not rename or reorder columns.
5. Optional: add this initial row to `salary_policies` after the header:
   `DEFAULT-30,Default 30-day policy,30,Present Days,admin,YYYY-MM-DDTHH:MM:SS+05:30`
   If omitted, the application defaults to 30 calculation days and `Present Days`.
6. Deploy the complete project folder, install `requirements.txt`, and restart the Streamlit app.
7. Sign in with the existing Admin account. Open **Employee Access Management** and verify roles, employees and access controls before creating staff accounts.
8. Create a test employee, sign in as that employee in a separate browser session, verify only their own profile/salary is visible, then lock the account from Admin and confirm the test session is denied on its next app rerun.

## Storage and security

- The existing `employees` login worksheet is reused; no duplicate login table is created.
- New profile, role, permission, salary, history, policy and audit data are stored in the seven new tabs.
- Profile images are validated as JPG/PNG/WEBP, limited to 2 MB on upload, resized and compressed to a JPEG payload below 38 KB before being stored in `employee_profiles`.
- Restrict direct Google spreadsheet access to the service account and trusted administrators. Employees must not be granted direct spreadsheet access: Google Sheets itself does not enforce per-row employee privacy. The application filters employee profile/salary data before rendering it.
- New passwords are stored as salted PBKDF2-SHA256 hashes. Existing legacy plaintext passwords remain accepted by the preserved login code for compatibility; Admin should reset those passwords to migrate them to hashes.
- Employee creation and salary + salary-history writes use one Sheets `batchUpdate` request. Google Sheets is not a relational database: separate actions such as profile update + audit log are not a full multi-operation transaction, and concurrent creation of the same employee ID can still race. Admin should verify IDs are unique.
- Account status and permissions are rechecked during authenticated app reruns. This adds employee/auth and access-control worksheet reads; it is intentional for server-side lock enforcement. If Google Sheets is unavailable, the app fails closed and blocks the session.

## Salary policy

`Per Day Salary = Monthly Salary / Calculation Days`

`Earned Salary = Per Day Salary × Payable Days`

`Final Salary = Earned Salary + Overtime + Incentives + Bonus - Advance - Deductions`

A policy change is versioned and affects only new salary records. Existing salary snapshots are not recalculated. `Present Days` is the default payable-day policy; `Present + Paid Leave` is available as an alternative. Confirm your company's paid-leave rules before selecting it.

## Rollback

1. Stop the Streamlit deployment.
2. Restore the pre-migration ZIP/project version.
3. Keep the seven new Google Sheets tabs untouched as an archive; do not delete salary or audit records.
4. Restore the spreadsheet backup only if a migration/write damaged existing data. Avoid restoring the entire spreadsheet if it would erase valid invoices or attendance written after the backup.
5. Redeploy the previous project and verify login, invoice entry, attendance and PDF workflows.

## Verification limits

Automated tests use mocked Google Sheets clients. Live service-account permissions, worksheet headers, browser photo rendering, and the actual deployed Streamlit session must be verified in the target deployment before payroll is used in production.
