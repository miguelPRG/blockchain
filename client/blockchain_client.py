"""Operações blockchain executadas localmente pelo cliente."""

from client.api_client import post_json
from client.config import BASE_URL


def deploy_contract_locally(_: str | None = None) -> str | None:
    """Pedir ao backend para publicar o contrato."""
    result = post_json(f"{BASE_URL}/config/deploy-contract", {})
    return result.get("contract_address")
