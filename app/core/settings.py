"""Configuração de aplicação carregada de variáveis de ambiente."""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

BACKEND_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    """Configuração em tempo de execução para FastAPI e integração de blockchain."""

    app_name: str = "Blockchain Supply Chain Tracking - Cerveja Artesanal"
    app_version: str = "0.1.0"
    database_url: str = f"sqlite:///{BACKEND_DIR / 'supply_chain.db'}"
    sepolia_rpc_url: str = Field(..., alias="SEPOLIA_RPC_URL")
    manager_key: str | None = Field(default=None, alias="MANAGER_KEY")

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
