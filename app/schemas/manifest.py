"""Esquemas de solicitação e resposta de manifesto."""

from datetime import datetime

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
    creator: str = Field(..., description="Endereço derivado da chave pública do criador.")
    timestamp: datetime = Field(..., description="Timestamp ISO da emissão de manifesto.")


class ManifestCreateRequest(BaseModel):
    """Criação de manifesto com assinatura para autenticação mútua."""

    payload: ManifestPayload
    auth: SignatureEnvelope


class ManifestResponse(BaseModel):
    """Manifesto armazenado + metadados de ancoragem."""

    payload: ManifestPayload
    payload_hash: str
    anchor: AnchorInfo
