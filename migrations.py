import logging
from db import get_conn

logger = logging.getLogger(__name__)


def ensure_project_name_column():
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


def ensure_db_procedures():
    procedures = [
        (
            "login",
            """
            CREATE PROCEDURE login(IN p_username VARCHAR(50))
            BEGIN
                SELECT u.UserID, u.CompanyID, u.Username, u.Password, c.CompanyName
                FROM User_tbl u
                JOIN Company c ON c.CompanyID = u.CompanyID
                WHERE u.Username = p_username;
            END
            """,
        ),
        (
            "DisplayProjects",
            """
            CREATE PROCEDURE DisplayProjects(
                IN p_company_id CHAR(6),
                IN p_search VARCHAR(100),
                IN p_status_filter TINYINT
            )
            BEGIN
                SELECT p.ProjectID, p.ProjectName, p.Status,
                       COUNT(js.SiteID) AS SiteCount
                FROM Project p
                LEFT JOIN Job_site js ON js.ProjectID = p.ProjectID
                WHERE p.CompanyID = p_company_id
                  AND (p_search IS NULL OR p.ProjectName LIKE CONCAT('%', p_search, '%')
                       OR p.ProjectID LIKE CONCAT('%', p_search, '%'))
                  AND (p_status_filter IS NULL OR p.Status = p_status_filter)
                GROUP BY p.ProjectID, p.ProjectName, p.Status
                ORDER BY p.ProjectID;
            END
            """,
        ),
        (
            "DisplayProjectSiteSum",
            """
            CREATE PROCEDURE DisplayProjectSiteSum(IN p_project_id CHAR(6))
            BEGIN
                SELECT SiteID, SiteName, Location
                FROM Job_site
                WHERE ProjectID = p_project_id;
            END
            """,
        ),
        (
            "GetEmployees",
            """
            CREATE PROCEDURE GetEmployees(
                IN p_company_id CHAR(6),
                IN p_search VARCHAR(100),
                IN p_active_filter TINYINT
            )
            BEGIN
                SELECT e.EmployeeID, e.Name, e.Active, e.UnionID, e.TradeID,
                       t.TradeName, u.UnionName
                FROM Employee e
                JOIN Trade t ON e.TradeID = t.TradeID
                LEFT JOIN Union_tbl u ON e.UnionID = u.UnionID
                WHERE e.CompanyID = p_company_id
                  AND (p_search IS NULL OR e.Name LIKE CONCAT('%', p_search, '%'))
                  AND (p_active_filter IS NULL OR e.Active = p_active_filter)
                ORDER BY e.Name;
            END
            """,
        ),
        (
            "GetAssignments",
            """
            CREATE PROCEDURE GetAssignments(IN p_company_id CHAR(6))
            BEGIN
                SELECT DISTINCT e.EmployeeID, e.Name AS EmployeeName, t.TradeName,
                       s.ScheduleID, js.SiteID, js.SiteName, p.ProjectID,
                       s.StartDate, s.EndDate, p.Status AS ProjectStatus
                FROM Timecard tc
                JOIN Employee e ON e.EmployeeID = tc.EmployeeID
                JOIN Trade t ON t.TradeID = e.TradeID
                JOIN Schedule s ON s.ScheduleID = tc.ScheduleID
                JOIN Job_site js ON js.SiteID = s.SiteID
                JOIN Project p ON p.ProjectID = js.ProjectID
                WHERE e.CompanyID = p_company_id
                ORDER BY e.Name, s.StartDate;
            END
            """,
        ),
        (
            "GetTimecards",
            """
            CREATE PROCEDURE GetTimecards(
                IN p_company_id CHAR(6),
                IN p_employee_id CHAR(6),
                IN p_date_filter DATE
            )
            BEGIN
                SELECT tc.TimecardID, tc.ScheduleID, tc.EmployeeID, tc.Date, tc.Hours,
                       e.Name AS EmployeeName, js.SiteID, js.SiteName, p.ProjectID
                FROM Timecard tc
                JOIN Employee e ON e.EmployeeID = tc.EmployeeID
                JOIN Schedule s ON s.ScheduleID = tc.ScheduleID
                JOIN Job_site js ON js.SiteID = s.SiteID
                JOIN Project p ON p.ProjectID = js.ProjectID
                WHERE e.CompanyID = p_company_id
                  AND (p_employee_id IS NULL OR tc.EmployeeID = p_employee_id)
                  AND (p_date_filter IS NULL OR tc.Date = p_date_filter)
                ORDER BY tc.Date DESC, e.Name;
            END
            """,
        ),
        (
            "GetPayroll",
            """
            CREATE PROCEDURE GetPayroll(
                IN p_company_id CHAR(6),
                IN p_filter_start DATE,
                IN p_filter_end DATE
            )
            BEGIN
                SELECT pr.PayrollID, pr.PeriodStart, pr.PeriodEnd,
                       COUNT(DISTINCT p.EmployeeID) AS num_employees,
                       SUM(p.Amount) AS total_gross,
                       SUM(p.Amount - p.Deduction) AS total_net,
                       (SELECT IFNULL(SUM(tc.Hours), 0)
                        FROM Timecard tc
                        JOIN Employee e2 ON e2.EmployeeID = tc.EmployeeID
                        WHERE e2.CompanyID = pr.CompanyID
                          AND tc.Date BETWEEN pr.PeriodStart AND pr.PeriodEnd
                       ) AS total_hours
                FROM Payroll pr
                LEFT JOIN Payment p ON p.PayrollID = pr.PayrollID
                WHERE pr.CompanyID = p_company_id
                  AND (p_filter_start IS NULL OR pr.PeriodStart >= p_filter_start)
                  AND (p_filter_end IS NULL OR pr.PeriodEnd <= p_filter_end)
                GROUP BY pr.PayrollID, pr.PeriodStart, pr.PeriodEnd
                ORDER BY pr.PeriodEnd DESC;
            END
            """,
        ),
        (
            "GetReports",
            """
            CREATE PROCEDURE GetReports(
                IN p_company_id CHAR(6),
                IN p_start_date DATE,
                IN p_end_date DATE,
                IN p_employee_id CHAR(6)
            )
            BEGIN
                SELECT e.EmployeeID, e.Name, t.TradeName,
                       employee_hours(e.EmployeeID, p_start_date, p_end_date) AS TotalHours,
                       COUNT(DISTINCT s.SiteID) AS NumSites
                FROM Timecard tc
                JOIN Employee e ON e.EmployeeID = tc.EmployeeID
                JOIN Trade t ON t.TradeID = e.TradeID
                JOIN Schedule s ON s.ScheduleID = tc.ScheduleID
                WHERE e.CompanyID = p_company_id
                  AND tc.Date BETWEEN p_start_date AND p_end_date
                  AND (p_employee_id IS NULL OR e.EmployeeID = p_employee_id)
                GROUP BY e.EmployeeID, e.Name, t.TradeName
                ORDER BY e.Name;
            END
            """,
        ),
        (
            "create_account",
            """
            CREATE PROCEDURE create_account(
                IN p_user_id CHAR(6),
                IN p_company_id CHAR(6),
                IN p_username VARCHAR(50),
                IN p_password VARCHAR(255)
            )
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM User_tbl WHERE Username = p_username) THEN
                    INSERT INTO User_tbl (UserID, CompanyID, Username, Password)
                    VALUES (p_user_id, p_company_id, p_username, p_password);
                END IF;
            END
            """,
        ),
        (
            "add_employee",
            """
            CREATE PROCEDURE add_employee(
                IN p_employee_id CHAR(6),
                IN p_company_id CHAR(6),
                IN p_union_id CHAR(6),
                IN p_trade_id CHAR(6),
                IN p_name VARCHAR(50),
                IN p_active BOOLEAN
            )
            BEGIN
                INSERT INTO Employee (EmployeeID, CompanyID, UnionID, TradeID, Name, Active)
                VALUES (p_employee_id, p_company_id, p_union_id, p_trade_id, p_name, p_active);
            END
            """,
        ),
        (
            "add_project",
            """
            CREATE PROCEDURE add_project(
                IN p_project_id CHAR(6),
                IN p_company_id CHAR(6),
                IN p_project_name VARCHAR(100),
                IN p_status BOOLEAN
            )
            BEGIN
                INSERT INTO Project (ProjectID, CompanyID, ProjectName, Status)
                VALUES (p_project_id, p_company_id, p_project_name, p_status);
            END
            """,
        ),
        (
            "run_payroll",
            """
            CREATE PROCEDURE run_payroll(
                IN p_payroll_id CHAR(6),
                IN p_company_id CHAR(6),
                IN p_start DATE,
                IN p_end DATE,
                IN p_hourly_rate DECIMAL(10,2)
            )
            BEGIN
                DECLARE v_done INT DEFAULT 0;
                DECLARE v_emp_id CHAR(6);
                DECLARE v_union_due DECIMAL(10,2);
                DECLARE v_amount DECIMAL(10,2);
                DECLARE v_payment_id CHAR(6);
                DECLARE v_counter INT DEFAULT 0;
                DECLARE v_base INT DEFAULT 0;

                DECLARE emp_cur CURSOR FOR
                    SELECT DISTINCT tc.EmployeeID, IFNULL(u.Due, 0) AS union_due
                    FROM Timecard tc
                    JOIN Employee e ON e.EmployeeID = tc.EmployeeID
                    LEFT JOIN Union_tbl u ON u.UnionID = e.UnionID
                    WHERE e.CompanyID = p_company_id
                      AND tc.Date BETWEEN p_start AND p_end;

                DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = 1;

                SELECT IFNULL(MAX(CAST(SUBSTRING(PaymentID, 3) AS UNSIGNED)), 0)
                INTO v_base FROM Payment;

                OPEN emp_cur;
                emp_loop: LOOP
                    FETCH emp_cur INTO v_emp_id, v_union_due;
                    IF v_done THEN LEAVE emp_loop; END IF;
                    SET v_counter = v_counter + 1;
                    SET v_payment_id = CONCAT('PM', LPAD(v_base + v_counter, 4, '0'));
                    SET v_amount = calc_gross_pay(v_emp_id, p_start, p_end, p_hourly_rate);
                    INSERT INTO Payment (PaymentID, PayrollID, EmployeeID, Amount, Deduction)
                    VALUES (v_payment_id, p_payroll_id, v_emp_id, v_amount, v_union_due);
                END LOOP;
                CLOSE emp_cur;
            END
            """,
        ),
        (
            "add_timecard",
            """
            CREATE PROCEDURE add_timecard(
                IN p_timecard_id CHAR(6),
                IN p_schedule_id CHAR(6),
                IN p_employee_id CHAR(6),
                IN p_date DATE,
                IN p_hours DECIMAL(10,2)
            )
            BEGIN
                INSERT INTO Timecard (TimecardID, ScheduleID, EmployeeID, Date, Hours)
                VALUES (p_timecard_id, p_schedule_id, p_employee_id, p_date, p_hours);
            END
            """,
        ),
        (
            "ActiveEmployees",
            """
            CREATE PROCEDURE ActiveEmployees(IN p_company_id CHAR(6))
            BEGIN
                SELECT COUNT(*) AS cnt
                FROM Employee
                WHERE CompanyID = p_company_id AND Active = TRUE;
            END
            """,
        ),
        (
            "ActiveTimecards",
            """
            CREATE PROCEDURE ActiveTimecards(IN p_company_id CHAR(6))
            BEGIN
                SELECT COUNT(*) AS cnt
                FROM Timecard tc
                JOIN Schedule s ON tc.ScheduleID = s.ScheduleID
                JOIN Job_site js ON js.SiteID = s.SiteID
                JOIN Project p ON p.ProjectID = js.ProjectID
                WHERE p.CompanyID = p_company_id
                  AND s.StartDate <= CURDATE() AND s.EndDate >= CURDATE();
            END
            """,
        ),
        (
            "ActiveProjects",
            """
            CREATE PROCEDURE ActiveProjects(IN p_company_id CHAR(6))
            BEGIN
                SELECT COUNT(*) AS cnt
                FROM Project
                WHERE CompanyID = p_company_id AND Status = TRUE;
            END
            """,
        ),
        (
            "generate_report",
            """
            CREATE PROCEDURE generate_report(
                IN p_company_id CHAR(6),
                IN p_start_date DATE,
                IN p_end_date DATE,
                IN p_employee_id CHAR(6),
                IN p_site_id CHAR(6),
                IN p_hourly_rate DECIMAL(10,2)
            )
            BEGIN
                SELECT e.EmployeeID, e.Name, js.SiteName, p.ProjectID,
                       SUM(tc.Hours) AS Hours,
                       pay_by_site(e.EmployeeID, js.SiteID,
                                   p_start_date, p_end_date, p_hourly_rate) AS TotalLaborCost
                FROM Timecard tc
                JOIN Employee e ON e.EmployeeID = tc.EmployeeID
                JOIN Schedule s ON s.ScheduleID = tc.ScheduleID
                JOIN Job_site js ON js.SiteID = s.SiteID
                JOIN Project p ON p.ProjectID = js.ProjectID
                WHERE e.CompanyID = p_company_id
                  AND tc.Date BETWEEN p_start_date AND p_end_date
                  AND (p_employee_id IS NULL OR e.EmployeeID = p_employee_id)
                  AND (p_site_id IS NULL OR js.SiteID = p_site_id)
                GROUP BY e.EmployeeID, e.Name, js.SiteID, js.SiteName, p.ProjectID
                ORDER BY e.Name, js.SiteName;
            END
            """,
        ),
        (
            "edit_employee",
            """
            CREATE PROCEDURE edit_employee(
                IN p_employee_id CHAR(6),
                IN p_name VARCHAR(50),
                IN p_union_id CHAR(6),
                IN p_trade_id CHAR(6),
                IN p_active BOOLEAN
            )
            BEGIN
                UPDATE Employee
                SET Name = p_name, UnionID = p_union_id,
                    TradeID = p_trade_id, Active = p_active
                WHERE EmployeeID = p_employee_id;
            END
            """,
        ),
        (
            "edit_job_site",
            """
            CREATE PROCEDURE edit_job_site(
                IN p_site_id CHAR(6),
                IN p_project_id CHAR(6),
                IN p_site_name VARCHAR(50),
                IN p_location VARCHAR(100)
            )
            BEGIN
                UPDATE Job_site
                SET ProjectID = p_project_id,
                    SiteName = p_site_name,
                    Location = p_location
                WHERE SiteID = p_site_id;
            END
            """,
        ),
        (
            "sp_edit_project",
            """
            CREATE PROCEDURE sp_edit_project(
                IN p_project_id CHAR(6),
                IN p_status BOOLEAN,
                IN p_project_name VARCHAR(100)
            )
            BEGIN
                UPDATE Project
                SET Status = p_status, ProjectName = p_project_name
                WHERE ProjectID = p_project_id;
            END
            """,
        ),
        (
            "delete_employee",
            """
            CREATE PROCEDURE delete_employee(IN p_employee_id CHAR(6))
            BEGIN
                DELETE FROM Employee WHERE EmployeeID = p_employee_id;
            END
            """,
        ),
        (
            "delete_timecard",
            """
            CREATE PROCEDURE delete_timecard(IN p_timecard_id CHAR(6))
            BEGIN
                DELETE FROM Timecard WHERE TimecardID = p_timecard_id;
            END
            """,
        ),
        (
            "delete_project",
            """
            CREATE PROCEDURE delete_project(IN p_project_id CHAR(6))
            BEGIN
                DELETE FROM Project WHERE ProjectID = p_project_id;
            END
            """,
        ),
        (
            "delete_assignment",
            """
            CREATE PROCEDURE delete_assignment(IN p_schedule_id CHAR(6))
            BEGIN
                DELETE FROM Schedule WHERE ScheduleID = p_schedule_id;
            END
            """,
        ),
    ]
    for name, ddl in procedures:
        try:
            with get_conn() as conn:
                cur = conn.cursor()
                cur.execute(f"DROP PROCEDURE IF EXISTS {name}")
                cur.execute(ddl.strip())
                cur.close()
        except Exception as exc:
            logger.warning("Could not create procedure %s: %s", name, exc)


