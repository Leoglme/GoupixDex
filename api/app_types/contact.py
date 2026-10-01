"""Contact page types (topic of a message and its label in the received e-mail)."""

from typing import Literal

ContactTopic = Literal["access", "help", "bug", "privacy", "other"]

CONTACT_TOPIC_LABELS: dict[ContactTopic, str] = {
    "access": "Accès à GoupixDex",
    "help": "Aide à l'utilisation",
    "bug": "Signaler un bug",
    "privacy": "Données personnelles",
    "other": "Autre",
}
