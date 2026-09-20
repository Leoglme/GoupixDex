-- Leboncoin listing tracking + marketplace toggle

ALTER TABLE articles ADD COLUMN IF NOT EXISTS published_on_leboncoin TINYINT(1) NOT NULL DEFAULT 0;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS leboncoin_listing_id VARCHAR(64) NULL;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS leboncoin_published_at DATETIME(6) NULL;

ALTER TABLE settings ADD COLUMN IF NOT EXISTS leboncoin_enabled TINYINT(1) NOT NULL DEFAULT 0;
