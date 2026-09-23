-- Prix marché saisi à la main : ne pas l'écraser à la revalorisation nocturne.
ALTER TABLE collection_cards
  ADD COLUMN market_price_overridden BOOLEAN NOT NULL DEFAULT 0 AFTER market_price_eur;
