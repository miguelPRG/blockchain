"""Ponto de entrada FastAPI para rastreabilidade de cerveja artesanal baseada em blockchain."""

from contextlib import asynccontextmanager

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
    """Inicializar esquema de DB e imprimir status de conexão Sepolia na inicialização."""
    Base.metadata.create_all(bind=engine)
    rprint(f"[bold cyan]Iniciando:[/bold cyan] {settings.app_name} v{settings.app_version}")
    rprint(f"[bold yellow]Status Sepolia:[/bold yellow] {check_connection_status()}")
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "API de cadeia de suprimentos híbrida em blockchain para Cerveja Artesanal. "
        "Dados operacionais são armazenados fora da cadeia em SQLite; hashes SHA-256 são ancorados em Ethereum Sepolia."
    ),
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(manifests_router)
app.include_router(records_router)
app.include_router(verification_router)
