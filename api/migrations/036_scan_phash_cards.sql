-- Empreintes pHash des cartes absentes de l'index de scan livré avec le site, calculées chaque nuit.
CREATE TABLE IF NOT EXISTS scan_phash_cards (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  locale VARCHAR(8) NOT NULL,
  tcgdex_card_id VARCHAR(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  set_id VARCHAR(64) NOT NULL,
  local_id VARCHAR(32) NOT NULL,
  name VARCHAR(255) NOT NULL,
  hashes VARBINARY(64) NULL,
  image_url VARCHAR(512) NULL,
  checked_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_scan_phash_cards_card (locale, tcgdex_card_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
