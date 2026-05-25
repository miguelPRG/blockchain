"""Lógica de negócios para criação de manifesto com repositório off-chain e âncora blockchain."""

import logging
import sys
import json
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from shared.hashing import sha256_hex, canonical_json_readable
from shared.security import (
    ethereum_address_from_public_key,
)
from app.schemas.manifest import ManifestCreateRequest, ManifestResponse
from app.models.manifest import Manifest as ManifestModel
from app.services.blockchain_service import broadcast_signed_anchor_transaction, decode_anchor_tx
from app.services.signature_service import validate_dual_signature

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
    creator_address = ethereum_address_from_public_key(request.auth.public_key)

    if request.role != "PRODUCER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manifest creation requires PRODUCER role.",
        )

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
    
    validate_dual_signature(
        auth=request.auth,
        payload_hash=payload_hash,
    )

    tx_hash = request.tx_hash
    expected_sender = creator_address

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
                detail=f"Blockchain anchor failed. Manifest was not saved. Reason: {anchor.reason}",
            )

        tx_hash = anchor.tx_hash

    # Validar a transação que acabou de ser criada, ou o TXID enviado pelo cliente.
    blockchain_anchor = decode_anchor_tx(tx_hash, request.contract_address)
    if (
        not blockchain_anchor
        or blockchain_anchor["payload_hash"] != payload_hash
        or blockchain_anchor["item_id"] != payload.manifest_id
        or blockchain_anchor["status"] != 1
        or blockchain_anchor["function"] != "anchorHash"
        or not blockchain_anchor.get("from_address")
        or blockchain_anchor["from_address"].lower() != expected_sender.lower()
    ):
        logger.error("Blockchain anchor does not match manifest payload. Manifest will not be stored.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Blockchain anchor does not match manifest payload. Manifest was not saved.",
        )
    
    logger.info(f"✅ Hash ancorado com sucesso: TX {tx_hash}")

    # Só depois de validar o TXID guardamos o manifesto off-chain.
    db_manifest = ManifestModel(
        manifest_id=payload.manifest_id,
        good_type=payload.good_type,
        quantity=payload.quantity,
        unit=payload.unit,
        ingredients_json=json.dumps(payload.ingredients),
        origin=payload.origin,
        sustainability=payload.sustainability,
        creator=creator_address,
        timestamp=payload.timestamp,
        payload_hash=payload_hash,
        signature=request.auth.signature,
        public_key=request.auth.public_key,
        manager_signature=request.auth.manager_signature,
        manager_public_key=request.auth.manager_public_key,
        contract_address=request.contract_address,
        tx_hash=tx_hash,
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
        contract_address=request.contract_address,
        tx_hash=tx_hash,
        anchor={"tx_hash": tx_hash, "anchored": True, "reason": None},
    )
