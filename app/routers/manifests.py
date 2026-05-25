"""Endpoints de manifesto."""

import json
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.core.database import get_db
from shared.hashing import sha256_hex
from app.models.manifest import Manifest as ManifestModel
from app.models.record import Record as RecordModel
from app.schemas.manifest import ManifestCreateRequest, ManifestResponse
from app.schemas.verification import VerificationRequest
from app.services.manifest_service import create_manifest
from app.services.verification_service import verify_payload

router = APIRouter(prefix="/manifests", tags=["Manifests"])


def _manifest_payload(manifest: ManifestModel) -> dict:
    payload = {
        "manifest_id": manifest.manifest_id,
        "good_type": manifest.good_type,
        "quantity": manifest.quantity,
        "unit": manifest.unit,
        "ingredients": json.loads(manifest.ingredients_json),
        "origin": manifest.origin,
        "sustainability": manifest.sustainability,
        "timestamp": manifest.timestamp,
    }
    if manifest.owner_user_id is not None:
        payload["owner_user_id"] = manifest.owner_user_id
    if manifest.root_manifest_id is not None:
        payload["root_manifest_id"] = manifest.root_manifest_id
    if manifest.parent_manifest_id is not None:
        payload["parent_manifest_id"] = manifest.parent_manifest_id
    if manifest.source_record_id is not None:
        payload["source_record_id"] = manifest.source_record_id
    return payload


def _manifest_response(manifest: ManifestModel) -> dict:
    payload = _manifest_payload(manifest)
    payload_hash_current = sha256_hex(payload)

    verification = verify_payload(
        VerificationRequest(
            payload=payload,
            tx_hash=manifest.tx_hash,
            contract_address=manifest.contract_address,
            item_id=manifest.manifest_id,
            public_key=manifest.public_key,
            signature=manifest.signature,
            manager_public_key=manifest.manager_public_key,
            manager_signature=manifest.manager_signature,
            expected_hash=manifest.payload_hash,
        )
    )

    return {
        "payload": payload,
        "payload_hash": manifest.payload_hash,
        "payload_hash_current": payload_hash_current,
        "signature": manifest.signature,
        "public_key": manifest.public_key,
        "manager_signature": manifest.manager_signature,
        "manager_public_key": manifest.manager_public_key,
        "contract_address": manifest.contract_address,
        "tx_hash": manifest.tx_hash,
        "verification": verification.model_dump(),
    }


@router.get(
    "",
    summary="Obter último manifesto com verificação criptográfica",
    description="Recupera o manifesto mais recente quando nenhum ID é fornecido.",
    response_model=dict,
)
async def get_latest_manifest(db: Session = Depends(get_db)):
    manifest = db.query(ManifestModel).order_by(ManifestModel.created_at.desc()).first()
    if not manifest:
        raise HTTPException(status_code=404, detail="Nenhum manifesto encontrado")

    return _manifest_response(manifest)


@router.get(
    "/{manifest_id}/chain",
    summary="Obter cadeia de manifestos e quantidade disponível",
    description="Mostra o root, os manifestos derivados e a quantidade ainda transferível do manifesto indicado.",
    response_model=dict,
)
async def get_manifest_chain(manifest_id: str, db: Session = Depends(get_db)):
    manifest = db.query(ManifestModel).filter(ManifestModel.manifest_id == manifest_id).first()
    if not manifest:
        raise HTTPException(status_code=404, detail=f"Manifesto '{manifest_id}' não encontrado")

    root_manifest_id = manifest.root_manifest_id or manifest.manifest_id
    chain_manifests = (
        db.query(ManifestModel)
        .filter(or_(ManifestModel.manifest_id == root_manifest_id, ManifestModel.root_manifest_id == root_manifest_id))
        .order_by(ManifestModel.created_at.asc())
        .all()
    )

    chain = []
    selected_available_quantity = 0.0
    for chain_manifest in chain_manifests:
        transfers = (
            db.query(RecordModel)
            .filter(
                RecordModel.manifest_id == chain_manifest.manifest_id,
                RecordModel.record_type == "TRANSFER",
            )
            .order_by(RecordModel.created_at.asc())
            .all()
        )
        transferred_quantity = sum(record.quantity for record in transfers)
        available_quantity = chain_manifest.quantity - transferred_quantity
        if chain_manifest.manifest_id == manifest_id:
            selected_available_quantity = available_quantity

        chain.append(
            {
                "manifest_id": chain_manifest.manifest_id,
                "root_manifest_id": chain_manifest.root_manifest_id or chain_manifest.manifest_id,
                "parent_manifest_id": chain_manifest.parent_manifest_id,
                "source_record_id": chain_manifest.source_record_id,
                "quantity": chain_manifest.quantity,
                "unit": chain_manifest.unit,
                "transferred_quantity": transferred_quantity,
                "available_quantity": available_quantity,
                "transfers": [
                    {
                        "record_id": record.record_id,
                        "quantity": record.quantity,
                    }
                    for record in transfers
                ],
            }
        )

    return {
        "root_manifest_id": root_manifest_id,
        "selected_manifest_id": manifest_id,
        "max_transfer_quantity": selected_available_quantity,
        "unit": manifest.unit,
        "chain": chain,
    }


@router.get(
    "/{manifest_id}",
    summary="Obter manifesto por ID com verificação criptográfica",
    description="Recupera um manifesto específico com metadados, prova de ancoragem blockchain e verificação criptográfica integrada.",
    response_model=dict,
)
async def get_manifest_by_id(manifest_id: str, db: Session = Depends(get_db)):
    manifest = db.query(ManifestModel).filter(ManifestModel.manifest_id == manifest_id).first()
    if not manifest:
        raise HTTPException(status_code=404, detail=f"Manifesto '{manifest_id}' não encontrado")

    return _manifest_response(manifest)

@router.post(
    "",
    response_model=ManifestResponse,
    summary="Criar manifesto",
    description="Cria manifesto assinado, armazena off-chain e ancora hash na blockchain.",
)
async def create_manifest_endpoint(request: ManifestCreateRequest, db: Session = Depends(get_db)) -> ManifestResponse:
    """Criar manifesto assinado."""
    return create_manifest(db, request)


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
