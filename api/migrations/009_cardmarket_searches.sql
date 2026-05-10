-- Saved Cardmarket "panier" searches (URLs) + last run snapshot (JSON)

CREATE TABLE IF NOT EXISTS cardmarket_searches (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  name VARCHAR(255) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  INDEX idx_cardmarket_searches_user_updated (user_id, updated_at),
  CONSTRAINT fk_cardmarket_searches_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cardmarket_search_urls (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  search_id BIGINT NOT NULL,
  url TEXT NOT NULL,
  sort_index INT NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  INDEX idx_cardmarket_search_urls_search (search_id),
  CONSTRAINT fk_cardmarket_search_urls_search FOREIGN KEY (search_id) REFERENCES cardmarket_searches (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cardmarket_search_results (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  search_id BIGINT NOT NULL,
  ran_at DATETIME(6) NOT NULL,
  payload_json LONGTEXT NOT NULL,
  UNIQUE KEY uq_cardmarket_search_results_search (search_id),
  CONSTRAINT fk_cardmarket_search_results_search FOREIGN KEY (search_id) REFERENCES cardmarket_searches (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
