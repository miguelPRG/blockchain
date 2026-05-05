"""Modelo de registro de operação de cadeia de suprimentos."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Record(Base):
    """Registro de operação assinado e com hash ancorado em Mainnet."""

    __tablename__ = "records"

    record_id: Mapped[str] = mapped_column(String(80), primary_key=True, index=True)
    record_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    manifest_id: Mapped[str] = mapped_column(ForeignKey("manifests.manifest_id"), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(30), nullable=False)
    user: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    tx_hash: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
