# Construction App Technical Deep Dive

This document explains how your app works end-to-end at a technical level:
- how HTML pages interact with Python (Flask),
- how Python interacts with MySQL,
- how data, state, and security move through the system.

---

## 1) High-level architecture

Your app is a classic server-rendered web app with this stack:

- **Frontend (browser)**: HTML templates + CSS + a small JavaScript file for modal behavior.
- **Backend (Flask/Python)**: routes/controllers in `app.py`.
- **Database (MySQL)**: tables for users, employees, projects, schedules, timecards, payroll, payments, etc.

At runtime, the browser never talks to MySQL directly.
It always talks to Flask over HTTP. Flask is the only layer that runs SQL.

---

## 2) Main files and responsibilities

- `app.py`
  - Defines all routes (`/login`, `/employees`, `/payroll`, `/reports`, etc.).
  - Reads form/query data from requests.
  - Runs SQL queries through cursor helpers.
  - Builds response pages with `render_template(...)`.
  - Manages session auth and company scoping.

- `db.py`
  - Creates a shared MySQL connection pool.
  - Exposes context managers:
    - `get_conn()` for transaction-scoped DB connections.
    - `get_cursor()` for convenient cursor usage.
  - Handles commit/rollback automatically.

- `templates/*.html`
  - Jinja2 templates rendered by Flask.
  - `base.html` is layout shell.
  - Feature pages (`employees.html`, `projects.html`, etc.) extend base.
  - Use server-provided variables (e.g., `employees`, `rows`, `payrolls`).

- `static/style.css`
  - Visual styles only.

- `static/app.js`
  - Handles opening/closing modal dialogs in the UI.
  - No API calls; no direct DB access.

---

## 3) Request-response lifecycle (what happens on each click)

When a user clicks a link or submits a form:

1. **Browser sends HTTP request** to Flask route.
2. **Flask route executes** in `app.py`.
3. Route may:
   - read URL query params (`request.args`) for filters/search,
   - read form body (`request.form`) for creates/updates,
   - read session (`session[...]`) to identify current user/company.
4. Route opens DB cursor/connection (`get_cursor` / `get_conn`).
5. Route executes SQL using parameterized placeholders (`%s`) + tuple params.
6. Route either:
   - returns HTML via `render_template(...)`, or
   - redirects to another route after mutation (`redirect(url_for(...))`).
7. Browser receives HTML and renders it.
8. If JS is present, `static/app.js` binds modal click handlers after DOM load.

This pattern repeats across almost every page.

---

## 4) HTML <-> Python interaction details

### 4.1 Template rendering

Flask calls:

- `render_template("employees.html", employees=..., trades=..., unions=...)`
- `render_template("reports.html", rows=..., report_type=..., ...)`

Jinja placeholders in templates (like `{{ employee.Name }}`) are replaced with Python data at render time.

So templates are not static files; they are server-generated views.

### 4.2 Forms and POST actions

In HTML:

- `<form method="post" action="{{ url_for('add_employee') }}">`

In Flask:

- route `@app.route("/employees/add", methods=["POST"])`
- values read from `request.form.get("name")`, etc.

The names of `<input name="...">` fields are the contract between HTML and Python.

### 4.3 Filters/search and GET query strings

In HTML:

- report/timecard/employee filters submit with `method="get"`.

In Flask:

- values read with `request.args.get("start_date")`, `request.args.get("search")`, etc.

These values are then inserted into SQL conditions (parameterized).

### 4.4 Flash messages (feedback path)

On backend:

- `flash("Employee added.", "success")`

In templates (`base.html`):

- `get_flashed_messages(with_categories=true)` renders notification banners.

That is how backend success/error state is surfaced in HTML.

---

## 5) Python <-> Database interaction details

## 5.1 Connection pooling and transactions

`db.py` builds a `MySQLConnectionPool` once, then reuses connections.

- `get_conn()`:
  - yields connection,
  - commits on success,
  - rollbacks on exception,
  - closes connection in `finally`.

- `get_cursor()`:
  - opens a cursor from `get_conn()`,
  - yields it,
  - closes cursor automatically.

This means each route block is transaction-protected without manual commit calls scattered everywhere.

### 5.2 Parameterized queries

Queries use `%s` placeholders:

- `cur.execute("SELECT ... WHERE CompanyID=%s", (company_id,))`

This prevents SQL injection by separating SQL text from data.

### 5.3 Company-level data scoping

After login, `session["company_id"]` is used in many queries:

- employees/projects/timecards/payroll/report queries all filter by company.

This is the app-level multi-tenant boundary: users only see records belonging to their company.

### 5.4 ID generation strategy

`next_id(cursor, table, column, prefix, digits)`:

- reads `MAX(id)` from table,
- increments numeric suffix,
- returns IDs like `E00001`, `PR0001`, etc.

This is app-managed key generation (not DB auto-increment).

---

## 6) Authentication and session mechanics

### 6.1 Login flow

1. User submits username/password from `login.html`.
2. Route `/login` calls `authenticate_user(...)`.
3. Query pulls `User_tbl` + company name.
4. Password check supports:
   - hashed passwords (`check_password_hash`) for new users,
   - plaintext fallback for legacy seed users.
