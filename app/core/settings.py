"""Configuração de aplicação carregada de variáveis de ambiente."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    """Configuração em tempo de execução para FastAPI e integração de blockchain."""

    app_name: str = "Blockchain Supply Chain Tracking - Cerveja Artesanal"
    app_version: str = "0.1.0"
    database_url: str = "sqlite:///./supply_chain.db"
    sepolia_rpc_url: str = Field(..., alias="SEPOLIA_RPC_URL") 
    contract_address: str = Field(default="0x0000000000000000000000000000000000000000", alias="CONTRACT_ADDRESS")
    manager_key: str = Field(..., alias="MANAGER_KEY") # Chave privada para deploy e operações administrativas

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def reload_contract_address(self) -> None:
        """Recarregar contract_address do arquivo .env em tempo de execução."""
        env_file = Path(__file__).parent.parent.parent / ".env"
        if env_file.exists():
            content = env_file.read_text()
            for line in content.split("\n"):
                if line.startswith("CONTRACT_ADDRESS="):
                    self.contract_address = line.split("=", 1)[1].strip()
                    break


settings = Settings()
