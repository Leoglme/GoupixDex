-- Produits scellés de la collection (ETB, UPC, coffrets, tripacks, pokébox, mini tins, displays…).
-- Prix Cardmarket par idProduct (même guide local que les cartes) ; prix d'achat saisi pour le % de gain.
CREATE TABLE IF NOT EXISTS sealed_products (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  name VARCHAR(255) NOT NULL,
  product_type VARCHAR(32) NOT NULL DEFAULT 'autre',
  set_name VARCHAR(255) NULL,
  language VARCHAR(8) NOT NULL DEFAULT 'fr',
  image_url VARCHAR(512) NULL,
  quantity INT NOT NULL DEFAULT 1,
  purchase_price_eur DECIMAL(12, 2) NULL,
  notes TEXT NULL,
  cardmarket_id_product BIGINT NULL,
  cardmarket_url VARCHAR(512) NULL,
  market_price_eur DECIMAL(12, 2) NULL,
  market_price_updated_at DATETIME(6) NULL,
  article_id BIGINT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  CONSTRAINT fk_sealed_products_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
  CONSTRAINT fk_sealed_products_article FOREIGN KEY (article_id) REFERENCES articles (id) ON DELETE SET NULL,
  INDEX idx_sealed_products_user (user_id),
  INDEX idx_sealed_products_article (article_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
