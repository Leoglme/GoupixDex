-- Longer seller remarks after variant (e.g. "CHR bit of whitening in the back")

ALTER TABLE cardmarket_order_lines
  MODIFY COLUMN language_code VARCHAR(16) NULL,
  MODIFY COLUMN condition_label VARCHAR(128) NULL,
  MODIFY COLUMN variant_token VARCHAR(512) NULL;
