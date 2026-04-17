"""Endpoints de saúde e status operacional."""

from fastapi import APIRouter

from app.schemas.common import MessageResponse

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=MessageResponse, summary="Verificação de saúde", description="Endpoint de disponibilidade simples da API.")
async def health_check() -> MessageResponse:
    """Verificar se o processo da API está vivo."""
    return MessageResponse(message="API está saudável.")
