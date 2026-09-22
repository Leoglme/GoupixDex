-- Classeur « complétion Pokédex » : région du Pokédex de référence (ex. kanto = n°1..151).
-- NULL = classeur libre (comportement historique). Sert à afficher les placeholders
-- (artwork + nom + n°) sur les pochettes encore vides.
ALTER TABLE binders
  ADD COLUMN pokedex_region VARCHAR(16) NULL AFTER page_count;
