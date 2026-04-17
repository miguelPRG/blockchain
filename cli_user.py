"""CLI básica para geração de chaves, assinatura e chamadas de API."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from urllib import request as urlrequest

from app.core.hashing import sha256_hex
from app.core.security import address_from_public_key, generate_key_pair_hex, sign_hash


def post_json(url: str, payload: dict) -> dict:
    """Enviar carga JSON para API e analisar resposta JSON."""
    req = urlrequest.Request(url=url, method="POST", data=json.dumps(payload).encode("utf-8"))
    req.add_header("Content-Type", "application/json")
    with urlrequest.urlopen(req) as resp:  # noqa: S310 - local educational setup
        return json.loads(resp.read().decode("utf-8"))


def cmd_gen_keys() -> None:
    """Gerar par de chaves ECDSA e imprimir como JSON."""
    private_key, public_key = generate_key_pair_hex()
    address = address_from_public_key(public_key)
    print(json.dumps({"private_key": private_key, "public_key": public_key, "address": address}, indent=2))


def cmd_create_manifest(args: argparse.Namespace) -> None:
    """Construir, assinar e enviar solicitação de manifesto."""
    payload = {
        "manifest_id": args.manifest_id,
        "good_type": args.good_type,
        "quantity": args.quantity,
        "unit": args.unit,
        "ingredients": args.ingredients,
        "origin": args.origin,
        "sustainability": args.sustainability,
        "creator": args.creator,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    payload_hash = sha256_hex(payload)
    signature = sign_hash(args.private_key, payload_hash)
    body = {"payload": payload, "auth": {"public_key": args.public_key, "signature": signature}}
    result = post_json(f"{args.base_url}/manifests", body)
    print(json.dumps(result, indent=2))


def cmd_create_record(args: argparse.Namespace) -> None:
    """Construir, assinar e enviar solicitação de registro de operação."""
    payload = {
        "record_id": args.record_id,
        "record_type": args.record_type,
        "manifest_id": args.manifest_id,
        "quantity": args.quantity,
        "unit": args.unit,
        "user": args.user,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "notes": args.notes,
    }
    payload_hash = sha256_hex(payload)
    signature = sign_hash(args.private_key, payload_hash)
    body = {"payload": payload, "auth": {"public_key": args.public_key, "signature": signature}}
    result = post_json(f"{args.base_url}/records", body)
    print(json.dumps(result, indent=2))


def build_parser() -> argparse.ArgumentParser:
    """Configurar argumentos da CLI e subcomandos."""
    parser = argparse.ArgumentParser(description="CLI client for blockchain craft beer traceability API")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("gen-keys", help="Gerar par de chaves ECDSA.")
    gen.set_defaults(func=lambda _: cmd_gen_keys())

    manifest = sub.add_parser("create-manifest", help="Criar e assinar um manifesto.")
    manifest.add_argument("--base-url", default="http://127.0.0.1:8000")
    manifest.add_argument("--manifest-id", required=True)
    manifest.add_argument("--good-type", default="IPA Artesanal")
    manifest.add_argument("--quantity", type=float, required=True)
    manifest.add_argument("--unit", default="litros")
    manifest.add_argument("--ingredients", nargs="+", required=True)
    manifest.add_argument("--origin", required=True)
    manifest.add_argument("--sustainability", default="Responsible Barley")
    manifest.add_argument("--creator", required=True)
    manifest.add_argument("--public-key", required=True)
    manifest.add_argument("--private-key", required=True)
    manifest.set_defaults(func=cmd_create_manifest)

    record = sub.add_parser("create-record", help="Criar e assinar um registro de operação.")
    record.add_argument("--base-url", default="http://127.0.0.1:8000")
    record.add_argument("--record-id", required=True)
    record.add_argument("--record-type", choices=["PRODUCED", "TRANSFER", "RECEIVED", "DELIVERY"], required=True)
    record.add_argument("--manifest-id", required=True)
    record.add_argument("--quantity", type=float, required=True)
    record.add_argument("--unit", default="litros")
    record.add_argument("--user", required=True)
    record.add_argument("--notes", default=None)
    record.add_argument("--public-key", required=True)
    record.add_argument("--private-key", required=True)
    record.set_defaults(func=cmd_create_record)
    return parser


if __name__ == "__main__":
    parser = build_parser()
    arguments = parser.parse_args()
    arguments.func(arguments)
