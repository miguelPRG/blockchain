"""Esquemas de endpoint de verificação."""

from pydantic import BaseModel, Field


class VerificationRequest(BaseModel):
    """Solicitação para verificação de integridade independente."""

    payload: dict = Field(..., description="Objeto de carga bruta a ser recomputado e verificado.")
    tx_hash: str | None = Field(default=None, description="Hash da transação blockchain anchorHash.")
    contract_address: str | None = Field(default=None, description="Endereço do contrato Anchor (opcional, necessário para decodificar tx).")
    item_id: str | None = Field(default=None, description="ID esperado do manifesto ou registo.")
    public_key: str | None = Field(default=None, description="Chave pública do signatário em hex.")
    signature: str | None = Field(default=None, description="Assinatura ECDSA em hex.")
    manager_public_key: str | None = Field(default=None, description="Chave pública do Supply Manager em hex.")
    manager_signature: str | None = Field(default=None, description="Assinatura ECDSA do Supply Manager em hex.")
    expected_hash: str | None = Field(default=None, description="Hash esperado para comparação local opcional.")


class VerificationResponse(BaseModel):
    """Resultado de verificação local e blockchain."""

    payload: dict
    recomputed_hash: str
    hash_matches: bool | None
    signature_valid: bool | None
    manager_public_key_valid: bool | None
    manager_signature_valid: bool | None
    blockchain_payload_hash: str | None = None
    blockchain_from_address: str | None = None
    blockchain_hash_matches: bool | None = None
    blockchain_tx_valid: bool | None = None
    blockchain_item_id: str | None = None
    blockchain_item_matches: bool | None = None
    block_number: int | None = None
    overall_valid: bool
