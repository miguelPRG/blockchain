"""Endpoints de registo."""

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from shared.hashing import sha256_hex
from app.models.record import Record as RecordModel
from app.schemas.record import RecordCreateRequest, RecordResponse
from app.schemas.verification import VerificationRequest
from app.services.record_service import create_record
from app.services.verification_service import verify_payload

router = APIRouter(prefix="/records", tags=["Records"])


def _record_payload(record: RecordModel) -> dict:
    return {
        "record_id": record.record_id,
        "record_type": record.record_type,
        "manifest_id": record.manifest_id,
        "quantity": record.quantity,
        "unit": record.unit,
        "user": record.user,
        "timestamp": record.timestamp,
        "notes": record.notes,
    }


@router.post(
    "",
    response_model=RecordResponse,
    summary="Criar registo",
    description="Cria registo assinado, armazena off-chain e ancora hash na blockchain.",
)
async def create_record_endpoint(request: RecordCreateRequest, db: Session = Depends(get_db)) -> RecordResponse:
    """Criar registo assinado."""
    return create_record(db, request)


@router.get(
    "/{record_id}",
    summary="Obter registro por ID com verificação criptográfica",
    description="Recupera um registo específico com metadados, prova de ancoragem blockchain e verificação criptográfica integrada.",
    response_model=dict,
)
async def get_record_by_id(record_id: str, db: Session = Depends(get_db)):
    record = db.query(RecordModel).filter(RecordModel.record_id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail=f"Registro '{record_id}' não encontrado")

    payload = _record_payload(record)
    payload_hash_current = sha256_hex(payload)

    # Realizar verificação criptográfica integrada
    verification = verify_payload(
        VerificationRequest(
            payload=payload,
            tx_hash=record.tx_hash,
            item_id=record_id,
            public_key=record.public_key,
            signature=record.signature,
            expected_hash=record.payload_hash,
        )
    )

    return {
        "payload": payload,
        "payload_hash": record.payload_hash,  # O que foi realmente ancorado na blockchain
        "payload_hash_current": payload_hash_current,  # O calculado agora para comparação
        "signature": record.signature,
        "public_key": record.public_key,
        "tx_hash": record.tx_hash,
        "verification": verification.model_dump(),
    }


class TamperRequest(BaseModel):
    new_quantity: float

@router.put(
    "/{record_id}/tamper",
    summary="Simular ataque: Alterar quantidade",
    description="Altera a quantidade do registro diretamente no banco de dados para testar a verificação de integridade.",
)
async def tamper_record_endpoint(record_id: str, request: TamperRequest, db: Session = Depends(get_db)):
    """Alterar dados do registro maliciosamente."""
    record = db.query(RecordModel).filter(RecordModel.record_id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail=f"Registro '{record_id}' não encontrado")
    
    record.quantity = request.new_quantity
    db.commit()
    return {"message": f"Registro {record_id} alterado maliciosamente para {request.new_quantity} na base de dados."}
