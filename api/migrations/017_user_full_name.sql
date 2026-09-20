-- Display name for marketplaces (Amazon registration, etc.)
ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR(120) NULL;
