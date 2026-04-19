-- Realized sale amount and channel (Vinted / eBay).

ALTER TABLE articles ADD COLUMN IF NOT EXISTS sold_price DECIMAL(12, 2) NULL;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS sale_source VARCHAR(16) NULL;
