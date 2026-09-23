-- Prix d'achat unitaire saisi par l'utilisateur (base du pourcentage de plus-value), comme pour les scellés.
ALTER TABLE collection_cards
  ADD COLUMN IF NOT EXISTS purchase_price_eur DECIMAL(12,2) NULL AFTER quantity;
