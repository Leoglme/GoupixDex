CREATE TABLE IF NOT EXISTS amazon_provision_inbound_messages (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  resend_email_id VARCHAR(64) NOT NULL,
  to_address VARCHAR(255) NOT NULL,
  from_address VARCHAR(255) NULL,
  subject VARCHAR(512) NULL,
  body_text MEDIUMTEXT NULL,
  otp_code VARCHAR(32) NULL,
  received_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_amazon_provision_inbound_resend (resend_email_id),
  INDEX idx_amazon_provision_inbound_to (to_address, received_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
