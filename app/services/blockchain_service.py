"""Integração Web3 para ancoragem de hash em Ethereum e verificação de prova."""

from dataclasses import dataclass

from web3 import Web3
from web3.exceptions import TransactionNotFound

from app.core.settings import settings

ANCHOR_ABI = [
    {
        "inputs": [
            {"internalType": "bytes32", "name": "_hash", "type": "bytes32"},
            {"internalType": "string", "name": "_manifestId", "type": "string"},
        ],
        "name": "anchorHash",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]


@dataclass(slots=True)
class AnchorResult:
    """Resultado de uma tentativa de ancorar um hash na cadeia."""

    tx_hash: str | None
    anchored: bool
    reason: str | None = None


def get_web3() -> Web3 | None:
    """Retornar um cliente Web3 se RPC estiver configurado, caso contrário None."""
    if not settings.spolia_rpc_url:
        return None
    return Web3(Web3.HTTPProvider(settings.spolia_rpc_url))


def check_connection_status() -> str:
    """Status de conectividade Sepolia legível para humanos para logs de inicialização."""
    client = get_web3()
    if client is None:
        return "SPOLIA_RPC_URL not configured."
    try:
        connected = client.is_connected()
        return "Connected to Mainnet RPC." if connected else "Unable to connect to Mainnet RPC."
    except Exception as exc:  # noqa: BLE001
        return f"Mainnet connection error: {exc}"


def anchor_hash(payload_hash: str, manifest_id: str) -> AnchorResult:
    """
    Ancorar hash SHA-256 em Sepolia através do contrato Anchor.sol.

    Retorna status gracioso se as configurações da cadeia ainda não estão configuradas.
    """
    w3 = get_web3()
    if w3 is None:
        return AnchorResult(tx_hash=None, anchored=False, reason="RPC URL not configured.")
    if not settings.contract_address:
        return AnchorResult(tx_hash=None, anchored=False, reason="Contract address not configured.")
    if not settings.private_key_for_deploy:
        return AnchorResult(tx_hash=None, anchored=False, reason="Private key not configured.")

    account = w3.eth.account.from_key(settings.private_key_for_deploy)
    contract = w3.eth.contract(address=Web3.to_checksum_address(settings.contract_address), abi=ANCHOR_ABI)
    nonce = w3.eth.get_transaction_count(account.address)
    txn = contract.functions.anchorHash(bytes.fromhex(payload_hash), manifest_id).build_transaction(
        {
            "from": account.address,
            "nonce": nonce,
            "gas": 200000,
            "gasPrice": w3.eth.gas_price,
        }
    )
    signed = w3.eth.account.sign_transaction(txn, private_key=settings.private_key_for_deploy)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return AnchorResult(tx_hash=tx_hash.hex(), anchored=True, reason=None)


def verify_tx_exists(tx_hash: str | None) -> bool:
    """Verificar se hash tx existe em Mainnet (prova básica de presença)."""
    if not tx_hash:
        return False
    w3 = get_web3()
    if w3 is None:
        return False
    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        return receipt is not None and receipt.get("status", 0) == 1
    except (TransactionNotFound, ValueError):
        return False
