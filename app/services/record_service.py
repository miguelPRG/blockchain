"""Lógica de negócios para criação segura de registro e verificações de estoque."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.hashing import sha256_hex
from app.core.security import address_from_public_key, verify_signature
from app.crud import manifest as manifest_crud
from app.crud import record as record_crud
from app.schemas.record import RecordCreateRequest, RecordResponse, RecordType
from app.services.blockchain_service import anchor_hash


def create_record(db: Session, request: RecordCreateRequest) -> RecordResponse:
    """Validar assinatura, aplicar regras de estoque, armazenar registro e ancorar hash."""
    payload = request.payload
    manifest = manifest_crud.get_manifest(db, payload.manifest_id)
    if manifest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manifest not found.")

    derived_address = address_from_public_key(request.auth.public_key)
    if payload.user.lower() != derived_address.lower():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User address/public key mismatch.")

    payload_hash = sha256_hex(payload.model_dump(mode="json"))
    if not verify_signature(request.auth.public_key, payload_hash, request.auth.signature):
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
