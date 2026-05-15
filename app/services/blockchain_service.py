"""Integração Web3 para armazenamento blockchain-only (sem SQLAlchemy)."""
import logging
from dataclasses import dataclass

from web3 import Web3
from web3.exceptions import TransactionNotFound

from app.core.settings import settings

logger = logging.getLogger(__name__)

# ABI do contrato Solidity: contracts/Anchor.sol
# Nova abordagem: Blockchain-only, sem cache SQLAlchemy
# 
# EXPLICAÇÃO:
# ===========
# O ABI mapeia as funções Solidity para chamadas Python:
#
# ✅ createManifest() - Armazenar manifesto completo por ID
#    - Recebe: manifestId, hash, goodType, quantity, unit, ingredients, origin, sustainability, timestamp
#    - Guarda: Struct Manifest (imutável)
#    - Validação: manifestId não pode estar duplicado
#
# ✅ createRecord() - Armazenar registo com validação de manifesto
#    - Recebe: recordId, manifestId, hash, recordType, quantity, unit, timestamp
#    - Validação: manifestId DEVE existir na blockchain
#    - Emite: RecordCreated ou RecordRejected
#
# ✅ manifestExists() - Verificar se manifesto existe por ID
#    - Recebe: manifestId (string)
#    - Retorna: bool
#
# ✅ getManifestById() - Recuperar manifesto por ID
#    - Recebe: manifestId
#    - Retorna: Struct Manifest com todos os dados
#
ANCHOR_ABI = [
    {
        "inputs": [
            {"internalType": "string", "name": "_manifestId", "type": "string"},
            {"internalType": "bytes32", "name": "_hash", "type": "bytes32"},
            {"internalType": "string", "name": "_goodType", "type": "string"},
            {"internalType": "uint256", "name": "_quantity", "type": "uint256"},
            {"internalType": "string", "name": "_unit", "type": "string"},
            {"internalType": "string[]", "name": "_ingredients", "type": "string[]"},
            {"internalType": "string", "name": "_origin", "type": "string"},
            {"internalType": "string", "name": "_sustainability", "type": "string"},
            {"internalType": "uint256", "name": "_timestamp", "type": "uint256"},
        ],
        "name": "createManifest",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "string", "name": "_recordId", "type": "string"},
            {"internalType": "string", "name": "_manifestId", "type": "string"},
            {"internalType": "bytes32", "name": "_hash", "type": "bytes32"},
            {"internalType": "string", "name": "_recordType", "type": "string"},
            {"internalType": "uint256", "name": "_quantity", "type": "uint256"},
            {"internalType": "string", "name": "_unit", "type": "string"},
            {"internalType": "uint256", "name": "_timestamp", "type": "uint256"},
        ],
        "name": "createRecord",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "string", "name": "_manifestId", "type": "string"}],
        "name": "manifestExists",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "string", "name": "_manifestId", "type": "string"}],
        "name": "getManifestById",
        "outputs": [
            {
                "components": [
                    {"internalType": "bool", "name": "exists", "type": "bool"},
                    {"internalType": "bytes32", "name": "hash", "type": "bytes32"},
                    {"internalType": "string", "name": "manifestId", "type": "string"},
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
        "inputs": [{"internalType": "string", "name": "_recordId", "type": "string"}],
        "name": "getRecordById",
        "outputs": [
            {
                "components": [
                    {"internalType": "bool", "name": "exists", "type": "bool"},
                    {"internalType": "bytes32", "name": "hash", "type": "bytes32"},
                    {"internalType": "string", "name": "recordId", "type": "string"},
                    {"internalType": "string", "name": "manifestId", "type": "string"},
                    {"internalType": "string", "name": "recordType", "type": "string"},
                    {"internalType": "uint256", "name": "quantity", "type": "uint256"},
                    {"internalType": "string", "name": "unit", "type": "string"},
                    {"internalType": "address", "name": "user", "type": "address"},
                    {"internalType": "uint256", "name": "timestamp", "type": "uint256"},
                ],
                "internalType": "struct Anchor.Record",
                "name": "",
                "type": "tuple",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
]


@dataclass(slots=True)
class AnchorResult:
    """Resultado de uma tentativa de criar um manifesto/registo na blockchain."""

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


def create_manifest(
    manifest_id: str,
    payload_hash: str,
    good_type: str,
    quantity: int,
    unit: str,
    ingredients: list[str],
    origin: str,
    sustainability: str,
    timestamp: int,
) -> AnchorResult:
    """
    Criar manifesto direto na blockchain Sepolia com todos os dados.
    
    Blockchain é a única fonte de verdade - sem cache SQLAlchemy.
    """
    w3 = get_web3()
    if w3 is None:
        return AnchorResult(tx_hash=None, anchored=False, reason="RPC URL not configured.")
    if not settings.contract_address or settings.contract_address == "0x0000000000000000000000000000000000000000":
        return AnchorResult(tx_hash=None, anchored=False, reason="Contract address not configured.")
    if not settings.private_key_for_deploy:
        return AnchorResult(tx_hash=None, anchored=False, reason="Private key not configured.")

    account = w3.eth.account.from_key(settings.private_key_for_deploy)
    contract = w3.eth.contract(address=Web3.to_checksum_address(settings.contract_address), abi=ANCHOR_ABI)
    nonce = w3.eth.get_transaction_count(account.address)
    
    logger.info("=" * 80)
    logger.info("📦 CRIAR MANIFESTO NA BLOCKCHAIN SEPOLIA")
    logger.info("=" * 80)
    logger.info(f"[CONTRATO] {settings.contract_address}")
    logger.info(f"[CONTA] {account.address}")
    logger.info(f"[NONCE] {nonce}")
    logger.info("")
    logger.info("📋 DADOS DO MANIFESTO:")
    logger.info(f"  • ID: {manifest_id}")
    logger.info(f"  • Hash: {payload_hash}")
    logger.info(f"  • Tipo: {good_type}")
    logger.info(f"  • Quantidade: {quantity} {unit}")
    logger.info(f"  • Ingredientes: {', '.join(ingredients)}")
    logger.info(f"  • Origem: {origin}")
    logger.info(f"  • Sustentabilidade: {sustainability}")
    logger.info(f"  • Timestamp: {timestamp}")
    logger.info("")
    
    try:
        txn = contract.functions.createManifest(
            manifest_id,
            bytes.fromhex(payload_hash),
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
                "gas": 500000,
                "gasPrice": w3.eth.gas_price,
            }
        )
        
        gas_price_gwei = w3.from_wei(txn["gasPrice"], "gwei")
        logger.info("⛽ GAS:")
        logger.info(f"  • Limite: {txn['gas']}")
        logger.info(f"  • Preço: {gas_price_gwei} Gwei")
        logger.info(f"  • Estimativa: {w3.from_wei(txn['gas'] * txn['gasPrice'], 'ether')} ETH")
        logger.info("")
        
        signed = w3.eth.account.sign_transaction(txn, private_key=settings.private_key_for_deploy)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        
        tx_hash_hex = tx_hash.hex()
        logger.info(f"🚀 TX: {tx_hash_hex}")
        logger.info(f"   https://sepolia.etherscan.io/tx/{tx_hash_hex}")
        logger.info("⏳ Aguardando confirmação...")
        
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        if receipt["status"] != 1:
            logger.error(f"❌ Transação falhou: status={receipt['status']}")
            logger.info("=" * 80)
            return AnchorResult(tx_hash=tx_hash_hex, anchored=False, reason="Transaction failed on chain")
        
        logger.info(f"✅ Manifesto criado com sucesso!")
        logger.info(f"   Bloco: {receipt['blockNumber']}")
        logger.info("=" * 80)
        return AnchorResult(tx_hash=tx_hash_hex, anchored=True, reason=None)
    
    except Exception as e:
        logger.error(f"❌ Erro: {e}")
        logger.info("=" * 80)
        return AnchorResult(tx_hash=None, anchored=False, reason=str(e))


def create_record(
    record_id: str,
    manifest_id: str,
    payload_hash: str,
    record_type: str,
    quantity: int,
    unit: str,
    timestamp: int,
) -> AnchorResult:
    """
    Criar registo na blockchain com validação de manifesto.
    
    IMPORTANTE: manifestId DEVE existir na blockchain antes de criar registo.
    A validação acontece automaticamente no smart contract.
    """
    w3 = get_web3()
    if w3 is None:
        return AnchorResult(tx_hash=None, anchored=False, reason="RPC URL not configured.")
    if not settings.contract_address or settings.contract_address == "0x0000000000000000000000000000000000000000":
        return AnchorResult(tx_hash=None, anchored=False, reason="Contract address not configured.")
    if not settings.private_key_for_deploy:
        return AnchorResult(tx_hash=None, anchored=False, reason="Private key not configured.")

    account = w3.eth.account.from_key(settings.private_key_for_deploy)
    contract = w3.eth.contract(address=Web3.to_checksum_address(settings.contract_address), abi=ANCHOR_ABI)
    nonce = w3.eth.get_transaction_count(account.address)
    
    logger.info("=" * 80)
    logger.info("📝 CRIAR REGISTO NA BLOCKCHAIN SEPOLIA")
    logger.info("=" * 80)
    logger.info(f"[CONTRATO] {settings.contract_address}")
    logger.info(f"[CONTA] {account.address}")
    logger.info("")
    logger.info("📋 DADOS DO REGISTO:")
    logger.info(f"  • Record ID: {record_id}")
    logger.info(f"  • Manifesto ID: {manifest_id}")
    logger.info(f"  • Hash: {payload_hash}")
    logger.info(f"  • Tipo: {record_type}")
    logger.info(f"  • Quantidade: {quantity} {unit}")
    logger.info(f"  • Timestamp: {timestamp}")
    logger.info("")
    
    try:
        txn = contract.functions.createRecord(
            record_id,
            manifest_id,
            bytes.fromhex(payload_hash),
            record_type,
            quantity,
            unit,
            timestamp,
        ).build_transaction(
            {
                "from": account.address,
                "nonce": nonce,
                "gas": 200000,
                "gasPrice": w3.eth.gas_price,
            }
        )
        
        gas_price_gwei = w3.from_wei(txn["gasPrice"], "gwei")
        logger.info(f"⛽ Gas: {txn['gas']} | Preço: {gas_price_gwei} Gwei")
        logger.info("")
        
        signed = w3.eth.account.sign_transaction(txn, private_key=settings.private_key_for_deploy)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        
        tx_hash_hex = tx_hash.hex()
        logger.info(f"🚀 TX: {tx_hash_hex}")
        logger.info(f"   https://sepolia.etherscan.io/tx/{tx_hash_hex}")
        logger.info("⏳ Aguardando confirmação...")
        
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        if receipt["status"] != 1:
            logger.error(f"❌ Transação falhou: status={receipt['status']}")
            logger.info("=" * 80)
            return AnchorResult(tx_hash=tx_hash_hex, anchored=False, reason="Transaction failed on chain")
        
        logger.info(f"✅ Registo criado com sucesso!")
        logger.info(f"   Bloco: {receipt['blockNumber']}")
        logger.info("=" * 80)
        return AnchorResult(tx_hash=tx_hash_hex, anchored=True, reason=None)
    
    except Exception as e:
        logger.error(f"❌ Erro: {e}")
        logger.info("=" * 80)
        return AnchorResult(tx_hash=None, anchored=False, reason=str(e))


def verify_tx_exists(tx_hash: str | None) -> bool:
    """Verificar se hash tx existe em Sepolia."""
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


def manifest_exists(manifest_id: str) -> bool:
    """
    Verificar se um manifesto existe na blockchain pelo ID.
    
    Consulta o smart contract - sem dependência em cache local.
    """
    w3 = get_web3()
    if w3 is None:
        logger.warning("RPC URL not configured")
        return False
    
    if not settings.contract_address or settings.contract_address == "0x0000000000000000000000000000000000000000":
        logger.warning("Contract address not configured")
        return False
    
    try:
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(settings.contract_address),
            abi=ANCHOR_ABI
        )
        
        exists = contract.functions.manifestExists(manifest_id).call()
        logger.info(f"Manifesto '{manifest_id}' exists: {exists}")
        return exists
    except Exception as e:
        logger.error(f"Erro ao verificar manifesto: {e}")
        return False


def get_manifest(manifest_id: str) -> dict | None:
    """
    Recuperar manifesto da blockchain pelo ID.
    
    Retorna dict com dados completos ou None se não encontrado.
    """
    w3 = get_web3()
    if w3 is None:
        return None
    
    if not settings.contract_address or settings.contract_address == "0x0000000000000000000000000000000000000000":
        return None
    
    try:
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(settings.contract_address),
            abi=ANCHOR_ABI
        )
        
        manifest_data = contract.functions.getManifestById(manifest_id).call()
        
        if manifest_data[0]:  # exists
            return {
                "manifestId": manifest_data[2],
                "hash": manifest_data[1].hex(),
                "good_type": manifest_data[3],
                "quantity": manifest_data[4],
                "unit": manifest_data[5],
                "ingredients": list(manifest_data[6]),
                "origin": manifest_data[7],
                "sustainability": manifest_data[8],
                "creator": manifest_data[9],
                "timestamp": manifest_data[10],
            }
        return None
    except Exception as e:
        logger.error(f"Erro ao recuperar manifesto: {e}")
        return None


def get_record(record_id: str) -> dict | None:
    """
    Recuperar registo da blockchain pelo ID.
    
    Retorna dict com dados completos ou None se não encontrado.
    """
    w3 = get_web3()
    if w3 is None:
        return None
    
    if not settings.contract_address or settings.contract_address == "0x0000000000000000000000000000000000000000":
        return None
    
    try:
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(settings.contract_address),
            abi=ANCHOR_ABI
        )
        
        record_data = contract.functions.getRecordById(record_id).call()
        
        if record_data[0]:  # exists
            return {
                "recordId": record_data[2],
                "hash": record_data[1].hex(),
                "manifestId": record_data[3],
                "recordType": record_data[4],
                "quantity": record_data[5],
                "unit": record_data[6],
                "user": record_data[7],
                "timestamp": record_data[8],
            }
        return None
    except Exception as e:
        logger.error(f"Erro ao recuperar registo: {e}")
        return None

