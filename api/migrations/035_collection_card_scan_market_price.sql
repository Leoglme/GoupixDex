-- Prix marché unitaire relevé au moment du scan (pré-rempli par le scan, modifiable ensuite).
ALTER TABLE collection_cards
  ADD COLUMN IF NOT EXISTS scan_market_price_eur DECIMAL(12,2) NULL AFTER purchase_price_eur;
