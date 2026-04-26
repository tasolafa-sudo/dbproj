import logging
from db import get_conn

logger = logging.getLogger(__name__)


def ensure_project_name_column():
    """Add ProjectName column to Project table if not present (supports Milestone 2 UI)."""
    try:
        with get_conn() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'Project'
                  AND COLUMN_NAME = 'ProjectName'
                """
            )
            if cur.fetchone()["cnt"] == 0:
                cur.execute(
                    "ALTER TABLE Project ADD COLUMN ProjectName VARCHAR(100) NOT NULL DEFAULT '' AFTER CompanyID"
                )
            cur.close()
    except Exception as exc:
        logger.warning("Could not add ProjectName column: %s", exc)


def ensure_db_functions():
    """Create stored functions from the report (advanced PL/SQL) if they don't exist."""
    functions = [
        (
            "calc_gross_pay",
            """
            CREATE FUNCTION calc_gross_pay(
                p_employee_id CHAR(6),
                p_start DATE,
                p_end DATE,
                p_hourly_rate DECIMAL(10,2)
            )
            RETURNS DECIMAL(10,2)
            READS SQL DATA
            DETERMINISTIC
            BEGIN
                RETURN (
                    SELECT CASE WHEN SUM(Hours) IS NULL THEN 0
                                ELSE ROUND(SUM(Hours) * p_hourly_rate, 2)
                           END
                    FROM Timecard
                    WHERE EmployeeID = p_employee_id
                      AND Date BETWEEN p_start AND p_end
                );
            END
            """,
        ),
        (
            "employee_hours",
            """
            CREATE FUNCTION employee_hours(
                p_employee_id CHAR(6),
                p_start DATE,
                p_end DATE
            )
            RETURNS DECIMAL(10,2)
            READS SQL DATA
            DETERMINISTIC
            BEGIN
                RETURN (
                    SELECT CASE WHEN SUM(Hours) IS NULL THEN 0
                                ELSE SUM(Hours)
                           END
                    FROM Timecard
                    WHERE EmployeeID = p_employee_id
                      AND Date BETWEEN p_start AND p_end
                );
            END
            """,
        ),
        (
            "pay_by_site",
            """
            CREATE FUNCTION pay_by_site(
                p_employee_id CHAR(6),
                p_site_id CHAR(6),
                p_start DATE,
                p_end DATE,
                p_hourly_rate DECIMAL(10,2)
            )
            RETURNS DECIMAL(10,2)
            READS SQL DATA
            DETERMINISTIC
            BEGIN
                RETURN (
                    SELECT CASE WHEN SUM(tc.Hours) IS NULL THEN 0
                                ELSE ROUND(SUM(tc.Hours) * p_hourly_rate, 2)
                           END
                    FROM Timecard tc
                    JOIN Schedule s ON tc.ScheduleID = s.ScheduleID
                    WHERE tc.EmployeeID = p_employee_id
                      AND s.SiteID = p_site_id
                      AND tc.Date BETWEEN p_start AND p_end
                );
            END
            """,
        ),
    ]
    try:
        with get_conn() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                "SELECT ROUTINE_NAME FROM information_schema.ROUTINES "
                "WHERE ROUTINE_SCHEMA = DATABASE() AND ROUTINE_TYPE = 'FUNCTION'"
            )
            existing = {row["ROUTINE_NAME"] for row in cur.fetchall()}
            for name, ddl in functions:
                if name not in existing:
                    cur.execute(ddl.strip())
            cur.close()
    except Exception as exc:
        logger.warning("Could not create stored functions: %s", exc)


def ensure_db_constraints():
    """Add CHECK constraints from the report if not already present."""
    constraints = [
        ("Timecard", "chk_timecard_hours", "Hours > 0 AND Hours <= 24"),
        ("Payment", "chk_payment_deduction", "Deduction >= 0 AND Deduction <= Amount"),
        ("Payroll", "chk_payroll_dates", "PeriodStart <= PeriodEnd"),
        ("Schedule", "chk_schedule_dates", "StartDate <= EndDate"),
    ]
    try:
        with get_conn() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT CONSTRAINT_NAME
                FROM information_schema.TABLE_CONSTRAINTS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND CONSTRAINT_TYPE = 'CHECK'
                """
            )
            existing = {row["CONSTRAINT_NAME"] for row in cur.fetchall()}
            for table, name, expr in constraints:
                if name not in existing:
                    try:
                        cur.execute(f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({expr})")
                    except Exception as inner:
                        logger.warning("Could not add constraint %s: %s", name, inner)
            cur.close()
    except Exception as exc:
        logger.warning("Could not add CHECK constraints: %s", exc)
