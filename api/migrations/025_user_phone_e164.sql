-- Numéro mobile (vérif Amazon SMS/WhatsApp) — drawer « Mon profil ».
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_e164 VARCHAR(20) NULL;
