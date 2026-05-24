"""Ponto de entrada FastAPI para rastreabilidade blockchain-only."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

# Carregar .env no início da aplicação
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent / ".env"
    load_dotenv(env_file)
except ImportError:
    pass

from fastapi import FastAPI
from rich import print as rprint

from app.core.database import init_db
from app.core.settings import settings
from app.routers.health import router as health_router
from app.routers.manifests import router as manifests_router
from app.routers.records import router as records_router
from app.routers.verification import router as verification_router
from app.routers.verification_config import router as verification_config_router
from app.routers.config import router as config_router
from app.services.blockchain_service import check_connection_status



@asynccontextmanager
async def lifespan(_: FastAPI):
    """Inicializar aplicação e recursos."""
    rprint(f"[bold cyan]Iniciando:[/bold cyan] {settings.app_name} v{settings.app_version}")
    
    # Verificar SEPOLIA_RPC_URL
    if not os.getenv("SEPOLIA_RPC_URL"):
        rprint("[bold red]✗ SEPOLIA_RPC_URL não configurada[/bold red]")
        raise RuntimeError("SEPOLIA_RPC_URL environment variable is required")
    
    rprint(f"[bold yellow]Blockchain Status:[/bold yellow] {check_connection_status()}")
    
    # Inicializar DB
    init_db()
    rprint(f"[bold green]✓ Banco de Dados:[/bold green] Inicializado SQLite (Repositório Off-chain)")
    
    rprint(f"[bold green]⚡ Modo:[/bold green] Híbrido (SQLite + Blockchain)")
    
    # Yield para permitir que a aplicação execute
    yield
    
    # Cleanup (opcional)
    rprint(f"[bold yellow]Encerrando aplicação[/bold yellow]")

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "API de cadeia de suprimentos para Cerveja Artesanal. "
        "Manifestos e registos são armazenados no Repositório Off-chain, enquanto "
        "apenas os hashes criptográficos são ancorados na blockchain Sepolia para prova de integridade."
    ),
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(manifests_router)
app.include_router(records_router)
app.include_router(verification_router)
app.include_router(verification_config_router)
app.include_router(config_router)
