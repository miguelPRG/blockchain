"""Lógica de negócios para criação de registo com repositório off-chain e validação de quantidades."""

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
from app.models.manifest import Manifest as ManifestModel
from app.models.record import Record as RecordModel
from app.services.blockchain_service import broadcast_signed_anchor_transaction, decode_anchor_tx
from app.services.signature_service import validate_dual_signature

logger = logging.getLogger(__name__)

ROLE_ALLOWED_RECORD_TYPES = {
    "PRODUCER": {RecordType.PRODUCED},
    "TRANSPORTER": {RecordType.TRANSFER, RecordType.DELIVERY},
    "RECEIVER": {RecordType.RECEIVED},
}

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

    # Calcular hash do payload
    payload_dict = payload.model_dump(mode='json')
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
        unit=payload.unit,
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
