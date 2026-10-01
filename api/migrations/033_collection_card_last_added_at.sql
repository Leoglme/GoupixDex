-- Dernier exemplaire entré dans la collection (scan, catalogue, emplacement de classeur rempli) : « Ma collection » se trie dessus.
ALTER TABLE collection_cards
  ADD COLUMN IF NOT EXISTS last_added_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) AFTER created_at;

UPDATE collection_cards SET last_added_at = created_at;
