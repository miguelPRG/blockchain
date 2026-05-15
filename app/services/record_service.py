"""Lógica de negócios para criação de registo blockchain-only."""

import logging
import sys
from datetime import datetime
from fastapi import HTTPException, status

from app.core.hashing import sha256_hex, canonical_json_readable
from app.core.security import verify_signature
from app.schemas.record import RecordCreateRequest, RecordResponse, RecordType
from app.services.blockchain_service import create_record as create_record_on_chain, manifest_exists
from app.services.deploy_service import auto_deploy_if_needed

logger = logging.getLogger(__name__)


def create_record(request: RecordCreateRequest) -> RecordResponse:
    """
    Criar registo direto na blockchain com validação de manifesto.
    
    Validações:
    - Manifesto DEVE existir na blockchain
    - Assinatura ECDSA válida
    - Contrato está deploiado
    
    Nota: User é derivado automaticamente do msg.sender (chave privada do backend)
    """
    payload = request.payload
    logger.info(f"Criando registo para manifesto: {payload.manifest_id}")
    
    # Verificar que manifesto existe na blockchain
    if not manifest_exists(payload.manifest_id):
        logger.error(f"Manifesto não encontrado: {payload.manifest_id}")
        sys.stderr.write(f"[API RECORD] Manifesto não encontrado na blockchain: {payload.manifest_id}\n")
        sys.stderr.flush()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Manifest '{payload.manifest_id}' does not exist on blockchain. Create it first."
        )

    # Calcular hash do payload
    payload_dict = payload.model_dump(mode='json')
    logger.debug("=== RECORD SERVICE PAYLOAD ===")
    logger.debug(payload_dict)
    logger.debug("==============================")
    
    canonical_readable = canonical_json_readable(payload_dict)
    sys.stderr.write(f"\n[API RECORD] CANONICAL JSON:\n{canonical_readable}\n")
    sys.stderr.flush()
    
    payload_hash = sha256_hex(payload_dict)
    logger.debug(f"Payload hash: {payload_hash}")
    sys.stderr.write(f"[API RECORD] PAYLOAD HASH: {payload_hash}\n")
    sys.stderr.write(f"[API RECORD] PUBLIC KEY: {request.auth.public_key}\n")
    sys.stderr.write(f"[API RECORD] SIGNATURE: {request.auth.signature}\n")
    sys.stderr.flush()
    
    # Verificar assinatura
    if not verify_signature(request.auth.public_key, payload_hash, request.auth.signature):
        logger.error(f"Signature verification failed for hash: {payload_hash}")
        sys.stderr.write(f"[API RECORD] VERIFICATION FAILED!\n")
        sys.stderr.flush()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid ECDSA signature.")

    # Garantir que contrato está deploiado
    if not auto_deploy_if_needed(verbose=False):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to deploy contract.")

    # Converter timestamp ISO para Unix timestamp
    timestamp_dt = datetime.fromisoformat(payload.timestamp)
    unix_timestamp = int(timestamp_dt.timestamp())

    # Criar registo na blockchain
    anchor = create_record_on_chain(
        record_id=payload.record_id,
        manifest_id=payload.manifest_id,
        payload_hash=payload_hash,
        record_type=payload.record_type.value,
        quantity=int(payload.quantity),
        unit=payload.unit,
        timestamp=unix_timestamp,
    )
    
    if not anchor.anchored:
        logger.error(f"Falha ao criar registo: {anchor.reason}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create record on blockchain: {anchor.reason}"
        )
    
    logger.info(f"✅ Registo criado com sucesso: TX {anchor.tx_hash}")
    return RecordResponse(
        payload=payload,
        payload_hash=payload_hash,
        anchor={"tx_hash": anchor.tx_hash, "anchored": anchor.anchored, "reason": anchor.reason},
    )
