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


class RecordPayload(BaseModel):
    """Carga de registro canônica usada para hash/assinatura."""

    record_id: str = Field(..., description="ID de registro único.")
    record_type: RecordType
    manifest_id: str = Field(..., description="ID do manifesto (deve existir na blockchain).")
    quantity: float = Field(..., gt=0)
    sender_user_id: str | None = Field(default=None, description="User que envia/transfere os bens.")
    receiver_user_id: str | None = Field(default=None, description="User que recebe os bens.")
    related_record_id: str | None = Field(default=None, description="Registo anterior relacionado, por exemplo a TRANSFER recebida.")
    timestamp: str = Field(..., description="Timestamp ISO (2026-05-12T14:50:38.566021+00:00).")
    notes: str | None = Field(default=None, description="Notas operacionais opcionais.")


class RecordCreateRequest(BaseModel):
    """Solicitação de criação de registro com autenticação criptográfica."""

    payload: RecordPayload
    auth: SignatureEnvelope
    role: str | None = Field(default=None, description="Papel declarado do utilizador nesta operação.")
    contract_address: str = Field(..., description="Endereço do contrato Anchor na blockchain Sepolia.")
    tx_hash: str | None = Field(default=None, description="TXID opcional de uma transação já publicada.")
    signed_anchor_tx: str | None = Field(default=None, description="Transação anchorHash assinada localmente pelo user para broadcast no backend.")


class RecordResponse(BaseModel):
    """Registro armazenado + hash e status de blockchain."""

    payload: RecordPayload
    payload_hash: str
    contract_address: str = Field(..., description="Endereço do contrato Anchor usado na transação.")
    tx_hash: str = Field(..., description="TXID/hash da transação blockchain associada ao registo.")
    anchor: AnchorInfo
