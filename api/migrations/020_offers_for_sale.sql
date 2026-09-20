-- Articles retirés de toutes les marketplaces restent en base mais hors « Mes articles ».
ALTER TABLE articles ADD COLUMN offers_for_sale TINYINT(1) NOT NULL DEFAULT 1;

UPDATE articles SET offers_for_sale = 1 WHERE offers_for_sale IS NULL;
