-- Cardmarket purchase orders (PDF import) and link to articles

CREATE TABLE IF NOT EXISTS cardmarket_orders (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  external_order_id VARCHAR(32) NOT NULL,
  seller_username VARCHAR(255) NULL,
  seller_display_name VARCHAR(255) NULL,
  seller_country_code CHAR(2) NULL,
  paid_at DATETIME(6) NULL,
  shipped_at DATETIME(6) NULL,
  delivered_at DATETIME(6) NULL,
  items_subtotal DECIMAL(12, 2) NOT NULL DEFAULT 0,
  shipping_fee DECIMAL(12, 2) NOT NULL DEFAULT 0,
  order_total DECIMAL(12, 2) NOT NULL DEFAULT 0,
  source_filename VARCHAR(512) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_cardmarket_orders_user_external (user_id, external_order_id),
  CONSTRAINT fk_cardmarket_orders_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
  INDEX idx_cardmarket_orders_user_paid (user_id, paid_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cardmarket_order_lines (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  order_id BIGINT NOT NULL,
  line_index INT NOT NULL DEFAULT 0,
  quantity INT NOT NULL DEFAULT 1,
  raw_label VARCHAR(1024) NOT NULL,
  pokemon_key VARCHAR(255) NULL,
  card_number VARCHAR(64) NULL,
  language_code VARCHAR(8) NULL,
  condition_label VARCHAR(32) NULL,
  set_code VARCHAR(64) NULL,
  variant_token VARCHAR(32) NULL,
  unit_price_eur DECIMAL(12, 2) NOT NULL,
  UNIQUE KEY uq_cardmarket_order_lines_order_idx (order_id, line_index),
  CONSTRAINT fk_cardmarket_order_lines_order FOREIGN KEY (order_id) REFERENCES cardmarket_orders (id) ON DELETE CASCADE,
  INDEX idx_cardmarket_order_lines_match (pokemon_key, set_code, card_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE articles ADD COLUMN IF NOT EXISTS order_line_id BIGINT NULL;

ALTER TABLE articles
  ADD CONSTRAINT fk_articles_order_line
  FOREIGN KEY (order_line_id) REFERENCES cardmarket_order_lines (id)
  ON DELETE SET NULL;
