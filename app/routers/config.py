"""Endpoints para configuração dinâmica da aplicação."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.settings import settings

router = APIRouter(prefix="/config", tags=["config"])

# ============================================================
# Constantes
# ============================================================
SUPPLY_MANAGER_ADDRESS = "0x9D77a7336C19eE8975Eb6267c2aF384B90C73455"


# ============================================================
# Modelos Pydantic
# ============================================================

class ContractValidationRequest(BaseModel):
    """Modelo para validar contrato existente."""
    contract_address: str


class AnchorTransactionPrepareRequest(BaseModel):
    """Pedido para preparar uma transação anchorHash sem assinatura."""

    payload_hash: str
    timestamp: int
    item_id: str
    contract_address: str
    from_address: str


@router.post("/authenticate-manager")
def authenticate_manager() -> dict:
    """Endpoint desativado: chaves privadas nunca devem ser enviadas à API."""
    raise HTTPException(
        status_code=410,
        detail="Private keys must stay in the CLI. The backend only validates public keys, signatures and tx_hash.",
    )


@router.post("/validate-contract")
def validate_contract(req: ContractValidationRequest) -> dict:
    """
    Validar se um contrato existe e está deployado na blockchain.
    
    Args:
        req: Contém o contract_address a validar
    
    Returns:
        Status de validação
    
    Raises:
        HTTPException: Se endereço é inválido ou contrato não existe
    """
    contract_address = req.contract_address
    
    if not contract_address.startswith("0x") or len(contract_address) != 42:
        raise HTTPException(
            status_code=400,
            detail="Endereço inválido. Deve ser um endereço Ethereum válido (0x...)"
        )
    
    from app.services.deploy_service import is_contract_deployed
    
    try:
        # Verificar se está deployado
        is_deployed = is_contract_deployed(contract_address)
        
        if not is_deployed:
            raise HTTPException(
                status_code=404,
                detail=f"Contrato não encontrado no endereço: {contract_address}"
            )
        
        return {
            "success": True,
            "message": "Contrato validado com sucesso",
            "contract_address": contract_address,
            "is_deployed": True,
            "explorer_url": f"https://sepolia.etherscan.io/address/{contract_address}"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao validar contrato: {str(e)}"
        )


# ============================================================
# Endpoints de Deployment
# ============================================================

@router.post("/deploy-contract")
def deploy_contract() -> dict:
    """Fazer deploy do contrato usando a chave do manager configurada no backend."""
    if not settings.manager_key:
        raise HTTPException(
            status_code=500,
            detail="MANAGER_KEY não configurada no backend.",
        )

    from app.services.deploy_service import auto_deploy_if_needed

    contract_address = auto_deploy_if_needed(verbose=False, manager_key=settings.manager_key)
    if not contract_address:
        raise HTTPException(status_code=500, detail="Falha ao fazer deploy do contrato.")

    return {
        "success": True,
        "contract_address": contract_address,
        "explorer_url": f"https://sepolia.etherscan.io/address/{contract_address}",
    }


@router.post("/prepare-anchor-transaction")
def prepare_anchor_transaction(req: AnchorTransactionPrepareRequest) -> dict:
    """Preparar transação anchorHash para o cliente assinar localmente."""
    from app.services.blockchain_service import build_anchor_transaction

    try:
        transaction = build_anchor_transaction(
            payload_hash=req.payload_hash,
            timestamp=req.timestamp,
            item_id=req.item_id,
            contract_address=req.contract_address,
            from_address=req.from_address,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"transaction": _json_safe_transaction(transaction)}


def _json_safe_transaction(transaction: dict) -> dict:
    """Converter tipos Web3 para JSON sem perder dados necessários à assinatura."""
    safe = {}
    for key, value in transaction.items():
        if hasattr(value, "hex"):
            safe[key] = value.hex()
        else:
            safe[key] = value
    return safe


@router.get("/contract-status")
def get_contract_status() -> dict:
    """
    Obter status actual do contrato.
    
    Returns:
        Mensagem informando que nenhum contrato é configurado globalmente
    """
    try:
        return {
            "success": True,
            "contract_address": None,
            "is_deployed": False,
            "explorer_url": None,
            "note": "Nenhum contrato configurado globalmente. Forneça o contract_address nas suas requisições."
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter status do contrato: {str(e)}"
        )


@router.get("/diagnose-account")
def diagnose_account() -> dict:
    """
    Diagnosticar estado da conta Supply Manager.
    
    Útil para debug de problemas com gas/saldo.
    
    Returns:
        Estado da conexão, saldo, gas price, etc.
    """
    raise HTTPException(status_code=410, detail="Private-key account diagnosis is disabled on the API.")
    


@router.post("/diagnose-account")
def diagnose_account_post() -> dict:
    """Endpoint desativado: chaves privadas nunca devem ser enviadas à API."""
    raise HTTPException(status_code=410, detail="Private keys are not accepted by the API.")
