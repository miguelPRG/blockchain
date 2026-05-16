"""Lógica de negócios para criação de registo com repositório off-chain e validação de quantidades."""

import logging
import sys
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.hashing import sha256_hex, canonical_json_readable
from app.core.security import verify_signature
from app.schemas.record import RecordCreateRequest, RecordResponse, RecordType
from app.models.manifest import Manifest as ManifestModel
from app.models.record import Record as RecordModel
from app.services.blockchain_service import anchor_hash, decode_anchor_tx
from app.services.deploy_service import auto_deploy_if_needed

logger = logging.getLogger(__name__)


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

    # 2. Computar quantidade disponível baseada nos registos existentes (se aplicável para validação)
    # Exemplo: não podemos transferir/receber/entregar mais do que o produzido
    # Vamos considerar que o manifest define a quantidade máxima
    
    # Validação rigorosa de quantidades:
    if payload.record_type != RecordType.PRODUCED:
        # Se não for produção, precisamos verificar se há o suficiente já produzido/disponível
        # (Nesta implementação simplificada, assumimos que as operações não podem exceder o valor do manifesto)
        if payload.quantity > manifest.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Operation quantity ({payload.quantity}) exceeds manifest total quantity ({manifest.quantity})."
            )
        
        # Pode-se implementar lógicas mais complexas aqui dependendo do ciclo de vida,
        # como verificar a soma de TRANSFERs vs PRODUCED.

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

    # Garantir que contrato está deploiado
    if not auto_deploy_if_needed(verbose=False):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to deploy contract.")

    # Converter timestamp ISO para Unix timestamp
    timestamp_dt = datetime.fromisoformat(payload.timestamp)
    unix_timestamp = int(timestamp_dt.timestamp())

    # Ancorar o hash na blockchain
    anchor = anchor_hash(
        payload_hash=payload_hash,
        timestamp=unix_timestamp,
        item_id=payload.record_id,
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
        timestamp=payload.timestamp,
        notes=payload.notes,
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
