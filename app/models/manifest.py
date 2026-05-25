"""Modelo de manifesto para lotes de cerveja artesanal."""

from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Manifest(Base):
    """Payload de manifesto guardado off-chain."""

    __tablename__ = "manifests"

    manifest_id: Mapped[str] = mapped_column(String(80), primary_key=True, index=True)
    good_type: Mapped[str] = mapped_column(String(120), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(30), nullable=False)
    ingredients_json: Mapped[str] = mapped_column(Text, nullable=False)
    origin: Mapped[str] = mapped_column(String(120), nullable=False)
    sustainability: Mapped[str] = mapped_column(String(120), nullable=False)
    creator: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    timestamp: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    manager_signature: Mapped[str] = mapped_column(Text, nullable=False, default="")
    manager_public_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    contract_address: Mapped[str] = mapped_column(String(42), nullable=False, default="")
    tx_hash: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
