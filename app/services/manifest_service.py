"""Lógica de negócios para criação segura de manifesto."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.hashing import sha256_hex
from app.core.security import address_from_public_key, verify_signature
from app.crud import manifest as manifest_crud
from app.schemas.manifest import ManifestCreateRequest, ManifestResponse
from app.services.blockchain_service import anchor_hash


def create_manifest(db: Session, request: ManifestCreateRequest) -> ManifestResponse:
    """Validar assinaturas, fazer hash de carga, armazenar manifesto e ancorar hash."""
    payload = request.payload
    if manifest_crud.get_manifest(db, payload.manifest_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Manifest ID already exists.")

    derived_address = address_from_public_key(request.auth.public_key)
    if payload.creator.lower() != derived_address.lower():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Creator address does not match provided public key.",
        )

    payload_hash = sha256_hex(payload.model_dump(mode="json"))
    if not verify_signature(request.auth.public_key, payload_hash, request.auth.signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid ECDSA signature.")

    anchor = anchor_hash(payload_hash, payload.manifest_id)
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
