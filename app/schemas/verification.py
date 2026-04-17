"""Esquemas de endpoint de verificação."""

from pydantic import BaseModel, Field


class VerificationRequest(BaseModel):
    """Solicitação para verificação de integridade independente."""

    payload: dict = Field(..., description="Objeto de carga bruta a ser recomputado e verificado.")
    public_key: str = Field(..., description="Chave pública do signatário em hex.")
    signature: str = Field(..., description="Assinatura ECDSA em hex.")
    expected_hash: str = Field(..., description="Hash armazenado fora da cadeia.")
    tx_hash: str | None = Field(default=None, description="Hash de transação blockchain para prova ancorada.")


class VerificationResponse(BaseModel):
    """Resultado detalhado de verificação."""

    recomputed_hash: str
    hash_matches: bool
    signature_valid: bool
    blockchain_proof_valid: bool
    overall_valid: bool
