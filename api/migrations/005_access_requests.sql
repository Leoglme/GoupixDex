-- Access requests, admin flag and password setup tokens.

ALTER TABLE users MODIFY COLUMN `password` VARCHAR(255) NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin TINYINT(1) NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR(16) NOT NULL DEFAULT 'pending';
ALTER TABLE users ADD COLUMN IF NOT EXISTS request_message TEXT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_setup_token VARCHAR(64) NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_setup_expires_at DATETIME(6) NULL;

-- Existing rows (pre-migration) are real users created by the admin → mark approved.
UPDATE users SET status = 'approved' WHERE status IS NULL OR status = '' OR status = 'pending';

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_password_setup_token ON users (password_setup_token);