def ensure_db_views():
    views = [
        (
            "v_users_no_password",
            """
            CREATE OR REPLACE VIEW v_users_no_password AS
            SELECT UserID, CompanyID, Username
            FROM User_tbl
            """,
        ),
        (
            "v_active_employees",
            """
            CREATE OR REPLACE VIEW v_active_employees AS
            SELECT EmployeeID, CompanyID, Name, TradeID, UnionID
            FROM Employee
            WHERE Active = 1
            """,
        ),
        (
            "v_payroll_summary",
            """
            CREATE OR REPLACE VIEW v_payroll_summary AS
            SELECT
                pr.PayrollID,
                pr.CompanyID,
                pr.PeriodStart,
                pr.PeriodEnd,
                COUNT(DISTINCT p.EmployeeID) AS EmployeeCount,
                SUM(p.Amount)               AS TotalGross,
                SUM(p.Amount - p.Deduction) AS TotalNet
            FROM Payroll pr
            LEFT JOIN Payment p ON p.PayrollID = pr.PayrollID
            GROUP BY pr.PayrollID, pr.CompanyID, pr.PeriodStart, pr.PeriodEnd
            """,
        ),
    ]
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            for _name, ddl in views:
                cur.execute(ddl.strip())
            cur.close()
    except Exception as exc:
        logger.warning("Could not create security views: %s", exc)


