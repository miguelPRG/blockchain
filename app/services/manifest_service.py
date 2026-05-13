"""Lógica de negócios para criação segura de manifesto."""

import logging
import sys
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.hashing import sha256_hex, canonical_json_readable
from app.core.security import address_from_public_key, verify_signature
from app.crud import manifest as manifest_crud
from app.schemas.manifest import ManifestCreateRequest, ManifestResponse
from app.services.blockchain_service import anchor_manifest
from app.services.deploy_service import auto_deploy_if_needed

logger = logging.getLogger(__name__)


def create_manifest(db: Session, request: ManifestCreateRequest) -> ManifestResponse:
    """Validar assinaturas, fazer hash de carga, armazenar manifesto e ancorar na blockchain."""
    payload = request.payload
    if manifest_crud.get_manifest(db, payload.manifest_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Manifest ID already exists.")
    
    # Verificar que creator foi preenchido pelo cliente
    if not payload.creator:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Creator must be provided in payload.")
    
    # Verificar que creator corresponde à chave pública
    derived_address = address_from_public_key(request.auth.public_key)
    if payload.creator.lower() != derived_address.lower():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Creator address does not match provided public key.",
        )

    # Hash já foi calculado corretamente no cliente (com creator preenchido)
    # Usar o mesmo método que a CLI: converter para dict antes de calcular hash
    # IMPORTANTE: usar mode='json' para serializar Enums como strings
    payload_dict = payload.model_dump(mode='json')

    # Log do JSON canônico (usar versão legível para display)
    canonical_readable = canonical_json_readable(payload_dict)
    sys.stderr.write(f"\n[API] CANONICAL JSON:\n{canonical_readable}\n")
    sys.stderr.flush()
    
    payload_hash = sha256_hex(payload_dict)
    logger.debug(f"Payload hash: {payload_hash}")
    sys.stderr.write(f"[API] PAYLOAD HASH: {payload_hash}\n")
    sys.stderr.write(f"[API] PUBLIC KEY: {request.auth.public_key}\n")
    sys.stderr.write(f"[API] SIGNATURE: {request.auth.signature}\n")
    sys.stderr.flush()
    
    if not verify_signature(request.auth.public_key, payload_hash, request.auth.signature):
        logger.error(f"Signature verification failed for hash: {payload_hash}")
        sys.stderr.write(f"[API] VERIFICATION FAILED!\n")
        sys.stderr.flush()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid ECDSA signature.")

    # Garantir que contrato está deploiado antes de ancorar
    if not auto_deploy_if_needed(verbose=True):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to deploy contract.")

    # Converter timestamp ISO para Unix timestamp
    timestamp_dt = datetime.fromisoformat(payload.timestamp)
    unix_timestamp = int(timestamp_dt.timestamp())

    # Ancorar manifesto completo na blockchain
    anchor = anchor_manifest(
        payload_hash=payload_hash,
        manifest_id=payload.manifest_id,
        good_type=payload.good_type,
        quantity=int(payload.quantity),
        unit=payload.unit,
        ingredients=payload.ingredients,
        origin=payload.origin,
        sustainability=payload.sustainability,
        timestamp=unix_timestamp,
    )
    
    manifest_crud.create_manifest(
        db=db,
        payload=payload,
        payload_hash=payload_hash,
        signature=request.auth.signature,
        public_key=request.auth.public_key,
        tx_hash=anchor.tx_hash,
    )
    return ManifestResponse(
        payload=payload,
        payload_hash=payload_hash,
        anchor={"tx_hash": anchor.tx_hash, "anchored": anchor.anchored, "reason": anchor.reason},
    )
