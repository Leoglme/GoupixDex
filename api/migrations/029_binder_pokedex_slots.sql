-- Placeholders explicites d'un classeur de complétion : map position -> numéro national.
-- Permet de reproduire fidèlement une disposition (évolutions groupées, pochettes vides
-- d'alignement) où seules certaines positions montrent un placeholder Pokédex, les trous
-- restant vides. NULL = pas de placeholders explicites (les positions vides restent vides).
ALTER TABLE binders
  ADD COLUMN pokedex_slots JSON NULL AFTER pokedex_region;