def ensure_audit_table():
    """Create AuditLog table for logging sensitive data operations."""
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS AuditLog (
                    LogID         INT AUTO_INCREMENT PRIMARY KEY,
                    TableName     VARCHAR(50)                        NOT NULL,
                    OperationType ENUM('INSERT','UPDATE','DELETE')   NOT NULL,
                    RecordID      VARCHAR(20)                        NOT NULL,
                    ChangedBy     VARCHAR(50)                        DEFAULT NULL,
                    ChangeTime    DATETIME                           NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    OldValue      TEXT                               DEFAULT NULL,
                    NewValue      TEXT                               DEFAULT NULL
                )
                """
            )
            cur.close()
    except Exception as exc:
        logger.warning("Could not create AuditLog table: %s", exc)


def ensure_audit_triggers():
    triggers = [
        (
            "trg_payment_after_insert",
            """
            CREATE TRIGGER trg_payment_after_insert
            AFTER INSERT ON Payment
            FOR EACH ROW
            BEGIN
                INSERT INTO AuditLog (TableName, OperationType, RecordID, NewValue)
                VALUES (
                    'Payment', 'INSERT', NEW.PaymentID,
                    CONCAT('PayrollID=', NEW.PayrollID,
                           ', EmployeeID=', NEW.EmployeeID,
                           ', Amount=', NEW.Amount,
                           ', Deduction=', NEW.Deduction)
                );
            END
            """,
        ),
        (
            "trg_payment_before_update",
            """
            CREATE TRIGGER trg_payment_before_update
            BEFORE UPDATE ON Payment
            FOR EACH ROW
            BEGIN
                INSERT INTO AuditLog (TableName, OperationType, RecordID, OldValue, NewValue)
                VALUES (
                    'Payment', 'UPDATE', OLD.PaymentID,
                    CONCAT('Amount=', OLD.Amount, ', Deduction=', OLD.Deduction),
                    CONCAT('Amount=', NEW.Amount, ', Deduction=', NEW.Deduction)
                );
            END
            """,
        ),
        (
            "trg_payment_after_delete",
            """
            CREATE TRIGGER trg_payment_after_delete
            AFTER DELETE ON Payment
            FOR EACH ROW
            BEGIN
                INSERT INTO AuditLog (TableName, OperationType, RecordID, OldValue)
                VALUES (
                    'Payment', 'DELETE', OLD.PaymentID,
                    CONCAT('PayrollID=', OLD.PayrollID,
                           ', EmployeeID=', OLD.EmployeeID,
                           ', Amount=', OLD.Amount)
                );
            END
            """,
        ),
        (
            "trg_payroll_after_insert",
            """
            CREATE TRIGGER trg_payroll_after_insert
            AFTER INSERT ON Payroll
            FOR EACH ROW
            BEGIN
                INSERT INTO AuditLog (TableName, OperationType, RecordID, NewValue)
                VALUES (
                    'Payroll', 'INSERT', NEW.PayrollID,
                    CONCAT('CompanyID=', NEW.CompanyID,
                           ', PeriodStart=', NEW.PeriodStart,
                           ', PeriodEnd=', NEW.PeriodEnd)
                );
            END
            """,
        ),
        (
            "trg_employee_before_update",
            """
            CREATE TRIGGER trg_employee_before_update
            BEFORE UPDATE ON Employee
            FOR EACH ROW
            BEGIN
                IF OLD.Name != NEW.Name OR OLD.Active != NEW.Active THEN
                    INSERT INTO AuditLog (TableName, OperationType, RecordID, OldValue, NewValue)
                    VALUES (
                        'Employee', 'UPDATE', OLD.EmployeeID,
                        CONCAT('Name=', OLD.Name, ', Active=', OLD.Active),
                        CONCAT('Name=', NEW.Name, ', Active=', NEW.Active)
                    );
                END IF;
            END
            """,
        ),
        (
            "trg_employee_after_delete",
            """
            CREATE TRIGGER trg_employee_after_delete
            AFTER DELETE ON Employee
            FOR EACH ROW
            BEGIN
                INSERT INTO AuditLog (TableName, OperationType, RecordID, OldValue)
                VALUES (
                    'Employee', 'DELETE', OLD.EmployeeID,
                    CONCAT('Name=', OLD.Name, ', CompanyID=', OLD.CompanyID)
                );
            END
            """,
        ),
    ]
    for trigger_name, ddl in triggers:
        try:
            with get_conn() as conn:
                cur = conn.cursor()
                cur.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")
                cur.execute(ddl.strip())
                cur.close()
        except Exception as exc:
            logger.warning("Could not create trigger %s: %s", trigger_name, exc)
