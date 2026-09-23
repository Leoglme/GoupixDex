-- idProduct TCGplayer du produit scellé : permet la courbe TCGplayer (shards statiques) pour les scellés
-- sans idProduct Cardmarket, comme l'aperçu catalogue.
ALTER TABLE sealed_products
  ADD COLUMN IF NOT EXISTS tcgplayer_id BIGINT NULL AFTER cardmarket_id_product;
