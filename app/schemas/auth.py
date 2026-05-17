"""Esquemas para autenticação de solicitação baseada em assinatura."""

from pydantic import BaseModel, Field


class SignatureEnvelope(BaseModel):
    """
    Metadados de assinatura anexados a cada operação mutável.

    O backend verifica:
    1) endereço do usuário é derivado da chave pública
    2) assinatura é válida para o hash SHA-256 determinístico da carga
    """

    public_key: str = Field(..., description="Chave pública ECDSA do usuário em hex.")
    signature: str = Field(..., description="Assinatura ECDSA em hex sobre hash da carga.")
    role: str | None = Field(default=None, description="Papel declarado do usuário nesta operação.")
