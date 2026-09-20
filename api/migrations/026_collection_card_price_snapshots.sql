-- Historique de prix marché par carte de collection (un point par jour), pour la courbe d'évolution de la fiche.
CREATE TABLE IF NOT EXISTS collection_card_price_snapshots (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  collection_card_id BIGINT NOT NULL,
  snapshot_date DATE NOT NULL,
  market_price_eur DECIMAL(12, 2) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  CONSTRAINT fk_collection_card_price_snapshots_card FOREIGN KEY (collection_card_id) REFERENCES collection_cards (id) ON DELETE CASCADE,
  UNIQUE KEY uq_collection_card_price_snapshots_card_date (collection_card_id, snapshot_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
