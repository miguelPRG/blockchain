"""Endpoints de registo (blockchain-only)."""

from fastapi import APIRouter

from app.schemas.record import RecordCreateRequest, RecordResponse
from app.services.record_service import create_record
from app.services.blockchain_service import get_record

router = APIRouter(prefix="/records", tags=["Records"])


@router.get(
    "/{record_id}",
    summary="Recuperar registo",
    description="Recupera registo da blockchain pelo ID.",
)
async def get_record_endpoint(record_id: str) -> dict | None:
    """Recuperar registo da blockchain."""
    record = get_record(record_id)
    if not record:
        return {"error": f"Registo '{record_id}' não encontrado na blockchain"}
    return record


@router.post(
    "",
    response_model=RecordResponse,
    summary="Criar registo",
    description="Cria registo assinado e o armazena direto na blockchain.",
)
async def create_record_endpoint(request: RecordCreateRequest) -> RecordResponse:
    """Criar registo assinado na blockchain."""
    return create_record(request)
