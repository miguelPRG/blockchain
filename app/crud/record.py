"""Auxiliares CRUD para registro incluindo cálculo de estoque."""

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.record import Record
from app.schemas.record import RecordPayload, RecordType


def create_record(
    db: Session,
    payload: RecordPayload,
) -> Record:
    """Persistir registro assinado no banco de dados."""
    entity = Record(
        record_id=payload.record_id,
        record_type=payload.record_type.value,
        manifest_id=payload.manifest_id,
        quantity=payload.quantity,
        unit=payload.unit,
        timestamp=payload.timestamp,
        notes=payload.notes,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


def get_available_stock(db: Session, manifest_id: str) -> float:
    """Calcular estoque líquido a partir de registros de operação para um manifesto específico."""
    incoming = case(
        (Record.record_type.in_([RecordType.PRODUCED.value, RecordType.RECEIVED.value]), Record.quantity),
        else_=0.0,
    )
    outgoing = case(
        (Record.record_type.in_([RecordType.TRANSFER.value, RecordType.DELIVERY.value]), Record.quantity),
        else_=0.0,
    )
    stmt = select(func.coalesce(func.sum(incoming - outgoing), 0.0)).where(Record.manifest_id == manifest_id)
    result = db.execute(stmt).scalar_one()
    return float(result)
