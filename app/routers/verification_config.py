"""Endpoints para verificação de contratos na blockchain Sepolia via Etherscan."""
import json
from urllib import request as urlrequest
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.settings import settings

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
        
        if data.get("result"):
            return {
                "exists": True,
                "transaction": data.get("result"),
            }
        
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
    
    # Obter status da transação (se possível)
    status = None
    receipt_params = f"module=proxy&action=eth_getTransactionReceipt&txhash={tx_hash}&apikey=YourApiKeyToken"
    try:
        receipt_data = query_etherscan_api(receipt_params)
        if receipt_data.get("result"):
            receipt = receipt_data.get("result", {})
            status = int(receipt.get("status", "0x0"), 16)  # Converter hex para int
    except Exception:
        pass  # Se não conseguir, deixa como None
    
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
        "explorer_url": f"{ETHERSCAN_EXPLORER_URL}/tx/{tx_hash}",
        "data": {},  # Placeholder para dados decodificados (se necessário)
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
    contract_address = settings.contract_address
    is_zero_address = contract_address == "0x0000000000000000000000000000000000000000"
    
    # Se não configurado
    if is_zero_address:
        return {
            "is_configured": False,
            "is_valid": False,
            "contract_address": None,
            "message": "Contrato não foi configurado",
        }
    
    # Verificar se existe na blockchain
    contract_info = get_contract_bytecode(contract_address)
    is_valid = contract_info.get("exists", False)
    
    return {
        "is_configured": True,
        "is_valid": is_valid,
        "contract_address": contract_address,
        "has_bytecode": is_valid,
        "explorer_url": f"{ETHERSCAN_EXPLORER_URL}/address/{contract_address}",
        "message": "Contrato validado com sucesso" if is_valid else "Contrato não encontrado na blockchain",
    }
