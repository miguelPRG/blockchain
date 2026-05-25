"""Construção de requests assinados para manifestos e registos."""

from datetime import datetime
from typing import Any

from client.api_client import post_json
from client.config import BASE_URL
from shared.hashing import sha256_hex
from shared.security import address_from_private_key, public_key_from_private_key, sign_hash
from shared.transaction_signing import sign_prepared_transaction


def create_signed_request(
    *,
    payload: dict[str, Any],
    user_private_key: str,
    manager_private_key: str,
    role: str,
    contract_address: str,
    item_id: str,
    timestamp_iso: str,
) -> tuple[dict[str, Any], str]:
    """Assinar payload e transação preparada pelo backend para enviar à API.

    Passos:
    1. Calcula o SHA-256 canónico do payload.
    2. Assina esse hash com a chave privada do user.
    3. Assina o mesmo hash com a chave privada do Supply Manager.
    4. Pede ao backend uma transação anchorHash sem assinatura.
    5. Assina essa transação localmente com a chave privada do user.
    6. Envia para a API apenas payload, chaves públicas, assinaturas, role,
       contract_address e signed_anchor_tx.

    O request final contém exatamente:
    - payload: dados funcionais do manifesto/registo.
    - auth.public_key: chave pública derivada da chave privada do user.
    - auth.signature: assinatura do user sobre o hash do payload.
    - auth.manager_public_key: chave pública derivada da chave do Supply Manager.
    - auth.manager_signature: assinatura do Supply Manager sobre o mesmo hash.
    - role, contract_address e signed_anchor_tx: contexto para validação da TX.
    """
    payload_hash = sha256_hex(payload)
    unix_timestamp = int(datetime.fromisoformat(timestamp_iso).timestamp())

    auth = {
        "public_key": public_key_from_private_key(user_private_key),
        "signature": sign_hash(user_private_key, payload_hash),
        "manager_public_key": public_key_from_private_key(manager_private_key),
        "manager_signature": sign_hash(manager_private_key, payload_hash),
    }
    request_body = {
        "payload": payload,
        "auth": auth,
        "role": role,
        "contract_address": contract_address,
        "signed_anchor_tx": _prepare_and_sign_anchor_tx(
            payload_hash=payload_hash,
            timestamp=unix_timestamp,
            item_id=item_id,
            contract_address=contract_address,
            user_private_key=user_private_key,
        ),
    }
    return request_body, payload_hash


def create_signed_api_request(
    *,
    payload: dict[str, Any],
    user_private_key: str,
    manager_private_key: str,
    role: str,
    contract_address: str,
    item_id: str,
    timestamp_iso: str,
) -> tuple[dict[str, Any], str]:
    """Criar body assinado com transação blockchain assinada pelo user.

    A chave privada nunca é enviada à API. O CLI assina a transação localmente,
    e o backend recebe apenas a transação já assinada para fazer broadcast e
    obter o tx_hash.
    """
    payload_hash = sha256_hex(payload)
    unix_timestamp = int(datetime.fromisoformat(timestamp_iso).timestamp())
    signed_anchor_tx = _prepare_and_sign_anchor_tx(
        payload_hash=payload_hash,
        timestamp=unix_timestamp,
        item_id=item_id,
        contract_address=contract_address,
        user_private_key=user_private_key,
    )
    auth = {
        "public_key": public_key_from_private_key(user_private_key),
        "signature": sign_hash(user_private_key, payload_hash),
        "manager_public_key": public_key_from_private_key(manager_private_key),
        "manager_signature": sign_hash(manager_private_key, payload_hash),
    }
    request_body = {
        "payload": payload,
        "auth": auth,
        "role": role,
        "contract_address": contract_address,
        "signed_anchor_tx": signed_anchor_tx,
    }
    return request_body, payload_hash


def _prepare_and_sign_anchor_tx(
    *,
    payload_hash: str,
    timestamp: int,
    item_id: str,
    contract_address: str,
    user_private_key: str,
) -> str:
    """Pedir ao backend uma TX sem assinatura e assiná-la localmente."""
    result = post_json(
        f"{BASE_URL}/config/prepare-anchor-transaction",
        {
            "payload_hash": payload_hash,
            "timestamp": timestamp,
            "item_id": item_id,
            "contract_address": contract_address,
            "from_address": address_from_private_key(user_private_key),
        },
    )
    transaction = result.get("transaction")
    if not transaction:
        raise RuntimeError("Backend failed to prepare anchor transaction.")

    return sign_prepared_transaction(
        transaction=transaction,
        signer_private_key=user_private_key,
    )
