-- Thematic binders (sub-collections): cards from `collection_cards` placed in pocket positions.
CREATE TABLE IF NOT EXISTS binders (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  name VARCHAR(255) NOT NULL,
  color VARCHAR(32) NULL,
  style VARCHAR(32) NOT NULL DEFAULT 'binder',
  page_grid VARCHAR(8) NOT NULL DEFAULT '3x3',
  page_count INT NOT NULL DEFAULT 0,
  position INT NULL,
  design JSON NULL,
  cover JSON NULL,
  cover_collection_card_ids JSON NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  CONSTRAINT fk_binders_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
  INDEX idx_binders_user (user_id),
  INDEX idx_binders_user_position (user_id, position)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS binder_items (
  binder_id BIGINT NOT NULL,
  collection_card_id BIGINT NOT NULL,
  position INT NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (binder_id, collection_card_id),
  CONSTRAINT fk_binder_items_binder FOREIGN KEY (binder_id) REFERENCES binders (id) ON DELETE CASCADE,
  CONSTRAINT fk_binder_items_card FOREIGN KEY (collection_card_id) REFERENCES collection_cards (id) ON DELETE CASCADE,
  INDEX idx_binder_items_binder (binder_id),
  INDEX idx_binder_items_card (collection_card_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
