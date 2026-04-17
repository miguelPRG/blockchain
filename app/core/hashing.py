"""Utilitários de hash SHA-256 determinístico para manifestos e registros."""

import hashlib
import json
from typing import Any


def canonical_json(data: dict[str, Any]) -> str:
    """Serializar dados em forma JSON canônica para geração de hash estável."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_hex(data: dict[str, Any]) -> str:
    """Calcular digest SHA-256 da carga JSON canônica."""
    encoded = canonical_json(data).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
