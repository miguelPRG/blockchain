"""Utilitários auxiliares para chave ECDSA, assinatura e endereço."""

import hashlib
import logging
import os

from ecdsa import BadSignatureError, SECP256k1, SigningKey, VerifyingKey
from eth_account import Account


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


def address_from_private_key(private_key_hex: str) -> str:
    """Derivar endereço Ethereum correto (20 bytes) a partir da chave privada.
    
    Usa Keccak-256 (correto para Ethereum), não SHA-256.
    - private_key_hex: Chave privada com ou sem prefixo 0x
    """
    try:
        account = Account.from_key(private_key_hex)
        return account.address
    except Exception:
        return "0x0000000000000000000000000000000000000000"


def address_from_public_key(public_key_hex: str) -> str:
    """Derivar endereço Ethereum-like (0x + 40 hex chars) da chave pública.
    
    ⚠️ DEPRECADO: Use address_from_private_key() para endereços corretos.
    Esta função usa SHA-256 (incorreto) e está mantida por compatibilidade.
    
    - public_key_hex: Chave pública (identificador único do utilizador)
    """
    clean_hex = public_key_hex[2:] if public_key_hex.startswith("0x") else public_key_hex
    digest = hashlib.sha256(bytes.fromhex(clean_hex)).hexdigest()
    return f"0x{digest[-40:]}"


def get_private_key_from_signer_id(signer_id: str | None) -> str | None:
    """Recupera a chave privada a partir do ID do utilizador (alice/bob/charlie).
    
    Args:
        signer_id: ID do utilizador ("alice", "bob", "charlie", etc.)
    
    Returns:
        Chave privada com prefixo 0x, ou None se não encontrada
    """
    logger = logging.getLogger(__name__)

    if not signer_id:
        logger.warning("[get_private_key_from_signer_id] signer_id is empty")
        return None

    signer_id_lower = signer_id.lower()
    
    # Mapear ID para variável de ambiente
    env_map = {
        "alice": "ALICE_KEY",
        "bob": "BOB_KEY",
        "charlie": "CHARLIE_KEY",
    }
    
    env_var = env_map.get(signer_id_lower)
    if not env_var:
        logger.warning(f"[get_private_key_from_signer_id] Unknown signer_id: {signer_id}")
        return None
    
    priv = os.getenv(env_var)
    if not priv:
        logger.warning(f"[get_private_key_from_signer_id] {env_var} not set in environment")
        return None
    
    logger.info(f"[get_private_key_from_signer_id] ✓ FOUND: {env_var}")
    return priv if priv.startswith("0x") else f"0x{priv}"