5. On success, Flask session stores:
   - `user_id`, `company_id`, `username`, `company_name`.
6. Browser receives session cookie and uses it on future requests.

### 6.2 Route protection

`@login_required` wrapper:

- if `session["user_id"]` missing -> redirect to `/login`.

`@app.before_request` loads `g.user` from session for template display in sidebar/user info.

---

## 7) Feature-by-feature data flow

## 7.1 Employees

- GET `/employees`
  - optional `search` + `active` filters from query params.
  - SQL builds dynamically with additional `AND` clauses.
  - returns employee list + lookup tables (trade/union).

- POST `/employees/add`, `/employees/<id>/edit`, `/employees/<id>/delete`
  - mutate employee records.
  - redirect back to `/employees` after commit.

## 7.2 Projects + Job Sites

- GET `/projects`
  - optional status filter.
  - loads both project summary and job site list.

- POST routes add/edit/delete project/site.
  - includes safety checks that project belongs to current company.

## 7.3 Assignments

There is no dedicated Assignment table, so assignments are materialized from joins:

- `Timecard` + `Employee` + `Schedule` + `Job_site` + `Project` + `Trade`.

Edit action updates `Schedule` (`SiteID`, `StartDate`, `EndDate`) with company ownership checks.

## 7.4 Timecards

- GET `/timecards` with employee/date filtering.
- POST add/edit/delete timecards.
- Uses joins to show employee/site context in table rows.

## 7.5 Payroll

POST `/payroll`:

1. Reads `start_date`, `end_date`, `hourly_rate`, `deduction`.
2. Validates date range (end cannot be before start).
3. Creates payroll header row in `Payroll`.
4. Aggregates `SUM(tc.Hours)` by employee in date range.
5. Inserts one `Payment` row per employee amount.

GET `/payroll`:

- returns payroll history with aggregate totals.

## 7.6 Reports + CSV export

GET `/reports`:

- accepts report type and filters.
- runs one of multiple SQL shapes (`hours_by_site`, `employee_hours`, `pay_by_site`).
- validates date range before querying.

GET `/reports/export`:

- reruns report query for CSV.
- writes output with Python `csv.writer`.
- returns `Response(..., mimetype="text/csv")` download.

---

## 8) Frontend behavior (JS and CSS role)

`static/app.js` only handles modal UX:

- buttons with `data-open-modal="modal-id"` add `.open` class,
- close buttons or backdrop clicks remove `.open`.

No fetch/AJAX layer is used; every data mutation is traditional form submit + full page reload.

So all business logic remains server-side in Flask.

---

## 9) Validation and error handling model

- Date parsing uses `safe_date(...)` (`YYYY-MM-DD` -> Python `date`).
- Date-range guard blocks invalid ranges (end before start) in payroll and reports/export.
- Generic global error handler:
  - `@app.errorhandler(Exception)` renders `error.html` and returns HTTP 500.

Because this handler is broad, any unhandled Python/DB exception becomes an error page instead of crashing the process.

---

## 10) Security model in practice

- **Session-based auth** for protected pages.
- **Password hashing** for new users (`werkzeug.security`).
- **Parameterized SQL** to reduce injection risk.
- **Company scoping** on many queries to isolate tenant data.
- Optional DB least-privilege user in `init_db_security.sql`.

Important note:
- App-level company filtering is strong but must be applied consistently on every route/query.
- Defense-in-depth can be improved with DB-level row security patterns or stricter ownership checks in every mutation path.

---

## 11) Why this app feels simple but is still full-stack

Even without a heavy frontend framework, this is complete full-stack behavior:

- UI forms and template rendering (view layer),
- Python route/controller logic (application layer),
- transactional SQL with joins/aggregates (data layer),
- session auth and permissions (security layer).

It is a server-rendered MVC-ish architecture where Flask route functions act as controllers, Jinja templates are views, and MySQL tables are the model/data source.

---

## 12) End-to-end example: "Add employee"

1. User opens Employees page (`GET /employees`) -> Flask renders `employees.html`.
2. User fills modal form and submits (`POST /employees/add`).
3. Flask reads form fields from `request.form`.
4. Flask checks company context from session.
5. Flask inserts row into `Employee` using parameterized SQL.
6. Transaction commits via `get_conn()`.
7. Flask flashes success message and redirects to `/employees`.
8. Browser follows redirect and re-renders updated employee table.

This exact pattern is reused throughout most create/update/delete flows.

---

## 13) Operational behavior and deployment assumptions

- Environment variables provide DB host/user/password/database and secret key.
- App expects shared MySQL instance for multi-user data consistency.
- Connection pool size is configurable (`DB_POOL_SIZE`).
- Works in local dev with Flask debug server; production should use WSGI server (gunicorn/uwsgi/waitress depending platform).

---

## 14) Suggested future technical improvements

- Add formal service/repository layers to reduce route size in `app.py`.
- Add schema-level constraints/checks for date logic where feasible.
- Add CSRF protection for all forms (Flask-WTF or custom token middleware).
- Add automated tests for route auth, company isolation, and payroll/report calculations.
- Introduce structured logging and per-route exception granularity instead of one global catch-all.

---

If you want, I can also generate a second doc that maps **every route to every SQL query** in a table for debugging and code reviews.
