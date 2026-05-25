"""Modelo de registro de operação de cadeia de suprimentos."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Record(Base):
    """Payload de registro guardado off-chain."""

    __tablename__ = "records"

    record_id: Mapped[str] = mapped_column(String(80), primary_key=True, index=True)
    record_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    manifest_id: Mapped[str] = mapped_column(ForeignKey("manifests.manifest_id"), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    sender_user_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    receiver_user_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    related_record_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    user: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    timestamp: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    manager_signature: Mapped[str] = mapped_column(Text, nullable=False, default="")
    manager_public_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    contract_address: Mapped[str] = mapped_column(String(42), nullable=False, default="")
    tx_hash: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
