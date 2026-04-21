-- Cartes gradées (slab) : société + note eBay + certificat optionnel ; Vinted « Neuf avec étiquette ».

ALTER TABLE articles ADD COLUMN IF NOT EXISTS is_graded TINYINT(1) NOT NULL DEFAULT 0;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS graded_grader_value_id VARCHAR(16) NULL;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS graded_grade_value_id VARCHAR(16) NULL;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS graded_cert_number VARCHAR(32) NULL;
