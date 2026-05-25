"""Tipos de esquema compartilhados."""

from datetime import datetime

from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    """Carga de mensagem API simples."""

    message: str = Field(..., description="Mensagem de resposta legível para humanos.")


class AnchorInfo(BaseModel):
    """Metadados de resultado de ancoragem em blockchain."""

    tx_hash: str | None = Field(default=None, description="Hash/ID da transação Sepolia se a ancoragem foi bem-sucedida.")
    anchored: bool = Field(..., description="Verdadeiro quando uma transação blockchain válida foi enviada.")
    reason: str | None = Field(default=None, description="Razão quando a ancoragem não é realizada.")


class TimestampedModel(BaseModel):
    """Modelo de resposta base que inclui metadados de timestamp."""

    timestamp: datetime
