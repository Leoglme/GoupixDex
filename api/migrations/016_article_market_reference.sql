-- Option B: prix marché pré-calculés sur les articles (affichage instantané, refresh nocturne).

ALTER TABLE articles
  ADD COLUMN cardmarket_id_product BIGINT NULL,
  ADD COLUMN market_cardmarket_eur DECIMAL(12, 2) NULL,
  ADD COLUMN market_tcgplayer_eur DECIMAL(12, 2) NULL,
  ADD COLUMN market_priced_at DATETIME(6) NULL;

CREATE INDEX IF NOT EXISTS ix_articles_market_priced_at ON articles (market_priced_at);
