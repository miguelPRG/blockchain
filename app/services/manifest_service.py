"""Lógica de negócios para criação de manifesto com repositório off-chain e âncora blockchain."""

import logging
import sys
import json
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.hashing import sha256_hex, canonical_json_readable
from app.core.security import verify_signature
from app.schemas.manifest import ManifestCreateRequest, ManifestResponse
from app.models.manifest import Manifest as ManifestModel
from app.services.blockchain_service import anchor_hash, decode_anchor_tx
from app.services.deploy_service import auto_deploy_if_needed

logger = logging.getLogger(__name__)


def create_manifest(db: Session, request: ManifestCreateRequest) -> ManifestResponse:
    """
    Criar manifesto no repositório local e ancorar o hash na blockchain.
    
    Validações:
    - Assinatura ECDSA válida
    - Manifesto ID único
    - Contrato está deploiado
    - Hash é ancorado na blockchain
    """
    payload = request.payload

    # Verificar se manifesto já existe no repositório local
    existing = db.query(ManifestModel).filter(ManifestModel.manifest_id == payload.manifest_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Manifest ID '{payload.manifest_id}' already exists."
        )

    # Calcular hash do payload
    payload_dict = payload.model_dump(mode='json')
    canonical_readable = canonical_json_readable(payload_dict)
    sys.stderr.write(f"\n[API] CANONICAL JSON:\n{canonical_readable}\n")
    sys.stderr.flush()
    
    payload_hash = sha256_hex(payload_dict)
    logger.debug(f"Payload hash: {payload_hash}")
    
    # Verificar assinatura
    if not verify_signature(request.auth.public_key, payload_hash, request.auth.signature):
        logger.error(f"Signature verification failed for hash: {payload_hash}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid ECDSA signature.")

    # Garantir que contrato está deploiado
    if not auto_deploy_if_needed(verbose=True):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to deploy contract.")

    # Converter timestamp ISO para Unix timestamp para a blockchain
    timestamp_dt = datetime.fromisoformat(payload.timestamp)
    unix_timestamp = int(timestamp_dt.timestamp())

    # Ancorar o hash na blockchain
    anchor = anchor_hash(
        payload_hash=payload_hash,
        timestamp=unix_timestamp,
        item_id=payload.manifest_id,
    )
    
    if not anchor.anchored:
        logger.error(f"Falha ao ancorar hash do manifesto: {anchor.reason}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to anchor hash on blockchain: {anchor.reason}"
        )

    blockchain_anchor = decode_anchor_tx(anchor.tx_hash) if anchor.tx_hash else None
    if (
        not blockchain_anchor
        or blockchain_anchor["payload_hash"] != payload_hash
        or blockchain_anchor["item_id"] != payload.manifest_id
        or blockchain_anchor["status"] != 1
        or blockchain_anchor["function"] != "anchorHash"
    ):
        logger.error("Blockchain anchor does not match manifest payload. Manifest will not be stored.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Blockchain anchor does not match manifest payload. Manifest was not saved.",
        )
    
    logger.info(f"✅ Hash ancorado com sucesso: TX {anchor.tx_hash}")

    # Salvar no banco de dados (Repositório Off-chain)
    db_manifest = ManifestModel(
        manifest_id=payload.manifest_id,
        good_type=payload.good_type,
        quantity=payload.quantity,
        unit=payload.unit,
        ingredients_json=json.dumps(payload.ingredients),
        origin=payload.origin,
        sustainability=payload.sustainability,
        timestamp=payload.timestamp,
    )

    try:
        db.add(db_manifest)
        db.commit()
        db.refresh(db_manifest)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Integrity error while saving manifest to database."
        )

    return ManifestResponse(
        payload=payload,
        payload_hash=payload_hash,
        anchor={"tx_hash": anchor.tx_hash, "anchored": anchor.anchored, "reason": anchor.reason},
    )
