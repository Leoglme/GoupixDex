-- Cartes « manquantes » dans un classeur : ligne collection qty 0, hors stats Ma collection.
ALTER TABLE collection_cards
  ADD COLUMN is_placeholder TINYINT(1) NOT NULL DEFAULT 0 AFTER quantity;
