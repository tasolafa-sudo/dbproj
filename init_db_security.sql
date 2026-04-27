-- ============================================================
-- Password column must hold werkzeug hashes (> 50 chars).
-- ============================================================
ALTER TABLE User_tbl MODIFY Password VARCHAR(255) NOT NULL;

-- ============================================================
-- ROLES (MySQL 8.0+)
-- Role-based access control: grant roles to users rather than
-- assigning privileges directly to each individual account.
-- ============================================================

-- CompanyUserRole: allowed to query and modify app data, and execute stored procedures.
CREATE ROLE IF NOT EXISTS 'CompanyUserRole';
GRANT SELECT, INSERT, UPDATE, DELETE ON managment_db.Company         TO 'CompanyUserRole';
GRANT SELECT, INSERT, UPDATE, DELETE ON managment_db.Union_tbl       TO 'CompanyUserRole';
GRANT SELECT, INSERT, UPDATE, DELETE ON managment_db.Trade           TO 'CompanyUserRole';
GRANT SELECT, INSERT, UPDATE, DELETE ON managment_db.User_tbl        TO 'CompanyUserRole';
GRANT SELECT, INSERT, UPDATE, DELETE ON managment_db.Employee        TO 'CompanyUserRole';
GRANT SELECT, INSERT, UPDATE, DELETE ON managment_db.Project         TO 'CompanyUserRole';
GRANT SELECT, INSERT, UPDATE, DELETE ON managment_db.Job_site        TO 'CompanyUserRole';
GRANT SELECT, INSERT, UPDATE, DELETE ON managment_db.Schedule        TO 'CompanyUserRole';
GRANT SELECT, INSERT, UPDATE, DELETE ON managment_db.Payroll         TO 'CompanyUserRole';
GRANT SELECT, INSERT, UPDATE, DELETE ON managment_db.Timecard        TO 'CompanyUserRole';
GRANT SELECT, INSERT, UPDATE, DELETE ON managment_db.Payment         TO 'CompanyUserRole';
GRANT SELECT, INSERT, UPDATE, DELETE ON managment_db.CompanyAuthCode TO 'CompanyUserRole';
GRANT EXECUTE ON managment_db.*                                      TO 'CompanyUserRole';
-- AuditLog: app user only needs INSERT (triggers write to it) and SELECT (for review).
GRANT SELECT, INSERT ON managment_db.AuditLog                        TO 'CompanyUserRole';
-- Views: read-only access to security views.
GRANT SELECT ON managment_db.v_users_no_password  TO 'CompanyUserRole';
GRANT SELECT ON managment_db.v_active_employees   TO 'CompanyUserRole';
GRANT SELECT ON managment_db.v_payroll_summary    TO 'CompanyUserRole';

-- AdminRole: inherits CompanyUserRole plus structural DDL rights (for developers/migrations).
CREATE ROLE IF NOT EXISTS 'AdminRole';
GRANT 'CompanyUserRole'                     TO 'AdminRole';
GRANT CREATE, DROP, ALTER, INDEX ON managment_db.* TO 'AdminRole';

-- ============================================================
-- APPLICATION DATABASE USER (least-privilege)
-- The web app connects using this account — never as root.
-- Assign to CompanyUserRole; no superuser or DDL privileges.
-- ============================================================
CREATE USER IF NOT EXISTS 'construction_app'@'%' IDENTIFIED BY 'ChangeThisStrongPassword!';
GRANT 'CompanyUserRole' TO 'construction_app'@'%';
SET DEFAULT ROLE 'CompanyUserRole' FOR 'construction_app'@'%';

-- ============================================================
-- DEVELOPER READ-ONLY SUBUSER
-- Developers can query data for debugging without write access.
-- Never grant WITH GRANT OPTION to this account.
-- ============================================================
CREATE USER IF NOT EXISTS 'construction_dev'@'%' IDENTIFIED BY 'DevReadonlyPassword!';
GRANT SELECT ON managment_db.* TO 'construction_dev'@'%';

FLUSH PRIVILEGES;
