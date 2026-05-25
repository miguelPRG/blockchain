"""Integração Web3 para armazenamento de hashes na blockchain Sepolia."""
import logging
from dataclasses import dataclass

from web3 import Web3
from web3.exceptions import TimeExhausted, TransactionNotFound

from app.core.settings import settings

logger = logging.getLogger(__name__)

_GWEI = 10**9

# ABI do contrato Solidity: contracts/Anchor.sol
ANCHOR_ABI = [
    {
        "inputs": [
            {"internalType": "bytes32", "name": "_payloadHash", "type": "bytes32"},
            {"internalType": "uint256", "name": "_timestamp", "type": "uint256"},
            {"internalType": "string", "name": "_itemId", "type": "string"}
        ],
        "name": "anchorHash",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "bytes32", "name": "_payloadHash", "type": "bytes32"}],
        "name": "isAnchored",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "bytes32", "name": "_payloadHash", "type": "bytes32"}],
        "name": "getAnchorDetails",
        "outputs": [
            {"internalType": "bool", "name": "exists", "type": "bool"},
            {"internalType": "uint256", "name": "timestamp", "type": "uint256"},
            {"internalType": "address", "name": "creator", "type": "address"},
            {"internalType": "string", "name": "itemId", "type": "string"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]


@dataclass(slots=True)
class AnchorResult:
    """Resultado de uma tentativa de criar um hash na blockchain."""
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
    except Exception as exc:
        return f"Sepolia connection error: {exc}"


def anchor_hash(
    payload_hash: str,
    timestamp: int,
    item_id: str,
    contract_address: str,
    signer_private_key: str | None = None,
    manager_key: str | None = None,
) -> AnchorResult:
    """Ancorar apenas o hash na blockchain.
    
    Args:
        payload_hash: Hash SHA-256 da carga
        timestamp: Unix timestamp
        item_id: Identificador do item
        contract_address: Endereço do contrato (obrigatório)
        signer_private_key: Chave privada do utilizador (opcional)
        manager_key: Chave privada do gestor (fallback)
    """
    w3 = get_web3()
    if w3 is None:
        return AnchorResult(tx_hash=None, anchored=False, reason="RPC URL not configured.")
    if not contract_address or contract_address == "0x0000000000000000000000000000000000000000":
        return AnchorResult(tx_hash=None, anchored=False, reason="Contract address not provided.")
    # Se não houver signer_private_key, use manager_key
    if not signer_private_key and not manager_key:
        return AnchorResult(tx_hash=None, anchored=False, reason="Private key not provided.")
    if not item_id or not item_id.strip():
        return AnchorResult(tx_hash=None, anchored=False, reason="Item ID not provided.")

    deploy_key_to_use = signer_private_key if signer_private_key else manager_key
    
    # Log which key is being used
    key_source = "USER" if signer_private_key else "DEPLOY"
    logger.info(f"[anchor_hash] Using {key_source} key for signing")
    
    account = w3.eth.account.from_key(deploy_key_to_use)
    contract = w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=ANCHOR_ABI)
    nonce = w3.eth.get_transaction_count(account.address, "pending")
    
    logger.info("=" * 80)
    logger.info("📦 ANCORAR HASH NA BLOCKCHAIN")
    logger.info("=" * 80)
    logger.info(f"[CONTRATO] {contract_address}")
    logger.info(f"[CONTA] {account.address}")
    logger.info(f"[NONCE] {nonce}")
    logger.info(f"  • Hash: {payload_hash}")
    logger.info(f"  • Timestamp: {timestamp}")
    logger.info(f"  • Item ID: {item_id}")
    logger.info("")
    
    try:
        latest_block = w3.eth.get_block("latest")
        base_fee = latest_block.get("baseFeePerGas") or w3.eth.gas_price
        priority_fee = w3.eth.max_priority_fee if hasattr(w3.eth, "max_priority_fee") else 2 * _GWEI

        gas_limit = 200000
        tx_hash_hex: str | None = None
        payload_hash_bytes = bytes.fromhex(payload_hash)

        max_priority_fee_per_gas = int(priority_fee)
        max_fee_per_gas = int(base_fee * 2 + priority_fee)

        txn = contract.functions.anchorHash(
            payload_hash_bytes,
            timestamp,
            item_id,
        ).build_transaction(
            {
                "from": account.address,
                "nonce": nonce,
                "gas": gas_limit,
                "chainId": w3.eth.chain_id,
                "maxPriorityFeePerGas": max_priority_fee_per_gas,
                "maxFeePerGas": max_fee_per_gas,
                "type": 2,
            }
        )

        logger.info("⛽ GAS:")
        logger.info(f"  • Limite: {txn['gas']}")
        logger.info(f"  • Max Priority: {w3.from_wei(max_priority_fee_per_gas, 'gwei')} Gwei")
        logger.info(f"  • Max Fee: {w3.from_wei(max_fee_per_gas, 'gwei')} Gwei")
        logger.info("")

        signed = w3.eth.account.sign_transaction(txn, private_key=deploy_key_to_use)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        tx_hash_hex = tx_hash.hex()

        logger.info(f"🚀 TX: {tx_hash_hex}")
        logger.info("⏳ Aguardando confirmação...")

        try:
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            if receipt["status"] != 1:
                logger.error(f"❌ Transação falhou: status={receipt['status']}")
                return AnchorResult(tx_hash=tx_hash_hex, anchored=False, reason="Transaction failed on chain")

            logger.info("✅ Hash ancorado com sucesso!")
            return AnchorResult(tx_hash=tx_hash_hex, anchored=True, reason=None)
        except TimeExhausted:
            logger.warning("Timeout aguardando receipt da TX %s", tx_hash_hex)

        # Fallback: alguns RPCs falham para receipt, mas o estado pode ter sido atualizado.
        anchored_on_chain = contract.functions.isAnchored(payload_hash_bytes).call()
        if anchored_on_chain:
            logger.info("✅ Hash encontrado no contrato após timeout de receipt")
            return AnchorResult(
                tx_hash=tx_hash_hex,
                anchored=True,
                reason="Receipt timeout, but hash is anchored on-chain",
            )

        return AnchorResult(
            tx_hash=tx_hash_hex,
            anchored=False,
            reason="Transaction not confirmed within retry window",
        )

    except Exception as e:
        logger.error(f"❌ Erro: {e}")
        return AnchorResult(tx_hash=None, anchored=False, reason=str(e))


