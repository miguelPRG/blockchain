"""Endpoints para configuração dinâmica da aplicação."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.settings import settings

router = APIRouter(prefix="/config", tags=["config"])


class ContractAddressUpdate(BaseModel):
    """Modelo para atualizar endereço do contrato."""
    contract_address: str


@router.get("/contract-address")
def get_contract_address() -> dict:
    """Retornar endereço do contrato atual."""
    return {
        "contract_address": settings.contract_address,
        "is_configured": settings.contract_address != "0x0000000000000000000000000000000000000000"
    }


@router.post("/contract-address")
def update_contract_address(data: ContractAddressUpdate) -> dict:
    """
    Atualizar endereço do contrato em tempo de execução.
    
    Útil quando um novo contrato foi publicado e precisa ser ativado sem reiniciar o servidor.
    """
    from pathlib import Path
    
    # Validação básica
    if not data.contract_address.startswith("0x") or len(data.contract_address) != 42:
        raise HTTPException(
            status_code=400,
            detail="Endereço inválido. Deve ser um endereço Ethereum válido (0x...)"
        )
    
    # Atualizar .env
    env_file = Path(__file__).parent.parent.parent / ".env"
    if env_file.exists():
        content = env_file.read_text()
        lines = content.split("\n")
        
        found = False
        for i, line in enumerate(lines):
            if line.startswith("CONTRACT_ADDRESS="):
                lines[i] = f"CONTRACT_ADDRESS={data.contract_address}"
                found = True
                break
        
        if not found:
            lines.append(f"CONTRACT_ADDRESS={data.contract_address}")
        
        env_file.write_text("\n".join(lines))
    
    # Atualizar settings em memória
    settings.contract_address = data.contract_address
    
    return {
        "message": "Contrato atualizado com sucesso",
        "contract_address": settings.contract_address,
        "is_configured": True
    }
