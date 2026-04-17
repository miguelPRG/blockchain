"""Script de verificador independente para registros/manifestos."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.hashing import sha256_hex
from app.core.security import verify_signature
from app.services.blockchain_service import verify_tx_exists


def main() -> None:
    """Carregar carga e metadados criptográficos e imprimir resultados de verificação."""
    parser = argparse.ArgumentParser(description="Script de verificação de registro independente")
    parser.add_argument("--payload-file", required=True, help="Caminho para o arquivo JSON de carga")
    parser.add_argument("--signature", required=True, help="Assinatura ECDSA em hex")
    parser.add_argument("--public-key", required=True, help="Chave pública ECDSA em hex")
    parser.add_argument("--expected-hash", required=True, help="Hash SHA-256 esperado da API/banco de dados")
    parser.add_argument("--tx-hash", default=None, help="Hash de transação Sepolia opcional")
    args = parser.parse_args()

    payload = json.loads(Path(args.payload_file).read_text(encoding="utf-8"))
    recomputed_hash = sha256_hex(payload)
    hash_matches = recomputed_hash == args.expected_hash
    signature_valid = verify_signature(args.public_key, recomputed_hash, args.signature)
    blockchain_valid = verify_tx_exists(args.tx_hash) if args.tx_hash else False
    overall = hash_matches and signature_valid and (blockchain_valid or args.tx_hash is None)

    print(
        json.dumps(
            {
                "recomputed_hash": recomputed_hash,
                "hash_matches": hash_matches,
                "signature_valid": signature_valid,
                "blockchain_proof_valid": blockchain_valid,
                "overall_valid": overall,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
