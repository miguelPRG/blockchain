"""Esquemas de solicitação e resposta de manifesto."""

from pydantic import BaseModel, Field

from app.schemas.auth import SignatureEnvelope
from app.schemas.common import AnchorInfo


class ManifestPayload(BaseModel):
    """Carga de manifesto canônica para hash e assinatura."""

    manifest_id: str = Field(..., description="ID de manifesto único para lote de cerveja artesanal.")
    good_type: str = Field(..., description='Tipo de cerveja artesanal, ex. "IPA Artesanal".')
    quantity: float = Field(..., gt=0, description='Quantidade produzida, ex. 1200.')
    unit: str = Field(..., description='Unidade de quantidade, tipicamente "litros".')
    ingredients: list[str] = Field(..., description="Lista de ingredientes para rastreabilidade.")
    origin: str = Field(..., description="Local de origem (cervejaria/fazenda).")
    sustainability: str = Field(..., description='Carimbo de sustentabilidade, ex. "Responsible Barley".')
    timestamp: str = Field(..., description="Timestamp ISO (2026-05-12T14:50:38.566021+00:00) da emissão de manifesto.")


class ManifestCreateRequest(BaseModel):
    """Criação de manifesto com assinatura para autenticação mútua."""

    payload: ManifestPayload
    auth: SignatureEnvelope
    role: str | None = Field(default=None, description="Papel declarado do utilizador nesta operação.")
    contract_address: str = Field(..., description="Endereço do contrato Anchor na blockchain Sepolia.")
    tx_hash: str | None = Field(default=None, description="TXID opcional de uma transação já publicada.")
    signed_anchor_tx: str | None = Field(default=None, description="Transação anchorHash assinada localmente pelo user para broadcast no backend.")


class ManifestResponse(BaseModel):
    """Manifesto armazenado + metadados de ancoragem."""

    payload: ManifestPayload
    payload_hash: str
    contract_address: str = Field(..., description="Endereço do contrato Anchor usado na transação.")
    tx_hash: str = Field(..., description="TXID/hash da transação blockchain associada ao manifesto.")
    anchor: AnchorInfo
