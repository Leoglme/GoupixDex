-- Cardmarket product id + locally computed market price on collection cards

ALTER TABLE collection_cards
  ADD COLUMN cardmarket_id_product BIGINT NULL,
  ADD COLUMN market_price_eur DECIMAL(12, 2) NULL,
  ADD COLUMN market_price_updated_at DATETIME(6) NULL;
