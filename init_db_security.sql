-- Password hashes need more than 50 chars.
ALTER TABLE User_tbl MODIFY Password VARCHAR(255) NOT NULL;

-- Example app database user for least-privilege access.
CREATE USER IF NOT EXISTS 'construction_app'@'%' IDENTIFIED BY 'ChangeThisStrongPassword!';
GRANT SELECT, INSERT, UPDATE, DELETE ON managment_db.Company TO 'construction_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON managment_db.Union_tbl TO 'construction_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON managment_db.Trade TO 'construction_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON managment_db.User_tbl TO 'construction_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON managment_db.Employee TO 'construction_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON managment_db.Project TO 'construction_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON managment_db.Job_site TO 'construction_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON managment_db.Schedule TO 'construction_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON managment_db.Payroll TO 'construction_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON managment_db.Timecard TO 'construction_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON managment_db.Payment TO 'construction_app'@'%';
FLUSH PRIVILEGES;
