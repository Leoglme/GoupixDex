-- Statut « publié sur Vinted » pour les articles (MariaDB / MySQL).
-- IF NOT EXISTS : ré-exécution sans erreur (bases déjà migrées sans table schema_migrations).

ALTER TABLE articles ADD COLUMN IF NOT EXISTS published_on_vinted TINYINT(1) NOT NULL DEFAULT 0;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS vinted_published_at DATETIME(6) NULL;