def sign_anchor_transaction(
    *,
    payload_hash: str,
    timestamp: int,
    item_id: str,
    contract_address: str,
    signer_private_key: str,
) -> str:
    """Construir e assinar localmente uma transação anchorHash sem a publicar."""
    w3 = get_web3()
    if w3 is None:
        raise RuntimeError("RPC URL not configured.")
    if not contract_address or contract_address == "0x0000000000000000000000000000000000000000":
        raise RuntimeError("Contract address not provided.")
    if not item_id or not item_id.strip():
        raise RuntimeError("Item ID not provided.")

    account = w3.eth.account.from_key(signer_private_key)
    contract = w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=ANCHOR_ABI)
    latest_block = w3.eth.get_block("latest")
    base_fee = latest_block.get("baseFeePerGas") or w3.eth.gas_price
    priority_fee = w3.eth.max_priority_fee if hasattr(w3.eth, "max_priority_fee") else 2 * _GWEI

    txn = contract.functions.anchorHash(
        bytes.fromhex(payload_hash),
        timestamp,
        item_id,
    ).build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address, "pending"),
            "gas": 200000,
            "chainId": w3.eth.chain_id,
            "maxPriorityFeePerGas": int(priority_fee),
            "maxFeePerGas": int(base_fee * 2 + priority_fee),
            "type": 2,
        }
    )
    signed = w3.eth.account.sign_transaction(txn, private_key=signer_private_key)
    return signed.raw_transaction.hex()


def build_anchor_transaction(
    *,
    payload_hash: str,
    timestamp: int,
    item_id: str,
    contract_address: str,
    from_address: str,
) -> dict:
    """Construir transação anchorHash sem assinar.

    O backend usa o RPC para nonce/gas/chainId, mas não recebe chave privada.
    """
    w3 = get_web3()
    if w3 is None:
        raise RuntimeError("RPC URL not configured.")
    if not contract_address or contract_address == "0x0000000000000000000000000000000000000000":
        raise RuntimeError("Contract address not provided.")
    if not item_id or not item_id.strip():
        raise RuntimeError("Item ID not provided.")
    if not from_address or not from_address.startswith("0x"):
        raise RuntimeError("Signer address not provided.")

    contract = w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=ANCHOR_ABI)
    latest_block = w3.eth.get_block("latest")
    base_fee = latest_block.get("baseFeePerGas") or w3.eth.gas_price
    priority_fee = w3.eth.max_priority_fee if hasattr(w3.eth, "max_priority_fee") else 2 * _GWEI

    return contract.functions.anchorHash(
        bytes.fromhex(payload_hash),
        timestamp,
        item_id,
    ).build_transaction(
        {
            "from": Web3.to_checksum_address(from_address),
            "nonce": w3.eth.get_transaction_count(from_address, "pending"),
            "gas": 200000,
            "chainId": w3.eth.chain_id,
            "maxPriorityFeePerGas": int(priority_fee),
            "maxFeePerGas": int(base_fee * 2 + priority_fee),
            "type": 2,
        }
    )


