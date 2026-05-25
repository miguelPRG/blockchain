"""Endpoints para verificação de contratos na blockchain Sepolia via Etherscan."""
import json
from urllib import request as urlrequest
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from web3.exceptions import TransactionNotFound

from app.services.blockchain_service import ANCHOR_ABI, get_web3

router = APIRouter(prefix="/verification", tags=["verification"])

# ============================================================
# Constantes
# ============================================================
ETHERSCAN_API_URL = "https://api-sepolia.etherscan.io/api"
ETHERSCAN_EXPLORER_URL = "https://sepolia.etherscan.io"


# ============================================================
# Modelos
# ============================================================

class ContractVerificationResponse(BaseModel):
    """Resposta da verificação de contrato."""
    exists: bool
    address: str
    has_bytecode: bool
    explorer_url: str
    message: str


# ============================================================
# Funções Auxiliares
# ============================================================

def query_etherscan_api(params: str) -> dict:
    """
    Fazer query à API do Etherscan.
    
    Args:
        params: Parâmetros da query (sem '?')
    
    Returns:
        Resposta JSON da API
    """
    try:
        url = f"{ETHERSCAN_API_URL}?{params}"
        req = urlrequest.Request(url, method="GET")
        with urlrequest.urlopen(req) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Erro ao consultar Etherscan API: {str(e)}"
        )


def serialize_web3_value(value):
    """Converter tipos Web3/HexBytes para valores JSON-friendly."""
    if isinstance(value, (bytes, bytearray)):
        return f"0x{value.hex()}"
    if hasattr(value, "hex"):
        return value.hex()
    if isinstance(value, dict):
        return {key: serialize_web3_value(val) for key, val in value.items()}
    if isinstance(value, list):
        return [serialize_web3_value(item) for item in value]
    return value


def get_transaction_data_from_rpc(tx_hash: str) -> dict:
    """Obter dados da transação usando o RPC Sepolia configurado."""
    w3 = get_web3()
    if w3 is None:
        return {"exists": False, "transaction": None, "source": "rpc"}

    try:
        tx = w3.eth.get_transaction(tx_hash)
        return {
            "exists": True,
            "transaction": serialize_web3_value(dict(tx)),
            "source": "rpc",
        }
    except TransactionNotFound:
        return {"exists": False, "transaction": None, "source": "rpc"}
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Erro ao consultar RPC Sepolia: {str(e)}"
        )


def get_transaction_receipt_status(tx_hash: str) -> int | None:
    """Obter status de receipt via RPC, com fallback para Etherscan."""
    w3 = get_web3()
    if w3 is not None:
        try:
            receipt = w3.eth.get_transaction_receipt(tx_hash)
            status = receipt.get("status")
            return int(status) if status is not None else None
        except TransactionNotFound:
            return None
        except Exception:
            pass

    receipt_params = f"module=proxy&action=eth_getTransactionReceipt&txhash={tx_hash}&apikey=YourApiKeyToken"
    try:
        receipt_data = query_etherscan_api(receipt_params)
        receipt = receipt_data.get("result")
        if isinstance(receipt, dict) and receipt.get("status"):
            return int(receipt.get("status"), 16)
    except Exception:
        pass

    return None


def decode_anchor_input(input_data: str | None) -> dict:
    """Decodificar input data de chamadas ao contrato Anchor."""
    if not input_data or input_data == "0x":
        return {}

    try:
        w3 = get_web3()
        if w3 is None:
            return {}

        contract = w3.eth.contract(abi=ANCHOR_ABI)
        func_obj, func_params = contract.decode_function_input(input_data)

        payload_hash = func_params.get("_payloadHash")
        if isinstance(payload_hash, (bytes, bytearray)):
            payload_hash = f"0x{payload_hash.hex()}"
        elif hasattr(payload_hash, "hex"):
            payload_hash = payload_hash.hex()

        return {
            "function": func_obj.fn_name,
            "data": {
                "payload_hash": payload_hash,
                "timestamp": func_params.get("_timestamp"),
                "item_id": func_params.get("_itemId"),
            },
        }
    except Exception:
        return {}


def get_contract_bytecode(contract_address: str) -> dict:
    """
    Obter bytecode de um contrato da Sepolia.
    
    Args:
        contract_address: Endereço do contrato
    
    Returns:
        Dicionário com informações do bytecode
    """
    if not contract_address or contract_address == "0x0000000000000000000000000000000000000000":
        return {"exists": False, "bytecode": None}
    
    # Garantir prefixo 0x
    addr = contract_address if contract_address.startswith("0x") else f"0x{contract_address}"
    
    try:
        # Query: module=account&action=getcode&address=...
        params = f"module=account&action=getcode&address={addr}&apikey=YourApiKeyToken"
        data = query_etherscan_api(params)
        
        if data.get("status") == "1":
            bytecode = data.get("result", "0x")
            exists = bytecode and bytecode != "0x"
            return {
                "exists": exists,
                "bytecode": bytecode if exists else None,
                "bytecode_length": len(bytecode) if exists else 0,
            }
        
        return {"exists": False, "bytecode": None}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Erro ao verificar contrato: {str(e)}"
        )


