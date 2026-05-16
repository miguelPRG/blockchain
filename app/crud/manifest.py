"""Auxiliares CRUD para manifesto."""

import json
from sqlalchemy.orm import Session

from app.models.manifest import Manifest
from app.schemas.manifest import ManifestPayload


def get_manifest(db: Session, manifest_id: str) -> Manifest | None:
    """Buscar manifesto por id."""
    return db.get(Manifest, manifest_id)


def create_manifest(
    db: Session,
    payload: ManifestPayload,
) -> Manifest:
    """Persistir manifesto e retornar entidade ORM."""
    entity = Manifest(
        manifest_id=payload.manifest_id,
        good_type=payload.good_type,
        quantity=payload.quantity,
        unit=payload.unit,
        ingredients_json=json.dumps(payload.ingredients, ensure_ascii=True),
        origin=payload.origin,
        sustainability=payload.sustainability,
        timestamp=payload.timestamp,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity
