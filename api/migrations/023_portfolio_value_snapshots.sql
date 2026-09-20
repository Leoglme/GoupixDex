-- Historique quotidien de la valeur du portefeuille (cartes + produits scellés), un point par jour.
-- Alimente les courbes « valeur du marché » vs « valeur d'achat » et le donut cartes/produits.
CREATE TABLE IF NOT EXISTS portfolio_value_snapshots (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  snapshot_date DATE NOT NULL,
  cards_market_eur DECIMAL(14, 2) NOT NULL DEFAULT 0,
  sealed_market_eur DECIMAL(14, 2) NOT NULL DEFAULT 0,
  purchase_value_eur DECIMAL(14, 2) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  CONSTRAINT fk_portfolio_snapshots_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
  UNIQUE KEY uq_portfolio_snapshots_user_date (user_id, snapshot_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
