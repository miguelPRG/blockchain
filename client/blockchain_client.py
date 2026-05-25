"""Operações blockchain executadas localmente pelo cliente."""

from eth_account import Account

from client.api_client import post_json
from client.config import BASE_URL
from shared.transaction_signing import sign_prepared_transaction


def deploy_contract_locally(manager_private_key: str) -> str | None:
    """Preparar deployment no backend, assinar no CLI e publicar a raw tx."""
    account = Account.from_key(manager_private_key)
    prepared = post_json(
        f"{BASE_URL}/config/prepare-deploy-contract",
        {"from_address": account.address},
    )
    transaction = prepared.get("transaction")
    if not transaction:
        return None

    signed_transaction = sign_prepared_transaction(
        transaction=transaction,
        signer_private_key=manager_private_key,
    )
    result = post_json(
        f"{BASE_URL}/config/broadcast-deploy-contract",
        {"signed_transaction": signed_transaction},
    )
    return result.get("contract_address")
