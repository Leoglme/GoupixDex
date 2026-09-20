-- Historique de prix marché par produit scellé (un point par jour), pour la courbe d'évolution de la fiche.
CREATE TABLE IF NOT EXISTS sealed_price_snapshots (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  sealed_product_id BIGINT NOT NULL,
  snapshot_date DATE NOT NULL,
  market_price_eur DECIMAL(12, 2) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  CONSTRAINT fk_sealed_price_snapshots_product FOREIGN KEY (sealed_product_id) REFERENCES sealed_products (id) ON DELETE CASCADE,
  UNIQUE KEY uq_sealed_price_snapshots_product_date (sealed_product_id, snapshot_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
