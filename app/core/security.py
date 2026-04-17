"""Utilitários auxiliares para chave ECDSA, assinatura e endereço."""

import hashlib

from ecdsa import BadSignatureError, SECP256k1, SigningKey, VerifyingKey


def generate_key_pair_hex() -> tuple[str, str]:
    """Gerar par de chaves ECDSA privada/pública codificadas como strings hex."""
    private_key = SigningKey.generate(curve=SECP256k1)
    public_key = private_key.verifying_key
    return private_key.to_string().hex(), public_key.to_string().hex()


def sign_hash(private_key_hex: str, hash_hex: str) -> str:
    """Assinar um digest de hash representado como hex usando ECDSA."""
    key = SigningKey.from_string(bytes.fromhex(private_key_hex), curve=SECP256k1)
    signature = key.sign_deterministic(bytes.fromhex(hash_hex))
    return signature.hex()


def verify_signature(public_key_hex: str, hash_hex: str, signature_hex: str) -> bool:
    """Verificar assinatura ECDSA contra o digest de hash fornecido."""
    try:
        key = VerifyingKey.from_string(bytes.fromhex(public_key_hex), curve=SECP256k1)
        return key.verify(bytes.fromhex(signature_hex), bytes.fromhex(hash_hex))
    except (BadSignatureError, ValueError):
        return False


def address_from_public_key(public_key_hex: str) -> str:
    """Construir um pseudo-endereço a partir da chave pública para identificação do usuário."""
    digest = hashlib.sha256(bytes.fromhex(public_key_hex)).hexdigest()
    return f"0x{digest[-40:]}"
