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
    contract_address: str = Field(..., alias="CONTRACT_ADDRESS")
    private_key_for_deploy: str = Field(..., alias="PRIVATE_KEY_FOR_DEPLOY")

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
