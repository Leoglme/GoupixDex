-- Historique de prix marché des produits scellés du catalogue (un point par idProduct et par jour), partagé entre utilisateurs.
CREATE TABLE IF NOT EXISTS sealed_catalog_price_snapshots (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  cardmarket_id_product BIGINT NOT NULL,
  snapshot_date DATE NOT NULL,
  market_price_eur DECIMAL(12, 2) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_sealed_catalog_price_snapshots_product_date (cardmarket_id_product, snapshot_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
