"""Endpoints de manifesto (blockchain-only)."""

from fastapi import APIRouter
from app.schemas.manifest import ManifestCreateRequest, ManifestResponse
from app.services.manifest_service import create_manifest
from app.services.blockchain_service import get_manifest

router = APIRouter(prefix="/manifests", tags=["Manifests"])


@router.get(
    "/{manifest_id}",
    summary="Recuperar manifesto",
    description="Recupera manifesto da blockchain pelo ID.",
)
async def get_manifest_endpoint(manifest_id: str) -> dict | None:
    """Recuperar manifesto da blockchain."""
    manifest = get_manifest(manifest_id)
    if not manifest:
        return {"error": f"Manifesto '{manifest_id}' não encontrado na blockchain"}
    return manifest


@router.post(
    "",
    response_model=ManifestResponse,
    summary="Criar manifesto",
    description="Cria manifesto assinado e o armazena direto na blockchain.",
)
async def create_manifest_endpoint(request: ManifestCreateRequest) -> ManifestResponse:
    """Criar manifesto assinado na blockchain."""
    return create_manifest(request)
