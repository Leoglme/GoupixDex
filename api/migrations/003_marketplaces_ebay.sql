-- Services marchands (Vinted / eBay) et colonnes eBay pour articles (MariaDB / MySQL).

ALTER TABLE settings ADD COLUMN IF NOT EXISTS vinted_enabled TINYINT(1) NOT NULL DEFAULT 1;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS ebay_enabled TINYINT(1) NOT NULL DEFAULT 0;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS ebay_marketplace_id VARCHAR(32) NOT NULL DEFAULT 'EBAY_FR';
ALTER TABLE settings ADD COLUMN IF NOT EXISTS ebay_category_id VARCHAR(32) NULL;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS ebay_merchant_location_key VARCHAR(64) NULL;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS ebay_fulfillment_policy_id VARCHAR(32) NULL;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS ebay_payment_policy_id VARCHAR(32) NULL;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS ebay_return_policy_id VARCHAR(32) NULL;

ALTER TABLE users ADD COLUMN IF NOT EXISTS ebay_refresh_token TEXT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS ebay_access_token TEXT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS ebay_access_expires_at DATETIME(6) NULL;

ALTER TABLE articles ADD COLUMN IF NOT EXISTS published_on_ebay TINYINT(1) NOT NULL DEFAULT 0;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS ebay_listing_id VARCHAR(64) NULL;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS ebay_published_at DATETIME(6) NULL;
