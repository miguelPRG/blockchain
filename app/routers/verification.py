"""Endpoints de verificação para partes independentes."""

from fastapi import APIRouter

from app.schemas.verification import VerificationRequest, VerificationResponse
from app.services.verification_service import verify_payload

router = APIRouter(prefix="/verify", tags=["Verification"])


@router.post(
    "",
    response_model=VerificationResponse,
    summary="Verificar integridade de carga e evidência de blockchain",
    description=(
        "Recalcula hash de carga, decodifica a transação anchorHash e compara a hash ancorada. "
        "Suporta validação independente sem confiar no gerenciador de cadeia de suprimentos."
    ),
)
async def verify_endpoint(request: VerificationRequest) -> VerificationResponse:
    """Executar pipeline de verificação completo para uma carga."""
    return verify_payload(request)
