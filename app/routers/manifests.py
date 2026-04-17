"""Endpoints de manifesto."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.manifest import ManifestCreateRequest, ManifestResponse
from app.services.manifest_service import create_manifest

router = APIRouter(prefix="/manifests", tags=["Manifests"])


@router.post(
    "",
    response_model=ManifestResponse,
    summary="Criar manifesto de bens",
    description=(
        "Cria um Manifesto de Bens assinado para um lote de cerveja artesanal. "
        "O servidor verifica a assinatura ECDSA, calcula o hash SHA-256, armazena fora da cadeia em SQLite, "
        "e tenta ancorar o hash em Sepolia."
    ),
)
async def create_manifest_endpoint(request: ManifestCreateRequest, db: Session = Depends(get_db)) -> ManifestResponse:
    """Criar manifesto com cadeia de prova criptográfica."""
    return create_manifest(db, request)
