"""Lógica de negócios para criação segura de registro e verificações de estoque."""

import logging
import sys
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.hashing import sha256_hex, canonical_json
from app.core.security import address_from_public_key, verify_signature
from app.crud import manifest as manifest_crud
from app.crud import record as record_crud
from app.schemas.record import RecordCreateRequest, RecordResponse, RecordType
from app.services.blockchain_service import anchor_hash

logger = logging.getLogger(__name__)


def create_record(db: Session, request: RecordCreateRequest) -> RecordResponse:
    """Validar assinatura, aplicar regras de estoque, armazenar registro e ancorar hash."""
    payload = request.payload
    manifest = manifest_crud.get_manifest(db, payload.manifest_id)
    if manifest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manifest not found.")

    derived_address = address_from_public_key(request.auth.public_key)
    if payload.user.lower() != derived_address.lower():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User address/public key mismatch.")

    # Hash já foi calculado corretamente no cliente
    # Usar o mesmo método que a CLI: converter para dict antes de calcular hash
    payload_dict = payload.model_dump()
    logger.debug("=== RECORD_SERVICE PAYLOAD ===")
    logger.debug(payload_dict)
    logger.debug("==============================")
    
    # Log do JSON canônico
    canonical = canonical_json(payload_dict)
    sys.stderr.write(f"\n[API RECORD] CANONICAL JSON:\n{canonical}\n")
    sys.stderr.flush()
    
    payload_hash = sha256_hex(payload_dict)
    logger.debug(f"Payload hash: {payload_hash}")
    sys.stderr.write(f"[API RECORD] PAYLOAD HASH: {payload_hash}\n")
    sys.stderr.write(f"[API RECORD] PUBLIC KEY: {request.auth.public_key}\n")
    sys.stderr.write(f"[API RECORD] SIGNATURE: {request.auth.signature}\n")
    sys.stderr.flush()
    
    if not verify_signature(request.auth.public_key, payload_hash, request.auth.signature):
        logger.error(f"Signature verification failed for hash: {payload_hash}")
        sys.stderr.write(f"[API RECORD] VERIFICATION FAILED!\n")
        sys.stderr.flush()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid ECDSA signature.")

    available = record_crud.get_available_stock(db, payload.manifest_id)
    if payload.record_type in {RecordType.TRANSFER, RecordType.DELIVERY} and payload.quantity > available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient stock. Available={available}, requested={payload.quantity}.",
        )

    anchor = anchor_hash(payload_hash, payload.manifest_id)
    record_crud.create_record(
        db=db,
        payload=payload,
        payload_hash=payload_hash,
        signature=request.auth.signature,
        public_key=request.auth.public_key,
        tx_hash=anchor.tx_hash,
    )
    return RecordResponse(
        payload=payload,
        payload_hash=payload_hash,
        anchor={"tx_hash": anchor.tx_hash, "anchored": anchor.anchored, "reason": anchor.reason},
    )
