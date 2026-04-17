"""Serviço de verificação independente para integridade e não-repúdio."""

from app.core.hashing import sha256_hex
from app.core.security import verify_signature
from app.schemas.verification import VerificationRequest, VerificationResponse
from app.services.blockchain_service import verify_tx_exists


def verify_payload(request: VerificationRequest) -> VerificationResponse:
    """Recomputar hash, verificar assinatura e verificar evidência de tx blockchain."""
    recomputed_hash = sha256_hex(request.payload)
    hash_matches = recomputed_hash == request.expected_hash
    signature_valid = verify_signature(request.public_key, recomputed_hash, request.signature)
    blockchain_proof_valid = verify_tx_exists(request.tx_hash) if request.tx_hash else False
    overall = hash_matches and signature_valid and (blockchain_proof_valid or request.tx_hash is None)
    return VerificationResponse(
        recomputed_hash=recomputed_hash,
        hash_matches=hash_matches,
        signature_valid=signature_valid,
        blockchain_proof_valid=blockchain_proof_valid,
        overall_valid=overall,
    )
