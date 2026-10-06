-- Échec du dernier retrait Leboncoin (worker du PC), affiché sur la fiche et relançable.
ALTER TABLE articles
  ADD COLUMN IF NOT EXISTS cross_leboncoin_removal_failed TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS cross_leboncoin_removal_error VARCHAR(512) NULL;
