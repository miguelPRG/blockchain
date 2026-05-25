"""Esquemas para autenticação de solicitação baseada em assinatura."""

from pydantic import BaseModel, Field


class SignatureEnvelope(BaseModel):
    """
    Metadados de assinatura anexados a cada operação mutável.

    O backend verifica:
    1) assinatura do utilizador é válida para o hash SHA-256 determinístico da carga
    2) assinatura do Supply Manager é válida para o mesmo hash
    3) chave pública do Supply Manager pertence ao gestor esperado
    """

    public_key: str = Field(..., description="Chave pública ECDSA do usuário em hex.")
    signature: str = Field(..., description="Assinatura ECDSA em hex sobre hash da carga.")
    manager_public_key: str = Field(..., description="Chave pública ECDSA do Supply Manager em hex.")
    manager_signature: str = Field(..., description="Assinatura ECDSA do Supply Manager em hex sobre o mesmo hash da carga.")
