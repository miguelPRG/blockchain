"""Utilitários auxiliares para chave ECDSA, assinatura e endereço."""

import hashlib

from ecdsa import BadSignatureError, SECP256k1, SigningKey, VerifyingKey


def sign_hash(private_key_hex: str, hash_hex: str) -> str:
    """Assinar um digest (hash) com ECDSA.
    
    - private_key_hex: Chave privada (necessária para criar a assinatura)
    - hash_hex: Digest SHA-256 dos dados a assinar
    """
    # Remover prefixo 0x se existir
    clean_privkey = private_key_hex[2:] if private_key_hex.startswith("0x") else private_key_hex
    clean_hash = hash_hex[2:] if hash_hex.startswith("0x") else hash_hex
    
    key = SigningKey.from_string(bytes.fromhex(clean_privkey), curve=SECP256k1)
    signature = key.sign_deterministic(bytes.fromhex(clean_hash))
    return signature.hex()


def get_public_key_from_private(private_key_hex: str) -> str:
    """Derivar chave pública a partir da chave privada (SECP256k1).
    
    - private_key_hex: Chave privada em hex
    """
    private_key = SigningKey.from_string(bytes.fromhex(private_key_hex), curve=SECP256k1)
    public_key = private_key.verifying_key
    return public_key.to_string().hex()


def verify_signature(public_key_hex: str, hash_hex: str, signature_hex: str) -> bool:
    """Verificar assinatura ECDSA contra o digest.
    
    - public_key_hex: Chave pública (para validar a assinatura)
    - hash_hex: Digest SHA-256 dos dados originais
    - signature_hex: Assinatura a verificar
    """
    try:
        # Remover prefixo 0x se existir
        clean_pubkey = public_key_hex[2:] if public_key_hex.startswith("0x") else public_key_hex
        clean_hash = hash_hex[2:] if hash_hex.startswith("0x") else hash_hex
        clean_sig = signature_hex[2:] if signature_hex.startswith("0x") else signature_hex
        
        key = VerifyingKey.from_string(bytes.fromhex(clean_pubkey), curve=SECP256k1)
        return key.verify(bytes.fromhex(clean_sig), bytes.fromhex(clean_hash))
    except (BadSignatureError, ValueError):
        return False


def address_from_public_key(public_key_hex: str) -> str:
    """Derivar endereço Ethereum-like (0x + 40 hex chars) da chave pública.
    
    - public_key_hex: Chave pública (identificador único do utilizador)
    """
    clean_hex = public_key_hex[2:] if public_key_hex.startswith("0x") else public_key_hex
    digest = hashlib.sha256(bytes.fromhex(clean_hex)).hexdigest()
    return f"0x{digest[-40:]}"