def get_transaction_data(tx_hash: str) -> dict:
    """
    Obter dados de uma transação.
    
    Args:
        tx_hash: Hash da transação
    
    Returns:
        Informações da transação
    """
    if not tx_hash.startswith("0x"):
        tx_hash = f"0x{tx_hash}"
    
    try:
        # Query: module=proxy&action=eth_getTransactionByHash&txhash=...
        params = f"module=proxy&action=eth_getTransactionByHash&txhash={tx_hash}&apikey=YourApiKeyToken"
        data = query_etherscan_api(params)
        result = data.get("result")
        
        if isinstance(result, dict):
            return {
                "exists": True,
                "transaction": result,
                "source": "etherscan",
            }

        rpc_data = get_transaction_data_from_rpc(tx_hash)
        if rpc_data.get("exists"):
            return rpc_data
        
        return {"exists": False, "transaction": None}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Erro ao obter transação: {str(e)}"
        )


# ============================================================
# Endpoints Públicos
# ============================================================

@router.get("/contract/{contract_address}")
def verify_contract(contract_address: str) -> dict:
    """
    Verificar se um contrato existe na blockchain Sepolia.
    
    Faz query à API do Etherscan para validar bytecode.
    
    Args:
        contract_address: Endereço do contrato (com ou sem 0x)
    
    Returns:
        Informações de verificação do contrato
    """
    contract_info = get_contract_bytecode(contract_address)
    
    addr = contract_address if contract_address.startswith("0x") else f"0x{contract_address}"
    
    return {
        "exists": contract_info.get("exists"),
        "address": addr,
        "has_bytecode": contract_info.get("exists"),
        "bytecode_length": contract_info.get("bytecode_length", 0),
        "explorer_url": f"{ETHERSCAN_EXPLORER_URL}/address/{addr}",
        "message": "Contrato encontrado na blockchain" if contract_info.get("exists") else "Contrato não encontrado",
    }


@router.get("/transaction/{tx_hash}")
def get_transaction(tx_hash: str) -> dict:
    """
    Obter dados completos de uma transação via Etherscan.
    
    Retorna informações básicas da transação, input data, e status.
    Nota: Decodificação completa do ABI não é implementada (cliente deve decodificar se necessário).
    
    Args:
        tx_hash: Hash da transação (com ou sem 0x)
    
    Returns:
        Informações da transação
    """
    if not tx_hash.startswith("0x"):
        tx_hash = f"0x{tx_hash}"
    
    tx_info = get_transaction_data(tx_hash)
    
    if not tx_info.get("exists"):
        raise HTTPException(
            status_code=404,
            detail=f"Transação não encontrada: {tx_hash}"
        )
    
    tx = tx_info.get("transaction", {})
    if not isinstance(tx, dict):
        raise HTTPException(
            status_code=502,
            detail="Resposta inválida ao obter transação: formato inesperado."
        )
    
    status = get_transaction_receipt_status(tx_hash)
    decoded = decode_anchor_input(tx.get("input"))
    
    return {
        "tx_hash": tx.get("hash"),
        "exists_on_chain": True,
        "from": tx.get("from"),
        "to": tx.get("to"),
        "value": tx.get("value"),
        "gas": tx.get("gas"),
        "gas_price": tx.get("gasPrice"),
        "input": tx.get("input"),
        "block_number": tx.get("blockNumber"),
        "transaction_index": tx.get("transactionIndex"),
        "status": status,  # None, 0 (failed), ou 1 (success)
        "source": tx_info.get("source"),
        "function": decoded.get("function"),
        "explorer_url": f"{ETHERSCAN_EXPLORER_URL}/tx/{tx_hash}",
        "data": decoded.get("data", {}),
    }


@router.get("/contract-status")
def get_contract_status_api() -> dict:
    """
    Verificar status do contrato configurado na aplicação.
    
    Retorna informações sobre o contrato desde as settings
    e valida se existe na blockchain.
    
    Returns:
        Status do contrato
    """
    # This application no longer stores a global contract address in settings.
    # Clients should provide `contract_address` in each request where needed.
    return {
        "is_configured": False,
        "is_valid": False,
        "contract_address": None,
        "message": "Nenhum contrato configurado globalmente. Forneça o contract_address nas suas requisições.",
    }
