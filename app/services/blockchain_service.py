"""Integração Web3 para ancoragem de hash em Ethereum e verificação de prova."""
import logging
from dataclasses import dataclass

from web3 import Web3
from web3.exceptions import TransactionNotFound

from app.core.settings import settings

logger = logging.getLogger(__name__)

# ABI do contrato Solidity: contracts/Anchor.sol
# Defines the interface for calling anchorManifest() function on-chain
# 
# EXPLICAÇÃO DA LIGAÇÃO:
# =====================
# O ABI (Application Binary Interface) abaixo é um "mapa" que Python usa
# para comunicar com o contrato Anchor.sol na blockchain.
#
# Cada função no ABI corresponde a uma função em Anchor.sol:
#
# ✅ anchorManifest() em Python → anchorManifest() em Solidity
#    - Recebe: hash, manifestId, goodType, quantity, unit, ingredients, origin, sustainability, timestamp
#    - Guarda: Dados completos do manifesto na blockchain (imutável)
#    - Emite: Evento ManifestAnchored com dados indexados
#
# ✅ getManifest() em Python → getManifest() em Solidity
#    - Recebe: hash do manifesto
#    - Retorna: Struct Manifest com todos os dados guardados
#
# ✅ isAnchored() em Python → isAnchored() em Solidity
#    - Recebe: hash do manifesto
#    - Retorna: bool indicando se foi ancorado
#
ANCHOR_ABI = [
    {
        "inputs": [
            {"internalType": "bytes32", "name": "_hash", "type": "bytes32"},
            {"internalType": "string", "name": "_manifestId", "type": "string"},
            {"internalType": "string", "name": "_goodType", "type": "string"},
            {"internalType": "uint256", "name": "_quantity", "type": "uint256"},
            {"internalType": "string", "name": "_unit", "type": "string"},
            {"internalType": "string[]", "name": "_ingredients", "type": "string[]"},
            {"internalType": "string", "name": "_origin", "type": "string"},
            {"internalType": "string", "name": "_sustainability", "type": "string"},
            {"internalType": "uint256", "name": "_timestamp", "type": "uint256"},
        ],
        "name": "anchorManifest",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "bytes32", "name": "_hash", "type": "bytes32"}],
        "name": "getManifest",
        "outputs": [
            {
                "components": [
                    {"internalType": "bool", "name": "exists", "type": "bool"},
                    {"internalType": "bytes32", "name": "hash", "type": "bytes32"},
                    {"internalType": "string", "name": "goodType", "type": "string"},
                    {"internalType": "uint256", "name": "quantity", "type": "uint256"},
                    {"internalType": "string", "name": "unit", "type": "string"},
                    {"internalType": "string[]", "name": "ingredients", "type": "string[]"},
                    {"internalType": "string", "name": "origin", "type": "string"},
                    {"internalType": "string", "name": "sustainability", "type": "string"},
                    {"internalType": "address", "name": "creator", "type": "address"},
                    {"internalType": "uint256", "name": "timestamp", "type": "uint256"},
                ],
                "internalType": "struct Anchor.Manifest",
                "name": "",
                "type": "tuple",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "bytes32", "name": "_hash", "type": "bytes32"}],
        "name": "isAnchored",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
]


@dataclass(slots=True)
class AnchorResult:
    """Resultado de uma tentativa de ancorar um hash na cadeia."""

    tx_hash: str | None
    anchored: bool
    reason: str | None = None


def get_web3() -> Web3 | None:
    """Retornar um cliente Web3 se RPC estiver configurado, caso contrário None."""
    if not settings.sepolia_rpc_url:
        return None
    return Web3(Web3.HTTPProvider(settings.sepolia_rpc_url))


def check_connection_status() -> str:
    """Status de conectividade Sepolia legível para humanos para logs de inicialização."""
    client = get_web3()
    if client is None:
        return "sepolia_rpc_url not configured."
    try:
        connected = client.is_connected()
        return "Connected to Sepolia RPC." if connected else "Unable to connect to Sepolia RPC."
    except Exception as exc:  # noqa: BLE001
        return f"Sepolia connection error: {exc}"


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


def anchor_manifest(
    payload_hash: str,
    manifest_id: str,
    good_type: str,
    quantity: int,
    unit: str,
    ingredients: list[str],
    origin: str,
    sustainability: str,
    timestamp: int,
) -> AnchorResult:
    """
    Ancorar manifesto completo na blockchain Sepolia com todos os dados.
    
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
    
    # Log de informações de deployment
    logger.info("=" * 80)
    logger.info("📦 DEPLOYMENT DE MANIFESTO NA BLOCKCHAIN SEPOLIA")
    logger.info("=" * 80)
    logger.info(f"[CONTRATO] Endereço: {settings.contract_address}")
    logger.info(f"[CONTA] Sender: {account.address}")
    logger.info(f"[NONCE] {nonce}")
    logger.info("")
    logger.info("📋 DADOS DO MANIFESTO:")
    logger.info(f"  • ID: {manifest_id}")
    logger.info(f"  • Tipo: {good_type}")
    logger.info(f"  • Quantidade: {quantity} {unit}")
    logger.info(f"  • Ingredientes: {', '.join(ingredients)}")
    logger.info(f"  • Origem: {origin}")
    logger.info(f"  • Sustentabilidade: {sustainability}")
    logger.info(f"  • Timestamp: {timestamp}")
    logger.info(f"  • Hash: {payload_hash}")
    logger.info("")
    
    txn = contract.functions.anchorManifest(
        bytes.fromhex(payload_hash),
        manifest_id,
        good_type,
        quantity,
        unit,
        ingredients,
        origin,
        sustainability,
        timestamp,
    ).build_transaction(
        {
            "from": account.address,
            "nonce": nonce,
            "gas": 400000,  # Aumentado para acomodar dados estruturados completos
            "gasPrice": w3.eth.gas_price,
        }
    )
    
    gas_price_gwei = w3.from_wei(txn["gasPrice"], "gwei")
    logger.info("⛽ CONFIGURAÇÃO DE GAS:")
    logger.info(f"  • Gas Limit: {txn['gas']}")
    logger.info(f"  • Gas Price: {gas_price_gwei} Gwei")
    logger.info(f"  • Estimativa de Custo: {w3.from_wei(txn['gas'] * txn['gasPrice'], 'ether')} ETH")
    logger.info("")
    
    signed = w3.eth.account.sign_transaction(txn, private_key=settings.private_key_for_deploy)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    
    tx_hash_hex = tx_hash.hex()
    logger.info("🚀 TRANSAÇÃO ENVIADA:")
    logger.info(f"  • TX Hash: {tx_hash_hex}")
    logger.info(f"  • Sepolia Explorer: https://sepolia.etherscan.io/tx/{tx_hash_hex}")
    logger.info("")
    logger.info("⏳ Aguardando confirmação na blockchain...")
    logger.info("=" * 80)
    
    return AnchorResult(tx_hash=tx_hash_hex, anchored=True, reason=None)



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
