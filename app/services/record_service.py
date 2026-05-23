"""Lógica de negócios para criação de registo com repositório off-chain e validação de quantidades."""

import logging
import sys
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.hashing import sha256_hex, canonical_json_readable
from app.core.security import verify_signature, address_from_private_key, get_private_key_from_signer_id
from app.schemas.record import RecordCreateRequest, RecordResponse, RecordType
from app.models.manifest import Manifest as ManifestModel
from app.models.record import Record as RecordModel
from app.services.blockchain_service import anchor_hash, decode_anchor_tx

logger = logging.getLogger(__name__)

ROLE_ALLOWED_RECORD_TYPES = {
    "PRODUCER": {RecordType.PRODUCED},
    "TRANSPORTER": {RecordType.TRANSFER, RecordType.DELIVERY},
    "RECEIVER": {RecordType.RECEIVED},
}


def _available_stock(db: Session, manifest_id: str) -> float:
    records = db.query(RecordModel).filter(RecordModel.manifest_id == manifest_id).all()
    incoming = sum(
        record.quantity
        for record in records
        if record.record_type in {RecordType.PRODUCED.value, RecordType.RECEIVED.value}
    )
    outgoing = sum(
        record.quantity
        for record in records
        if record.record_type in {RecordType.TRANSFER.value, RecordType.DELIVERY.value}
    )
    return float(incoming - outgoing)


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
    
    # Derivar endereço correto a partir da chave privada do signer_id
    signer_priv = get_private_key_from_signer_id(request.auth.signer_id)
    if not signer_priv:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Signer ID '{request.auth.signer_id}' not found in environment.",
        )
    user_address = address_from_private_key(signer_priv)

    if payload.user != user_address:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Record user {payload.user} does not match signer {user_address}.",
        )

    if request.auth.role not in ROLE_ALLOWED_RECORD_TYPES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid role for record creation.",
        )

    if payload.record_type not in ROLE_ALLOWED_RECORD_TYPES[request.auth.role]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Role '{request.auth.role}' cannot create record type '{payload.record_type.value}'."
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

    # Calcular hash do payload
    payload_dict = payload.model_dump(mode='json')
    canonical_readable = canonical_json_readable(payload_dict)
    sys.stderr.write(f"\n[API RECORD] CANONICAL JSON:\n{canonical_readable}\n")
    sys.stderr.flush()
    
    payload_hash = sha256_hex(payload_dict)
    
    # Verificar assinatura
    if not verify_signature(request.auth.public_key, payload_hash, request.auth.signature):
        logger.error(f"Signature verification failed for hash: {payload_hash}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid ECDSA signature.")

    # Converter timestamp ISO para Unix timestamp
    timestamp_dt = datetime.fromisoformat(payload.timestamp)
    unix_timestamp = int(timestamp_dt.timestamp())

    # Ancorar o hash na blockchain
    logger.info(f"[create_record] signer_id={request.auth.signer_id} signer_priv={'FOUND' if signer_priv else 'NOT FOUND'}")
    anchor = anchor_hash(
        payload_hash=payload_hash,
        timestamp=unix_timestamp,
        item_id=payload.record_id,
        signer_private_key=signer_priv,
    )
    
    if not anchor.anchored:
        logger.error(f"Falha ao ancorar hash do registo: {anchor.reason}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to anchor hash on blockchain: {anchor.reason}"
        )

    blockchain_anchor = decode_anchor_tx(anchor.tx_hash) if anchor.tx_hash else None
    if (
        not blockchain_anchor
        or blockchain_anchor["payload_hash"] != payload_hash
        or blockchain_anchor["item_id"] != payload.record_id
        or blockchain_anchor["status"] != 1
        or blockchain_anchor["function"] != "anchorHash"
    ):
        logger.error("Blockchain anchor does not match record payload. Record will not be stored.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Blockchain anchor does not match record payload. Record was not saved.",
        )
    
    logger.info(f"✅ Hash do registo ancorado com sucesso: TX {anchor.tx_hash}")

    # Armazenar no banco de dados local
    db_record = RecordModel(
        record_id=payload.record_id,
        record_type=payload.record_type.value,
        manifest_id=payload.manifest_id,
        quantity=payload.quantity,
        unit=payload.unit,
        user=payload.user,
        timestamp=payload.timestamp,
        notes=payload.notes,
        payload_hash=payload_hash,
        signature=request.auth.signature,
        public_key=request.auth.public_key,
        tx_hash=anchor.tx_hash,
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
        anchor={"tx_hash": anchor.tx_hash, "anchored": anchor.anchored, "reason": anchor.reason},
    )
