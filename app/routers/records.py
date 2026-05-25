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
    payload = {
        "record_id": record.record_id,
        "record_type": record.record_type,
        "manifest_id": record.manifest_id,
        "quantity": record.quantity,
        "timestamp": record.timestamp,
        "notes": record.notes,
    }
    if record.sender_user_id is not None:
        payload["sender_user_id"] = record.sender_user_id
    if record.receiver_user_id is not None:
        payload["receiver_user_id"] = record.receiver_user_id
    if record.related_record_id is not None:
        payload["related_record_id"] = record.related_record_id
    return payload


def _record_response(record: RecordModel) -> dict:
    payload = _record_payload(record)
    payload_hash_current = sha256_hex(payload)

    verification = verify_payload(
        VerificationRequest(
            payload=payload,
            tx_hash=record.tx_hash,
            contract_address=record.contract_address,
            item_id=record.record_id,
            public_key=record.public_key,
            signature=record.signature,
            manager_public_key=record.manager_public_key,
            manager_signature=record.manager_signature,
            expected_hash=record.payload_hash,
        )
    )

    return {
        "payload": payload,
        "payload_hash": record.payload_hash,
        "payload_hash_current": payload_hash_current,
        "signature": record.signature,
        "public_key": record.public_key,
        "manager_signature": record.manager_signature,
        "manager_public_key": record.manager_public_key,
        "contract_address": record.contract_address,
        "tx_hash": record.tx_hash,
        "verification": verification.model_dump(),
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
    "",
    summary="Obter último registo com verificação criptográfica",
    description="Recupera o registo mais recente quando nenhum ID é fornecido.",
    response_model=dict,
)
async def get_latest_record(db: Session = Depends(get_db)):
    record = db.query(RecordModel).order_by(RecordModel.created_at.desc()).first()
    if not record:
        raise HTTPException(status_code=404, detail="Nenhum registro encontrado")

    return _record_response(record)


@router.get(
    "/pending-transfers",
    summary="Listar TRANSFERs ainda sem RECEIVED associado",
    description="Devolve transferências Bob -> Charlie que ainda não foram confirmadas por um registo RECEIVED.",
    response_model=dict,
)
async def get_pending_transfers(db: Session = Depends(get_db)):
    received_transfer_ids = (
        db.query(RecordModel.related_record_id)
        .filter(
            RecordModel.record_type == "RECEIVED",
            RecordModel.related_record_id.isnot(None),
        )
        .subquery()
    )

    transfers = (
        db.query(RecordModel)
        .filter(
            RecordModel.record_type == "TRANSFER",
            RecordModel.sender_user_id == "bob",
            RecordModel.receiver_user_id == "charlie",
            ~RecordModel.record_id.in_(received_transfer_ids),
        )
        .order_by(RecordModel.created_at.asc())
        .all()
    )

    return {
        "count": len(transfers),
        "transfers": [_record_response(record) for record in transfers],
    }


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

    return _record_response(record)


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
