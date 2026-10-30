"""Empreinte pHash d'une carte absente de l'index de scan livré avec le site."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class ScanPhashCard(Base):
    """
    Carte TCGdex que l'index ``web/public/scan-index/phash-v1`` ne connaît pas, avec l'image qui a servi au calcul.

    ``hashes`` : 32 octets pour la carte entière puis 32 pour l'illustration, comme l'index livré ; ``None`` tant
    qu'aucune image n'a été trouvée (la carte est retentée plus tard).
    """

    __tablename__ = "scan_phash_cards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    locale: Mapped[str] = mapped_column(String(8))
    tcgdex_card_id: Mapped[str] = mapped_column(String(120))
    set_id: Mapped[str] = mapped_column(String(64))
    local_id: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(255))
    hashes: Mapped[bytes | None] = mapped_column(LargeBinary(64), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    checked_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
    )
