"""Endpoints de registro."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.record import RecordCreateRequest, RecordResponse
from app.services.record_service import create_record

router = APIRouter(prefix="/records", tags=["Records"])


@router.post(
    "",
    response_model=RecordResponse,
    summary="Criar registro de operação",
    description=(
        "Cria registro assinado (PRODUCED/TRANSFER/RECEIVED/DELIVERY). "
        "O backend verifica a assinatura, impõe consistência de estoque, armazena fora da cadeia, "
        "e ancora o hash do registro em Sepolia."
    ),
)
async def create_record_endpoint(request: RecordCreateRequest, db: Session = Depends(get_db)) -> RecordResponse:
    """Criar registro de operação assinado."""
    return create_record(db, request)
