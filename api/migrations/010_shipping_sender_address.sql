-- Return / sender address for envelope flap labels (per user).
ALTER TABLE settings ADD COLUMN IF NOT EXISTS sender_full_name VARCHAR(120) NULL;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS sender_line1 VARCHAR(180) NULL;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS sender_line2 VARCHAR(180) NULL;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS sender_postal_code VARCHAR(20) NULL;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS sender_city VARCHAR(80) NULL;
