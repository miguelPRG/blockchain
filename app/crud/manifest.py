"""Auxiliares CRUD para manifesto."""

import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.manifest import Manifest
from app.schemas.manifest import ManifestPayload


def get_manifest(db: Session, manifest_id: str) -> Manifest | None:
    """Buscar manifesto por id."""
    return db.get(Manifest, manifest_id)


def create_manifest(
    db: Session,
    payload: ManifestPayload,
    payload_hash: str,
    signature: str,
    public_key: str,
    tx_hash: str | None,
) -> Manifest:
    """Persistir manifesto e retornar entidade ORM."""
    # Converter timestamp ISO string de volta para datetime
    timestamp_dt = datetime.fromisoformat(payload.timestamp)
    
    entity = Manifest(
        manifest_id=payload.manifest_id,
        good_type=payload.good_type,
        quantity=payload.quantity,
        unit=payload.unit,
        ingredients_json=json.dumps(payload.ingredients, ensure_ascii=True),
        origin=payload.origin,
        sustainability=payload.sustainability,
        creator=payload.creator,
        timestamp=timestamp_dt,
        payload_hash=payload_hash,
        signature=signature,
        public_key=public_key,
        tx_hash=tx_hash,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity
