"""Lógica de negócios para criação de registo com repositório off-chain e validação de quantidades."""

import json
import logging
import sys
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from shared.hashing import sha256_hex, canonical_json_readable
from shared.security import (
    ethereum_address_from_public_key,
)
from app.schemas.record import RecordCreateRequest, RecordResponse, RecordType
from app.schemas.verification import VerificationRequest
from app.models.manifest import Manifest as ManifestModel
from app.models.record import Record as RecordModel
from app.services.blockchain_service import broadcast_signed_anchor_transaction, decode_anchor_tx
from app.services.signature_service import validate_dual_signature
from app.services.verification_service import verify_payload

logger = logging.getLogger(__name__)

ROLE_ALLOWED_RECORD_TYPES = {
    "PRODUCER": {RecordType.PRODUCED},
    "TRANSPORTER": {RecordType.TRANSFER},
    "RECEIVER": {RecordType.RECEIVED},
}


def _records_for_manifest(db: Session, manifest_id: str) -> list[RecordModel]:
    return (
        db.query(RecordModel)
        .filter(RecordModel.manifest_id == manifest_id)
        .order_by(RecordModel.created_at.asc())
        .all()
    )


def _transferred_quantity(records: list[RecordModel]) -> float:
    return sum(record.quantity for record in records if record.record_type == RecordType.TRANSFER.value)


def _received_quantity_for_transfer(db: Session, transfer_record_id: str):
    return (
        db.query(RecordModel)
        .filter(
            RecordModel.record_type == RecordType.RECEIVED.value,
            RecordModel.related_record_id == transfer_record_id,
        )
        .with_entities(RecordModel.quantity)
        .all()
    )


def _sum_quantities(rows) -> float:
    return sum(row[0] for row in rows)


def record_payload_for_hash(payload) -> dict:
    """Canonical record payload, preserving old notes=None behavior."""
    payload_dict = payload.model_dump(mode="json")
    for optional_field in ("sender_user_id", "receiver_user_id", "related_record_id"):
        if payload_dict.get(optional_field) is None:
            payload_dict.pop(optional_field, None)
    return payload_dict


def _manifest_payload_for_verification(manifest: ManifestModel) -> dict:
    payload = {
        "manifest_id": manifest.manifest_id,
        "good_type": manifest.good_type,
        "quantity": manifest.quantity,
        "unit": manifest.unit,
        "ingredients": json.loads(manifest.ingredients_json),
        "origin": manifest.origin,
        "sustainability": manifest.sustainability,
        "timestamp": manifest.timestamp,
    }
    if manifest.owner_user_id is not None:
        payload["owner_user_id"] = manifest.owner_user_id
    if manifest.root_manifest_id is not None:
        payload["root_manifest_id"] = manifest.root_manifest_id
    if manifest.parent_manifest_id is not None:
        payload["parent_manifest_id"] = manifest.parent_manifest_id
    if manifest.source_record_id is not None:
        payload["source_record_id"] = manifest.source_record_id
    return payload


def _ensure_manifest_integrity(manifest: ManifestModel) -> None:
    try:
        payload = _manifest_payload_for_verification(manifest)
        verification = verify_payload(
            VerificationRequest(
                payload=payload,
                tx_hash=manifest.tx_hash,
                contract_address=manifest.contract_address,
                item_id=manifest.manifest_id,
                public_key=manifest.public_key,
                signature=manifest.signature,
                manager_public_key=manifest.manager_public_key,
                manager_signature=manifest.manager_signature,
                expected_hash=manifest.payload_hash,
            )
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Manifest '{manifest.manifest_id}' could not be verified before creating record: {exc}"
            ),
        )

    if not verification.overall_valid:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Manifest '{manifest.manifest_id}' failed blockchain integrity verification. "
                "Record was not saved."
            ),
        )


def _record_payload_for_verification(record: RecordModel) -> dict:
    payload = {
        "record_id": record.record_id,
        "record_type": record.record_type,
        "manifest_id": record.manifest_id,
        "quantity": record.quantity,
        "timestamp": record.timestamp,
        "notes": record.notes,
    }
    if record.sender_user_id is not None:
        payload["sender_user_id"] = record.sender_user_id
    if record.receiver_user_id is not None:
        payload["receiver_user_id"] = record.receiver_user_id
    if record.related_record_id is not None:
        payload["related_record_id"] = record.related_record_id
    return payload


def _ensure_record_integrity(record: RecordModel) -> None:
    try:
        payload = _record_payload_for_verification(record)
        verification = verify_payload(
            VerificationRequest(
                payload=payload,
                tx_hash=record.tx_hash,
                contract_address=record.contract_address,
                item_id=record.record_id,
                public_key=record.public_key,
                signature=record.signature,
                manager_public_key=record.manager_public_key,
                manager_signature=record.manager_signature,
                expected_hash=record.payload_hash,
            )
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Record '{record.record_id}' could not be verified before RECEIVED confirmation: {exc}",
        )

    if not verification.overall_valid:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Record '{record.record_id}' failed blockchain integrity verification. "
                "RECEIVED record was not saved."
            ),
        )


def _validate_record_flow(db: Session, payload, manifest: ManifestModel) -> None:
    records = _records_for_manifest(db, payload.manifest_id)

    if payload.record_type == RecordType.PRODUCED:
        produced_total = sum(record.quantity for record in records if record.record_type == RecordType.PRODUCED.value)
        if produced_total + payload.quantity > manifest.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Produced quantity exceeds manifest quantity.",
            )
        return

    if payload.record_type == RecordType.TRANSFER:
        if payload.sender_user_id != "bob" or payload.receiver_user_id != "charlie":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="TRANSFER must identify Bob as sender_user_id and Charlie as receiver_user_id.",
            )

        available_quantity = manifest.quantity - _transferred_quantity(records)
        if payload.quantity > available_quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Insufficient available quantity. Available: {available_quantity} "
                    f"{manifest.unit}, requested transfer: {payload.quantity} {manifest.unit}."
                ),
            )
        return

    if payload.record_type == RecordType.RECEIVED:
        if payload.sender_user_id != "bob" or payload.receiver_user_id != "charlie":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="RECEIVED must identify Bob as sender_user_id and Charlie as receiver_user_id.",
            )
        if not payload.related_record_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="RECEIVED records must reference the TRANSFER record in related_record_id.",
            )

        transfer = db.query(RecordModel).filter(RecordModel.record_id == payload.related_record_id).first()
        if (
            not transfer
            or transfer.record_type != RecordType.TRANSFER.value
            or transfer.manifest_id != payload.manifest_id
            or transfer.sender_user_id != payload.sender_user_id
            or transfer.receiver_user_id != payload.receiver_user_id
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="RECEIVED record does not match a valid TRANSFER record.",
            )

        _ensure_record_integrity(transfer)

        already_received = _sum_quantities(_received_quantity_for_transfer(db, transfer.record_id))
        if already_received + payload.quantity > transfer.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Received quantity exceeds the referenced transfer quantity.",
            )
        return


def create_record(db: Session, request: RecordCreateRequest) -> RecordResponse:
    """
    Criar registo no repositório local com validação de quantidades.
    
    Validações:
    - Manifesto DEVE existir no banco de dados local
    - Assinatura ECDSA válida
    - Operações não podem exceder as quantidades disponíveis
    - Contrato está deploiado
    - Hash é ancorado na blockchain
    """
    payload = request.payload
    logger.info(f"Criando registo para manifesto: {payload.manifest_id}")
    user_address = ethereum_address_from_public_key(request.auth.public_key)

    if request.role not in ROLE_ALLOWED_RECORD_TYPES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid role for record creation.",
        )

    if payload.record_type not in ROLE_ALLOWED_RECORD_TYPES[request.role]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Role '{request.role}' cannot create record type '{payload.record_type.value}'."
            ),
        )
    
    # Verificar se o registo já existe
    existing_record = db.query(RecordModel).filter(RecordModel.record_id == payload.record_id).first()
    if existing_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Record '{payload.record_id}' already exists."
        )

    # 1. Verificar que manifesto existe no banco de dados
    manifest = db.query(ManifestModel).filter(ManifestModel.manifest_id == payload.manifest_id).first()
    if not manifest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Manifest '{payload.manifest_id}' does not exist in repository. Create it first."
        )
    _ensure_manifest_integrity(manifest)
    _validate_record_flow(db, payload, manifest)

    # Calcular hash do payload
    payload_dict = record_payload_for_hash(payload)
    canonical_readable = canonical_json_readable(payload_dict)
    sys.stderr.write(f"\n[API RECORD] CANONICAL JSON:\n{canonical_readable}\n")
    sys.stderr.flush()
    
    payload_hash = sha256_hex(payload_dict)
    
    validate_dual_signature(
        auth=request.auth,
        payload_hash=payload_hash,
    )

    tx_hash = request.tx_hash
    if not tx_hash:
        if not request.signed_anchor_tx:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Either tx_hash or signed_anchor_tx must be provided.",
            )

        anchor = broadcast_signed_anchor_transaction(request.signed_anchor_tx)
        if not anchor.anchored or not anchor.tx_hash:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Blockchain anchor failed. Record was not saved. Reason: {anchor.reason}",
            )
        tx_hash = anchor.tx_hash

    # Validar a transação que acabou de ser publicada, ou o TXID enviado pelo CLI.
    blockchain_anchor = decode_anchor_tx(tx_hash, request.contract_address)
    if (
        not blockchain_anchor
        or blockchain_anchor["payload_hash"] != payload_hash
        or blockchain_anchor["item_id"] != payload.record_id
        or blockchain_anchor["status"] != 1
        or blockchain_anchor["function"] != "anchorHash"
        or not blockchain_anchor.get("from_address")
        or blockchain_anchor["from_address"].lower() != user_address.lower()
    ):
        logger.error("Blockchain anchor does not match record payload. Record will not be stored.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Blockchain anchor does not match record payload. Record was not saved.",
        )
    
    logger.info(f"✅ Hash do registo ancorado com sucesso: TX {tx_hash}")

    # Só depois de validar o TXID guardamos o registo off-chain.
    db_record = RecordModel(
        record_id=payload.record_id,
        record_type=payload.record_type.value,
        manifest_id=payload.manifest_id,
        quantity=payload.quantity,
        sender_user_id=payload.sender_user_id,
        receiver_user_id=payload.receiver_user_id,
        related_record_id=payload.related_record_id,
        user=user_address,
        timestamp=payload.timestamp,
        notes=payload.notes,
        payload_hash=payload_hash,
        signature=request.auth.signature,
        public_key=request.auth.public_key,
        manager_signature=request.auth.manager_signature,
        manager_public_key=request.auth.manager_public_key,
        contract_address=request.contract_address,
        tx_hash=tx_hash,
    )

    try:
        db.add(db_record)
        db.commit()
        db.refresh(db_record)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Integrity error while saving record to database."
        )

    return RecordResponse(
        payload=payload,
        payload_hash=payload_hash,
        contract_address=request.contract_address,
        tx_hash=tx_hash,
        anchor={"tx_hash": tx_hash, "anchored": True, "reason": None},
    )
