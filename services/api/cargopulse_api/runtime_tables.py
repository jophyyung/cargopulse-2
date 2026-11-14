"""Additive transient OIDC state, separate from the frozen operational schema."""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from .tables import Base


class OIDCFlow(Base):
    __tablename__ = "oidc_flows"
    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    nonce: Mapped[str] = mapped_column(String(200))
    verifier: Mapped[str] = mapped_column(String(200))
    browser_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
