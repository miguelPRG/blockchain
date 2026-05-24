"""Endpoints para configuração dinâmica da aplicação."""
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.settings import settings
from shared.security import address_from_private_key

router = APIRouter(prefix="/config", tags=["config"])

# ============================================================
# Constantes
# ============================================================
SUPPLY_MANAGER_ADDRESS = "0x9D77a7336C19eE8975Eb6267c2aF384B90C73455"


# ============================================================
# Modelos Pydantic
# ============================================================

class SupplyManagerAuth(BaseModel):
    """Modelo para autenticar o Supply Manager."""
    private_key: str


class ContractValidationRequest(BaseModel):
    """Modelo para validar contrato existente."""
    contract_address: str


@router.post("/authenticate-manager")
def authenticate_manager(auth: SupplyManagerAuth) -> dict:
    """
    Autenticar o Supply Manager com a chave privada.
    
    Valida se a chave privada corresponde ao endereço esperado
    e a armazena em settings para uso posterior.
    
    Args:
        auth: Contém a chave privada do Supply Manager
    
    Returns:
        Status da autenticação
    
    Raises:
        HTTPException: Se a chave privada é inválida
    """
    private_key = auth.private_key
    
    if not private_key:
        raise HTTPException(
            status_code=400,
            detail="Chave privada não pode estar vazia"
        )
    
    # Garantir prefixo 0x
    if not private_key.startswith("0x"):
        private_key = f"0x{private_key}"
    
    try:
        # Validar se a chave corresponde ao endereço esperado
        derived_address = address_from_private_key(private_key)
        
        if derived_address.lower() != SUPPLY_MANAGER_ADDRESS.lower():
            raise HTTPException(
                status_code=401,
                detail=f"Endereço inválido. Esperado: {SUPPLY_MANAGER_ADDRESS}, Obtido: {derived_address}"
            )
        
        # Guardar a chave privada em memória e variável de ambiente
        settings.manager_key = private_key
        os.environ["MANAGER_KEY"] = private_key
        
        return {
            "success": True,
            "message": "Autenticação do Supply Manager bem-sucedida",
            "manager_address": derived_address,
            "manager_authenticated": True
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Erro ao validar chave privada: {str(e)}"
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
        # Atualizar settings em memória com o endereço a validar
        settings.contract_address = contract_address
        
        # Verificar se está deployado
        is_deployed = is_contract_deployed()
        
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
    """
    Fazer deployment de um novo contrato Anchor.
    
    Requer que o Supply Manager tenha sido autenticado previamente.
    
    Returns:
        Informações do contrato deployado
    
    Raises:
        HTTPException: Se não autenticado ou falha no deployment
    """
    if not settings.manager_key:
        raise HTTPException(
            status_code=401,
            detail="Supply Manager não autenticado. Faça autenticação primeiro."
        )
    
    from app.services.deploy_service import auto_deploy_if_needed
    
    try:
        contract_address = auto_deploy_if_needed(verbose=False)
        
        if not contract_address:
            raise HTTPException(
                status_code=500,
                detail="Falha ao fazer deployment do contrato"
            )
        
        # Garantir que settings está atualizado
        settings.contract_address = contract_address
        
        return {
            "success": True,
            "message": "Contrato deployado com sucesso",
            "contract_address": contract_address,
            "explorer_url": f"https://sepolia.etherscan.io/address/{contract_address}"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao fazer deployment: {str(e)}"
        )


@router.get("/contract-status")
def get_contract_status() -> dict:
    """
    Obter status actual do contrato.
    
    Returns:
        Endereço do contrato e se está deployado
    """
    from app.services.deploy_service import is_contract_deployed
    
    try:
        contract_addr = settings.contract_address
        
        # Se não tem endereço, não está deployado
        if not contract_addr or contract_addr == "0x0000000000000000000000000000000000000000":
            return {
                "success": True,
                "contract_address": None,
                "is_deployed": False,
                "explorer_url": None
            }
        
        # Verificar se realmente está na blockchain
        is_deployed = is_contract_deployed()
        
        return {
            "success": True,
            "contract_address": contract_addr,
            "is_deployed": is_deployed,
            "explorer_url": f"https://sepolia.etherscan.io/address/{contract_addr}" if is_deployed else None
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
    from app.services.deploy_service import diagnose_account as diagnose
    
    try:
        result = diagnose()
        
        if result.get("error"):
            raise HTTPException(
                status_code=500,
                detail=f"Erro no diagnóstico: {result['error']}"
            )
        
        return {
            "success": True,
            "message": "Diagnóstico da conta",
            "data": {
                "connected": result["connected"],
                "account": result["account"],
                "balance_eth": result["balance_eth"],
                "balance_wei": result["balance_wei"],
                "gas_price_gwei": result["gas_price_gwei"],
                "nonce": result["nonce"],
                "sufficient_balance": result["balance_eth"] >= 0.01
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao diagnosticar conta: {str(e)}"
        )