def broadcast_signed_anchor_transaction(signed_anchor_tx: str) -> AnchorResult:
    """Publicar uma transação já assinada pelo user e devolver o TXID."""
    w3 = get_web3()
    if w3 is None:
        return AnchorResult(tx_hash=None, anchored=False, reason="RPC URL not configured.")

    try:
        raw_tx = signed_anchor_tx[2:] if signed_anchor_tx.startswith("0x") else signed_anchor_tx
        tx_hash = w3.eth.send_raw_transaction(bytes.fromhex(raw_tx))
        tx_hash_hex = tx_hash.hex()

        try:
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            if receipt["status"] != 1:
                return AnchorResult(tx_hash=tx_hash_hex, anchored=False, reason="Transaction failed on chain")
            return AnchorResult(tx_hash=tx_hash_hex, anchored=True, reason=None)
        except TimeExhausted:
            return AnchorResult(
                tx_hash=tx_hash_hex,
                anchored=True,
                reason="Receipt timeout after broadcasting signed transaction",
            )
    except Exception as e:
        logger.error(f"❌ Erro ao publicar raw transaction: {e}")
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


def decode_anchor_tx(tx_hash: str, contract_address: str) -> dict | None:
    """Decodificar uma transação anchorHash e extrair a hash ancorada.
    
    Args:
        tx_hash: Hash da transação
        contract_address: Endereço do contrato (obrigatório)
    """
    w3 = get_web3()
    if w3 is None:
        return None
    if not contract_address or contract_address == "0x0000000000000000000000000000000000000000":
        return None

    try:
        normalized_tx_hash = tx_hash if tx_hash.startswith("0x") else f"0x{tx_hash}"
        tx = w3.eth.get_transaction(normalized_tx_hash)
        receipt = w3.eth.get_transaction_receipt(normalized_tx_hash)

        if not tx or not receipt:
            return None

        tx_to = tx.get("to")
        if not tx_to or tx_to.lower() != contract_address.lower():
            return None

        input_data = tx.get("input")
        if input_data in (None, "0x"):
            return None
        if hasattr(input_data, "hex"):
            input_data = input_data.hex()

        contract = w3.eth.contract(abi=ANCHOR_ABI)
        func_obj, func_params = contract.decode_function_input(input_data)

        payload_hash = func_params.get("_payloadHash")
        if isinstance(payload_hash, bytes):
            payload_hash = payload_hash.hex()

        return {
            "tx_hash": normalized_tx_hash,
            "from_address": tx.get("from"),
            "status": receipt.get("status"),
            "block": receipt.get("blockNumber"),
            "gas_used": receipt.get("gasUsed"),
            "function": func_obj.fn_name,
            "payload_hash": payload_hash,
            "timestamp": func_params.get("_timestamp"),
            "item_id": func_params.get("_itemId"),
        }
    except (TransactionNotFound, ValueError) as e:
        logger.error(f"Erro ao recuperar transação: {e}")
        return None
    except Exception as e:
        logger.error(f"Erro ao decodificar transação anchorHash: {e}")
        return None


def is_anchored(payload_hash: str, contract_address: str) -> bool:
    """Verificar se um hash foi ancorado no smart contract."""
    w3 = get_web3()
    if w3 is None:
        return False
    if not contract_address or contract_address == "0x0000000000000000000000000000000000000000":
        return False
    try:
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=ANCHOR_ABI
        )
        return contract.functions.isAnchored(bytes.fromhex(payload_hash)).call()
    except Exception as e:
        logger.error(f"Erro ao verificar se o hash está ancorado: {e}")
        return False

def get_anchor_details(payload_hash: str, contract_address: str) -> dict | None:
    """Verificar detalhes do hash no smart contract."""
    w3 = get_web3()
    if w3 is None:
        return None
    if not contract_address or contract_address == "0x0000000000000000000000000000000000000000":
        return None
    try:
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=ANCHOR_ABI
        )
        exists, timestamp, creator, item_id = contract.functions.getAnchorDetails(bytes.fromhex(payload_hash)).call()
        if exists:
            return {"exists": exists, "timestamp": timestamp, "creator": creator, "item_id": item_id}
        return None
    except Exception as e:
        logger.error(f"Erro ao recuperar detalhes do hash: {e}")
        return None
