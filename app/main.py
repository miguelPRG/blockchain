"""Ponto de entrada FastAPI para rastreabilidade de cerveja artesanal baseada em blockchain."""

from contextlib import asynccontextmanager
from eth_account import Account
from fastapi import FastAPI
from rich import print as rprint
from app.core.database import Base, engine
from app.core.settings import settings
from app.routers.health import router as health_router
from app.routers.manifests import router as manifests_router
from app.routers.records import router as records_router
from app.routers.verification import router as verification_router
from app.services.blockchain_service import check_connection_status

@asynccontextmanager
async def lifespan(_: FastAPI):
    """Inicializar esquema de DB, deployment automático, e imprimir status de conexão."""
    Base.metadata.create_all(bind=engine)
    rprint(f"[bold cyan]Iniciando:[/bold cyan] {settings.app_name} v{settings.app_version}")
    rprint(f"[bold yellow]Network Status:[/bold yellow] {check_connection_status()}")
    
    # Verificar chave privada
    private_key = settings.private_key_for_deploy
    if private_key:
        try:
            # Adicionar prefixo 0x se não tiver
            if not private_key.startswith("0x"):
                private_key = f"0x{private_key}"
            
            account = Account.from_key(private_key)
            rprint(f"[bold green]✓ Wallet conectada:[/bold green] {account.address}")
        except Exception as e:
            rprint(f"[bold red]✗ Erro na chave privada:[/bold red] {e}")
    else:
        rprint(f"[bold red]✗ PRIVATE_KEY_FOR_DEPLOY não configurada[/bold red]")

    yield

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "API de cadeia de suprimentos híbrida em blockchain para Cerveja Artesanal. "
        "Dados operacionais são armazenados fora da cadeia em SQLite; hashes SHA-256 são ancorados em Ethereum Mainnet."
    ),
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(manifests_router)
app.include_router(records_router)
app.include_router(verification_router)
