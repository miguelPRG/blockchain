"""Lógica de negócios para criação de manifesto blockchain-only."""

import logging
import sys
from datetime import datetime
from fastapi import HTTPException, status

from app.core.hashing import sha256_hex, canonical_json_readable
from app.core.security import verify_signature
from app.schemas.manifest import ManifestCreateRequest, ManifestResponse
from app.services.blockchain_service import create_manifest as create_manifest_on_chain
from app.services.deploy_service import auto_deploy_if_needed

logger = logging.getLogger(__name__)


def create_manifest(request: ManifestCreateRequest) -> ManifestResponse:
    """
    Criar manifesto direto na blockchain (blockchain-only, sem SQLAlchemy).
    
    Validações:
    - Assinatura ECDSA válida
    - Contrato está deploiado
    - Manifesto é criado e armazenado na blockchain
    
    Nota: Creator é derivado automaticamente do msg.sender (chave privada do backend)
    """
    payload = request.payload

    # Calcular hash do payload
    payload_dict = payload.model_dump(mode='json')
    canonical_readable = canonical_json_readable(payload_dict)
    sys.stderr.write(f"\n[API] CANONICAL JSON:\n{canonical_readable}\n")
    sys.stderr.flush()
    
    payload_hash = sha256_hex(payload_dict)
    logger.debug(f"Payload hash: {payload_hash}")
    sys.stderr.write(f"[API] PAYLOAD HASH: {payload_hash}\n")
    sys.stderr.write(f"[API] PUBLIC KEY: {request.auth.public_key}\n")
    sys.stderr.write(f"[API] SIGNATURE: {request.auth.signature}\n")
    sys.stderr.flush()
    
    # Verificar assinatura
    if not verify_signature(request.auth.public_key, payload_hash, request.auth.signature):
        logger.error(f"Signature verification failed for hash: {payload_hash}")
        sys.stderr.write(f"[API] VERIFICATION FAILED!\n")
        sys.stderr.flush()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid ECDSA signature.")

    # Garantir que contrato está deploiado
    if not auto_deploy_if_needed(verbose=True):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to deploy contract.")

    # Converter timestamp ISO para Unix timestamp
    timestamp_dt = datetime.fromisoformat(payload.timestamp)
    unix_timestamp = int(timestamp_dt.timestamp())

    # Criar manifesto direto na blockchain
    anchor = create_manifest_on_chain(
        manifest_id=payload.manifest_id,
        payload_hash=payload_hash,
        good_type=payload.good_type,
        quantity=int(payload.quantity),
        unit=payload.unit,
        ingredients=payload.ingredients,
        origin=payload.origin,
        sustainability=payload.sustainability,
        timestamp=unix_timestamp,
    )
    
    # Se criação falhou, erro
    if not anchor.anchored:
        logger.error(f"Falha ao criar manifesto: {anchor.reason}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create manifest on blockchain: {anchor.reason}"
        )
    
    logger.info(f"✅ Manifesto criado com sucesso: TX {anchor.tx_hash}")
    return ManifestResponse(
        payload=payload,
        payload_hash=payload_hash,
        anchor={"tx_hash": anchor.tx_hash, "anchored": anchor.anchored, "reason": anchor.reason},
    )
