"""Endpoints de manifesto."""

import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.hashing import sha256_hex
from app.models.manifest import Manifest as ManifestModel
from app.schemas.manifest import ManifestCreateRequest, ManifestResponse
from app.schemas.verification import VerificationRequest, VerificationResponse
from app.services.manifest_service import create_manifest
from app.services.verification_service import verify_payload

router = APIRouter(prefix="/manifests", tags=["Manifests"])


def _manifest_payload(manifest: ManifestModel) -> dict:
    return {
        "manifest_id": manifest.manifest_id,
        "good_type": manifest.good_type,
        "quantity": manifest.quantity,
        "unit": manifest.unit,
        "ingredients": json.loads(manifest.ingredients_json),
        "origin": manifest.origin,
        "sustainability": manifest.sustainability,
        "creator": manifest.creator,
        "timestamp": manifest.timestamp,
    }

@router.get(
    "/{manifest_id}/verify",
    summary="Verificar manifesto contra blockchain",
    description="Recalcula a hash do payload off-chain e compara com a hash ancorada na transação blockchain.",
    response_model=VerificationResponse,
)
async def verify_manifest_endpoint(
    manifest_id: str,
    db: Session = Depends(get_db),
) -> VerificationResponse:
    manifest = db.query(ManifestModel).filter(ManifestModel.manifest_id == manifest_id).first()
    if not manifest:
        raise HTTPException(status_code=404, detail=f"Manifesto '{manifest_id}' não encontrado")

    payload = _manifest_payload(manifest)
    return verify_payload(
        VerificationRequest(
            payload=payload,
            tx_hash=manifest.tx_hash,
            item_id=manifest_id,
            public_key=manifest.public_key,
            signature=manifest.signature,
            expected_hash=manifest.payload_hash,
        )
    )


@router.get(
    "/{manifest_id}",
    summary="Obter manifesto por ID",
    description="Recupera um manifesto específico com metadados e prova de ancoragem blockchain.",
    response_model=dict,
)
async def get_manifest_by_id(manifest_id: str, db: Session = Depends(get_db)):
    manifest = db.query(ManifestModel).filter(ManifestModel.manifest_id == manifest_id).first()
    if not manifest:
        raise HTTPException(status_code=404, detail=f"Manifesto '{manifest_id}' não encontrado")

    payload = _manifest_payload(manifest)

    return {
        "payload": payload,
        "payload_hash": sha256_hex(payload),
        "signature": manifest.signature,
        "public_key": manifest.public_key,
        "tx_hash": manifest.tx_hash,
    }

@router.post(
    "",
    response_model=ManifestResponse,
    summary="Criar manifesto",
    description="Cria manifesto assinado, armazena off-chain e ancora hash na blockchain.",
)
async def create_manifest_endpoint(request: ManifestCreateRequest, db: Session = Depends(get_db)) -> ManifestResponse:
    """Criar manifesto assinado."""
    return create_manifest(db, request)

from pydantic import BaseModel

class TamperRequest(BaseModel):
    new_quantity: float

@router.put(
    "/{manifest_id}/tamper",
    summary="Simular ataque: Alterar quantidade",
    description="Altera a quantidade do manifesto diretamente no banco de dados para testar a verificação de integridade.",
)
async def tamper_manifest_endpoint(manifest_id: str, request: TamperRequest, db: Session = Depends(get_db)):
    """Alterar dados do manifesto maliciosamente."""
    manifest = db.query(ManifestModel).filter(ManifestModel.manifest_id == manifest_id).first()
    if not manifest:
        raise HTTPException(status_code=404, detail=f"Manifesto '{manifest_id}' não encontrado")
    
    manifest.quantity = request.new_quantity
    db.commit()
    return {"message": f"Manifesto {manifest_id} alterado maliciosamente para {request.new_quantity} na base de dados."}
