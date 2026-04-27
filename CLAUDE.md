# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

**BLUE** is a construction management and payroll web application. It manages employees, projects, job sites, schedules, timecards, and payroll for construction companies. It is multi-tenant — each company's data is fully isolated by `CompanyID`.

## Running the App

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (debug mode, port 5000)
python app.py

# Production (as deployed)
gunicorn --bind "0.0.0.0:8080" --workers 1 --timeout 120 app:app
```

Environment variables are loaded from `.env`. Required vars: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`.

There is no test suite.

## Architecture

### Entry Points
- `app.py` — all Flask routes (~30 endpoints), session auth, flash messaging, rate limiting
- `db.py` — MySQL connection pooling via `mysql-connector-python`
- `migrations.py` — schema migrations that run automatically on first request via `@app.before_request`

### Two Auth Systems
1. **Company users** — log in at `/login`, scoped to their `CompanyID`; all queries must include `WHERE CompanyID = session['company_id']`
2. **Admin** — logs in at `/admin/login` with credentials from `.env`; manages company records across tenants

### Database Layer
- No ORM. All queries are raw SQL via `db.py` connection pool.
- Concurrency: sequential IDs are generated with `LOCK TABLES` in the `next_id()` helper inside `app.py`.
- Stored functions live in the DB: `calc_gross_pay()`, `employee_hours()`, `pay_by_site()` — these are created by `migrations.py` if missing.
- CHECK constraints on hours (0 < Hours ≤ 24), deductions, and date ordering are also enforced at the DB level via migrations.

### Frontend
- Jinja2 templates in `templates/`, base layout in `base.html`
- Vanilla JS in `static/app.js` (modal handling, form submission, dynamic UI)
- Styles in `static/style.css`

### Reports & CSV Export
- Three report types: `hours_by_site`, `employee_hours`, `pay_by_site`
- Export route at `/reports/export` streams CSV with proper `Content-Disposition` header

## Deployment

Deployed on Railway via `Dockerfile`. The `Procfile` and `railway.json` configure the build. Port defaults to `8080` via the `PORT` env var. The Docker entrypoint (`docker-entrypoint.sh`) runs migrations before starting gunicorn.

## Key Conventions

- All management routes (`/employees`, `/projects`, `/sites`, etc.) use `GET` to render pages and `POST` to handle form submissions on the same URL.
- Flash categories used: `success`, `danger`, `warning` — rendered in `base.html`.
- Date inputs are parsed defensively; invalid ranges fall back to current month defaults.
- The `init_db_security.sql` file documents intent to run the app under a least-privilege DB user (`construction_app`) rather than root.

## Initial app design 
Check @Minestone 2 (1).pdf and @Report.pdf for initial app design plans for features and also SQL to be implemented. 

## Coding Rules 
- Code should be simpler rather than more complex, but still effecient/accurate. Should be the level of a college student 
    - Do not use coalesce function for any sql 
    - This includes comments - make them brief and without neat formatting, just simple lines