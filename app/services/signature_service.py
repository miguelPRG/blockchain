"""Validação comum das assinaturas de user e Supply Manager."""

from fastapi import HTTPException, status

from app.schemas.auth import SignatureEnvelope
from shared.security import (
    ethereum_address_from_public_key,
    verify_signature,
)
from app.core.settings import settings

SUPPLY_MANAGER_ADDRESS = settings.supply_manager_address


def validate_dual_signature(
    *,
    auth: SignatureEnvelope,
    payload_hash: str,
) -> None:
    """Validar que user e Supply Manager assinaram exatamente o mesmo payload_hash.

    O backend recebe apenas chaves públicas e assinaturas. Não recebe nem
    recupera chaves privadas.
    """
    if not verify_signature(auth.public_key, payload_hash, auth.signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user signature.",
        )

    manager_address = ethereum_address_from_public_key(auth.manager_public_key)
    if manager_address.lower() != SUPPLY_MANAGER_ADDRESS.lower():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Supply Manager public key.",
        )

    if not verify_signature(auth.manager_public_key, payload_hash, auth.manager_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Supply Manager signature.",
        )
