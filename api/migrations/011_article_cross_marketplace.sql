-- Cross-marketplace cleanup after « vendu » (Vinted id, eBay SKU, retry flags).
ALTER TABLE articles
  ADD COLUMN IF NOT EXISTS vinted_id BIGINT UNSIGNED NULL,
  ADD COLUMN IF NOT EXISTS ebay_inventory_sku VARCHAR(50) NULL,
  ADD COLUMN IF NOT EXISTS cross_ebay_removal_failed TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS cross_vinted_removal_failed TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS cross_ebay_removal_error VARCHAR(512) NULL,
  ADD COLUMN IF NOT EXISTS cross_vinted_removal_error VARCHAR(512) NULL;
