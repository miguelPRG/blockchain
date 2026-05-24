"""Serviço de verificação independente para integridade e não-repúdio."""

from shared.hashing import sha256_hex
from shared.security import verify_signature
from app.schemas.verification import VerificationRequest, VerificationResponse
from app.services.blockchain_service import decode_anchor_tx

def verify_payload(request: VerificationRequest) -> VerificationResponse:
    """Recomputar hash e comparar com a prova ancorada na blockchain."""
    recomputed_hash = sha256_hex(request.payload)
    hash_matches = recomputed_hash == request.expected_hash if request.expected_hash else None

    signature_valid = None
    if request.public_key and request.signature:
        signature_valid = verify_signature(request.public_key, recomputed_hash, request.signature)

    blockchain_tx = decode_anchor_tx(request.tx_hash) if request.tx_hash else None
    blockchain_payload_hash = blockchain_tx["payload_hash"] if blockchain_tx else None
    blockchain_item_id = blockchain_tx["item_id"] if blockchain_tx else None
    blockchain_hash_matches = (
        recomputed_hash == blockchain_payload_hash
        if blockchain_payload_hash is not None
        else None
    )
    blockchain_tx_valid = blockchain_tx["status"] == 1 and blockchain_tx["function"] == "anchorHash" if blockchain_tx else None
    if request.tx_hash and blockchain_tx is None:
        blockchain_tx_valid = False
        blockchain_hash_matches = False
    blockchain_item_matches = (
        blockchain_item_id == request.item_id
        if blockchain_item_id is not None and request.item_id is not None
        else None
    )

    # Lógica de verificação SIMPLES:
    # É válido se o hash na blockchain corresponde ao hash recalculado
    # FIM. Esquece o resto.
    
    overall_valid = blockchain_hash_matches is True if request.tx_hash else False
    
    return VerificationResponse(
        payload=request.payload,
        recomputed_hash=recomputed_hash,
        hash_matches=hash_matches,
        signature_valid=signature_valid,
        blockchain_payload_hash=blockchain_payload_hash,
        blockchain_hash_matches=blockchain_hash_matches,
        blockchain_tx_valid=blockchain_tx_valid,
        blockchain_item_id=blockchain_item_id,
        blockchain_item_matches=blockchain_item_matches,
        block_number=blockchain_tx["block"] if blockchain_tx else None,
        overall_valid=overall_valid,
    )
