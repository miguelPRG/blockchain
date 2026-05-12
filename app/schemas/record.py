"""Esquemas de solicitação e resposta de registro."""

from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.auth import SignatureEnvelope
from app.schemas.common import AnchorInfo


class RecordType(str, Enum):
    """Tipos de operação de cadeia de suprimentos permitidos."""

    PRODUCED = "PRODUCED"
    TRANSFER = "TRANSFER"
    RECEIVED = "RECEIVED"
    DELIVERY = "DELIVERY"


class RecordPayload(BaseModel):
    """Carga de registro canônica usada para hash/assinatura."""

    record_id: str = Field(..., description="ID de registro único.")
    record_type: RecordType
    manifest_id: str
    quantity: float = Field(..., gt=0)
    unit: str
    user: str = Field(..., description="Endereço derivado da chave pública do usuário.")
    timestamp: str = Field(..., description="Timestamp ISO (2026-05-12T14:50:38.566021+00:00).")
    notes: str | None = Field(default=None, description="Notas operacionais opcionais.")


class RecordCreateRequest(BaseModel):
    """Solicitação de criação de registro com autenticação criptográfica."""

    payload: RecordPayload
    auth: SignatureEnvelope


class RecordResponse(BaseModel):
    """Registro armazenado + hash e status de blockchain."""

    payload: RecordPayload
    payload_hash: str
    anchor: AnchorInfo
