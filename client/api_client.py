"""Chamadas HTTP e gestão do contrato usadas pelo CLI."""

from __future__ import annotations

import json
from urllib import request as urlrequest

from rich.console import Console

from client.config import BASE_URL, CLIENT_ENV_FILE

console = Console()


def post_json(url: str, payload: dict) -> dict:
    """Envia uma carga JSON para a API e devolve a resposta JSON."""
    try:
        if url.endswith(("/manifests", "/records")):
            _validate_mutation_payload(payload)

        req = urlrequest.Request(
            url=url,
            method="POST",
            data=json.dumps(payload).encode("utf-8"),
        )
        req.add_header("Content-Type", "application/json")

        with urlrequest.urlopen(req) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))

    except urlrequest.HTTPError as e:
        try:
            error_detail = json.loads(e.read().decode("utf-8"))
            console.print(
                f"[red]✗ Erro HTTP {e.code}:[/red] "
                f"{error_detail.get('detail', str(error_detail))}"
            )
        except Exception:
            console.print(f"[red]✗ Erro HTTP {e.code}:[/red] {e.reason}")
        return {}

    except Exception as e:
        console.print(f"[red]✗ Erro na requisição:[/red] {e}")
        return {}


def _validate_mutation_payload(payload: dict) -> None:
    """Evita enviar à API um body antigo/incompleto para manifestos ou registos."""
    required_fields = ["payload", "auth", "role", "contract_address"]

    missing = [
        field
        for field in required_fields
        if field not in payload
    ]
    if missing:
        raise ValueError(f"Payload mutável incompleto. Campos em falta: {', '.join(missing)}")

    if "signer_id" in payload:
        raise ValueError("Payload mutável antigo: signer_id já não deve ser enviado.")

    if "tx_hash" not in payload and "signed_anchor_tx" not in payload:
        raise ValueError("Payload mutável incompleto. Envie tx_hash ou signed_anchor_tx.")

    auth = payload.get("auth") or {}
    missing_auth = [
        field
        for field in ("public_key", "signature", "manager_public_key", "manager_signature")
        if field not in auth
    ]
    if missing_auth:
        raise ValueError(f"Envelope auth incompleto. Campos em falta: {', '.join(missing_auth)}")


def get_json(url: str) -> dict:
    """Faz um pedido GET e devolve a resposta JSON."""
    try:
        req = urlrequest.Request(url=url, method="GET")

        with urlrequest.urlopen(req) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))

    except urlrequest.HTTPError as e:
        try:
            error_detail = json.loads(e.read().decode("utf-8"))
            console.print(
                f"[red]✗ Erro HTTP {e.code}:[/red] "
                f"{error_detail.get('detail', str(error_detail))}"
            )
        except Exception:
            console.print(f"[red]✗ Erro HTTP {e.code}:[/red] {e.reason}")
        return {}

    except Exception as e:
        console.print(f"[red]✗ Erro no pedido GET:[/red] {e}")
        return {}


def put_json(url: str, payload: dict) -> dict:
    """Envia uma carga JSON por PUT e devolve a resposta JSON."""
    try:
        req = urlrequest.Request(
            url=url,
            method="PUT",
            data=json.dumps(payload).encode("utf-8"),
        )
        req.add_header("Content-Type", "application/json")

        with urlrequest.urlopen(req) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))

    except Exception as e:
        console.print(f"[red]✗ Erro na requisição PUT:[/red] {e}")
        return {}


def validate_contract_via_api(contract_address: str) -> bool:
    """Validar se um contrato existe e está deployado na blockchain."""
    result = post_json(
        f"{BASE_URL}/config/validate-contract",
        {"contract_address": contract_address},
    )
    if result.get("success"):
        console.print(f"[bold green]✓ Contrato Validado:[/bold green] {contract_address}")
        console.print(f"[dim]Explorer: {result.get('explorer_url')}[/dim]")
        return True

    console.print("[red]✗ Falha na validação[/red]")
    return False

def read_contract_address_from_env() -> str | None:
    """Ler CONTRACT_ADDRESS do ficheiro .env local."""
    if CLIENT_ENV_FILE.exists():
        content = CLIENT_ENV_FILE.read_text()
        for line in content.split("\n"):
            if line.startswith("CONTRACT_ADDRESS="):
                addr = line.split("=", 1)[1].strip()
                if addr and addr != "0x0000000000000000000000000000000000000000":
                    return addr
    return None


def save_contract_address_to_env(address: str) -> None:
    """Guardar CONTRACT_ADDRESS no ficheiro .env local."""
    if CLIENT_ENV_FILE.exists():
        content = CLIENT_ENV_FILE.read_text()
        lines = content.split("\n")

        found = False
        for i, line in enumerate(lines):
            if line.startswith("CONTRACT_ADDRESS="):
                lines[i] = f"CONTRACT_ADDRESS={address}"
                found = True
                break

        if not found:
            lines.append(f"CONTRACT_ADDRESS={address}")

        CLIENT_ENV_FILE.write_text("\n".join(lines))
    else:
        CLIENT_ENV_FILE.write_text(f"CONTRACT_ADDRESS={address}\n")
