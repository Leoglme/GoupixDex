CREATE TABLE IF NOT EXISTS amazon_provision_inbound_watch (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  email VARCHAR(255) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  expires_at DATETIME(6) NOT NULL,
  UNIQUE KEY uq_amazon_provision_watch_user_email (user_id, email),
  INDEX idx_amazon_provision_watch_email (email, expires_at),
  CONSTRAINT fk_amazon_provision_watch_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
