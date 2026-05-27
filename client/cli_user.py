"""CLI interativa para assinatura de manifestos/registos e testagem de blockchain com múltiplos utilizadores."""

from __future__ import annotations

import json
import sys
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except Exception:
    # dotenv is optional; if not installed, environment variables must be set externally
    pass

# Adicionar PYTHONPATH para importar da raiz
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from client.api_client import (
    get_json,
    post_json,
    put_json,
    read_contract_address_from_env,
    save_contract_address_to_env,
    validate_contract_via_api,
)
from client.blockchain_client import deploy_contract_locally
from client.config import ALICE_ADDRESS, BASE_URL, BOB_ADDRESS, CHARLIE_ADDRESS, SUPPLY_MANAGER_ADDRESS
from client.request_signing import create_signed_api_request
from client.verify_blockchain import get_verified_resource_status
from shared.security import address_from_private_key, public_key_from_private_key


# ============================================================
# Configuração
# ============================================================

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("/tmp/blockchain_cli_debug.log"),
        logging.StreamHandler(sys.stderr),
    ],
)

logger = logging.getLogger(__name__)
console = Console()

def request_and_validate_manager_private_key() -> str | None:
    """Pede e valida a chave privada do Supply Manager."""
    console.print("\n[bold cyan]🔐 Autenticação do Supply Manager[/bold cyan]")
    console.print(f"[dim]Endereço esperado: {SUPPLY_MANAGER_ADDRESS}[/dim]\n")

    max_attempts = 3

    for attempt in range(max_attempts):
        private_key = Prompt.ask(
            "[bold]Introduza a chave privada do Supply Manager[/bold]",
            password=True,
        )

        if not private_key:
            console.print("[red]✗ Chave privada não pode estar vazia[/red]")
            continue

        if not private_key.startswith("0x"):
            private_key = f"0x{private_key}"

        try:
            derived_address = address_from_private_key(private_key)
            if derived_address.lower() != SUPPLY_MANAGER_ADDRESS.lower():
                console.print("[red]✗ Endereço inválido[/red]")
                console.print(f"[dim]Esperado: {SUPPLY_MANAGER_ADDRESS}[/dim]")
                console.print(f"[dim]Obtido: {derived_address}[/dim]\n")
                remaining = max_attempts - attempt - 1
                if remaining > 0:
                    console.print(f"[yellow]Tentativas restantes: {remaining}[/yellow]\n")
                continue

            console.print("[bold green]✓ Chave do Supply Manager validada[/bold green]\n")
            return private_key

        except Exception as e:
            console.print(f"[red]✗ Erro ao validar chave:[/red] {e}\n")

    console.print("[red]✗ Falha na validação da chave privada[/red]")
    return None


def initialize_blockchain_setup() -> bool:
    """
    Fluxo completo de inicialização:
    1. Verificar se existe CONTRACT_ADDRESS no .env local
       - Se existe: validar no backend
       - Se não existe: fazer deployment de novo contrato
    2. Guardar endereço do contrato no .env local
    
    Returns:
        True se sucesso, False se falhou
    """
    console.print("[bold cyan]🔗 Verificando Contrato Inteligente...[/bold cyan]\n")
    
    # Tentar ler CONTRACT_ADDRESS do .env local
    local_contract = read_contract_address_from_env()
    
    if local_contract:
        # Contrato existe no .env local, validar no backend
        console.print(f"[dim]Contrato encontrado no .env local:[/dim] {local_contract}\n")
        console.print("[dim]Validando contrato na blockchain...[/dim]\n")
        
        if validate_contract_via_api(local_contract):
            # Contrato é válido
            console.print(f"[bold green]✓ Sistema pronto para operações![/bold green]\n")
            return True
        else:
            # Contrato não é válido, perguntar se quer fazer deploy novo
            console.print("[yellow]⚠ Contrato não encontrado ou inválido[/yellow]\n")
            
            if Confirm.ask("[bold]Deseja fazer deployment de um novo contrato?[/bold]", default=True):
                manager_private_key = request_and_validate_manager_private_key()
                if not manager_private_key:
                    return False

                console.print("[bold cyan]📦 Fazendo Deployment do Contrato...[/bold cyan]\n")
                new_contract = deploy_contract_locally(manager_private_key)
                
                if new_contract:
                    save_contract_address_to_env(new_contract)
                    console.print(f"[bold green]✓ Contrato guardado localmente[/bold green]\n")
                    console.print("[bold green]✓ Sistema pronto para operações![/bold green]\n")
                    return True
                else:
                    console.print("[red]✗ Falha ao fazer deployment[/red]")
                    return False
            else:
                console.print("[red]✗ Operação cancelada[/red]")
                return False
    else:
        # Contrato não existe no .env local, fazer deployment novo
        console.print("[dim]Nenhum contrato configurado localmente[/dim]")
        console.print("[dim]Será criado um novo contrato...[/dim]\n")
        
        console.print("[bold cyan]📦 Fazendo Deployment do Contrato...[/bold cyan]\n")

        manager_private_key = request_and_validate_manager_private_key()
        if not manager_private_key:
            return False

        new_contract = deploy_contract_locally(manager_private_key)
        
        if new_contract:
            save_contract_address_to_env(new_contract)
            console.print(f"[bold green]✓ Contrato guardado localmente[/bold green]\n")
            console.print("[bold green]✓ Sistema pronto para operações![/bold green]\n")
            return True
        else:
            console.print("[red]✗ Falha ao fazer deployment[/red]")
            return False


# ============================================================
# Utilizadores de teste (endereços conhecidos pelo sistema)
# ============================================================
# As chaves privadas são pedidas ao utilizador quando seleciona um personagem
# O sistema valida se a chave privada gera o endereço esperado

USERS = {
    "1": {
        "name": "Alice (Producer)",
        "id": "alice",
        "role": "PRODUCER",
        "expected_address": ALICE_ADDRESS,
        "priv": None,  # Será preenchido quando o utilizador fornecer a chave
        "public_key": None,  # Será derivado da chave privada
    },
    "2": {
        "name": "Bob (Transporter)",
        "id": "bob",
        "role": "TRANSPORTER",
        "expected_address": BOB_ADDRESS,
        "priv": None,
        "public_key": None,
    },
    "3": {
        "name": "Charlie (Receiver)",
        "id": "charlie",
        "role": "RECEIVER",
        "expected_address": CHARLIE_ADDRESS,
        "priv": None,
        "public_key": None,
    },
}


ROLE_TO_RECORD_TYPES = {
    "PRODUCER": ["PRODUCED"],
    "TRANSPORTER": ["TRANSFER"],
    "RECEIVER": ["RECEIVED"],
}


RECORD_TYPE_LABELS = {
    "PRODUCED": "Produção",
    "TRANSFER": "Transferência Bob -> Charlie",
    "RECEIVED": "Receção por Charlie",
}


# ============================================================
# Funções de autenticação de utilizadores
# ============================================================

def request_and_validate_private_key(user: dict) -> bool:
    """
    Pede a chave privada do utilizador e valida se corresponde ao endereço esperado.
    
    Args:
        user: Dicionário do utilizador com 'name', 'expected_address', etc.
    
    Returns:
        True se a chave privada foi validada com sucesso, False caso contrário
    """
    user_name = user["name"]
    expected_address = user["expected_address"]
    max_attempts = 3
    
    for attempt in range(max_attempts):
        console.print(
            f"\n[bold cyan]🔐 Autenticação: {user_name}[/bold cyan]"
        )
        console.print(f"[dim]Endereço esperado: {expected_address}[/dim]")
        
        private_key = Prompt.ask(
            "[bold]Introduza a chave privada[/bold]",
            password=True
        )
        
        if not private_key:
            console.print("[red]✗ Chave privada não pode estar vazia[/red]")
            continue
        
        # Garantir prefixo 0x
        if not private_key.startswith("0x"):
            private_key = f"0x{private_key}"
        
        try:
            # Validar se a chave corresponde ao endereço esperado
            derived_address = address_from_private_key(private_key)
            
            if derived_address.lower() == expected_address.lower():
                # Guardar a chave privada e derivar a chave pública
                user["priv"] = private_key
                user["public_key"] = public_key_from_private_key(private_key)
                
                console.print(f"[bold green]✓ Autenticação bem-sucedida![/bold green]")
                console.print(f"[dim]Chave pública: {user['public_key']}[/dim]")
                return True
            else:
                console.print(f"[red]✗ Endereço inválido![/red]")
                console.print(f"[dim]Esperado: {expected_address}[/dim]")
                console.print(f"[dim]Obtido: {derived_address}[/dim]")
                remaining = max_attempts - attempt - 1
                if remaining > 0:
                    console.print(f"[yellow]Tentativas restantes: {remaining}[/yellow]")
        except Exception as e:
            console.print(f"[red]✗ Erro ao validar chave: {e}[/red]")
            remaining = max_attempts - attempt - 1
            if remaining > 0:
                console.print(f"[yellow]Tentativas restantes: {remaining}[/yellow]")
    
    console.print(
        "[red]✗ Falha na autenticação após múltiplas tentativas[/red]"
    )
    return False


def show_header(current_user: dict | None = None) -> None:
    """Mostra o cabeçalho da aplicação."""
    console.clear()

    console.print(
        Panel(
            "[bold cyan]🍺 Rastreador de Cerveja Artesanal[/bold cyan]\n"
            "[dim]Sistema de Blockchain para Supply Chain[/dim]",
            title="[bold]Blockchain CLI[/bold]",
            border_style="cyan",
        )
    )

    if current_user:
        private_key = current_user["priv"]
        address = address_from_private_key(private_key)

        console.print(f"[bold green]👤 Utilizador Ativo:[/bold green] {current_user['name']}")
        console.print(f"[dim]Papel: {current_user['role']}[/dim]")
        console.print(f"[dim]Endereço: {address}[/dim]\n")


def select_user(default: str = "1") -> str | None:
    """Permite selecionar um utilizador e autentica-se com a chave privada."""
    console.print("\n[bold cyan]Selecione o Utilizador:[/bold cyan]")

    for key, user in USERS.items():
        console.print(f"  [cyan]{key}[/cyan] - {user['name']}")

    choice = Prompt.ask("Escolha", choices=list(USERS.keys()), default=default)

    chosen = USERS.get(choice)
    if not chosen:
        console.print("[red]✗ Utilizador inválido[/red]")
        return None

    # Pedir e validar a chave privada
    if not request_and_validate_private_key(chosen):
        return None

    return choice


# ============================================================
# Manifestos
# ============================================================

def create_manifest_interactive(
    base_url: str,
    private_key: str,
) -> tuple[str | None, str | None]:
    """Cria um manifesto de forma interativa."""

    console.print("\n[bold cyan]📋 Criar Novo Manifesto[/bold cyan]")
    console.print("[dim]Preencha os dados do lote de cerveja[/dim]\n")

    manifest_id = Prompt.ask(
        "[bold]ID do Manifesto[/bold]",
        default=f"manifest-{datetime.now().strftime('%Y%m%d%H%M%S')}",
    )

    good_type = Prompt.ask("[bold]Tipo de Cerveja[/bold]", default="IPA Artesanal")
    quantity = float(Prompt.ask("[bold]Quantidade[/bold]", default="100"))
    unit = Prompt.ask("[bold]Unidade[/bold]", default="litros")

    console.print("\n[bold]Ingredientes[/bold] separados por espaço:")
    ingredients_str = Prompt.ask("Ex: água malte lúpulo", default="água malte lúpulo")
    ingredients = ingredients_str.split()

    origin = Prompt.ask("[bold]Origem[/bold]", default="Douro, Portugal")
    sustainability = Prompt.ask("[bold]Certificação[/bold]", default="Produção Responsável")

    if not Confirm.ask("\n[bold]Confirmar criação de manifesto?[/bold]", default=True):
        console.print("[yellow]⊘ Cancelado[/yellow]")
        return None, None

    manager_private_key = request_and_validate_manager_private_key()
    if not manager_private_key:
        console.print("[red]✗ Criação cancelada: Supply Manager não validado[/red]")
        return None, None

    payload = {
        "manifest_id": manifest_id,
        "good_type": good_type,
        "quantity": quantity,
        "unit": unit,
        "ingredients": ingredients,
        "origin": origin,
        "sustainability": sustainability,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    console.print("\n[dim]Assinando payload do manifesto...[/dim]")

    contract_address = read_contract_address_from_env() or Prompt.ask("Contract address (0x...)")
    try:
        body, payload_hash = create_signed_api_request(
            payload=payload,
            user_private_key=private_key,
            manager_private_key=manager_private_key,
            role="PRODUCER",
            contract_address=contract_address,
            item_id=payload["manifest_id"],
            timestamp_iso=payload["timestamp"],
        )
    except RuntimeError as exc:
        console.print(f"[red]✗ {exc}[/red]")
        return None, None

    console.print(f"[yellow]PAYLOAD HASH:[/yellow] {payload_hash}")
    console.print(f"[yellow]USER SIGNATURE:[/yellow] {body['auth']['signature']}")
    console.print(f"[yellow]MANAGER SIGNATURE:[/yellow] {body['auth']['manager_signature']}")

    console.print(f"\n[dim]Enviando para {base_url}/manifests...[/dim]")
    result = post_json(f"{base_url}/manifests", body)

    if not result:
        console.print("[red]✗ Erro ao criar manifesto[/red]")
        return None, None

    console.print("[green]✓ Manifesto criado com sucesso![/green]")
    tx_hash = result.get("tx_hash") or result.get("anchor", {}).get("tx_hash")
    if tx_hash:
        console.print(f"[bold cyan]TXID da transação:[/bold cyan] {tx_hash}")
        console.print(f"[dim]Explorer: https://sepolia.etherscan.io/tx/{tx_hash}[/dim]")

    return manifest_id, None


def create_bob_manifest_after_transfer(
    *,
    base_url: str,
    private_key: str,
    manager_private_key: str,
    parent_manifest_id: str,
    transfer_record_id: str,
    transferred_quantity: float,
    contract_address: str,
) -> str | None:
    """Cria um novo manifesto do Bob com a quantidade restante após TRANSFER."""

    parent = get_json(f"{base_url}/manifests/{parent_manifest_id}")
    parent_payload = parent.get("payload") if parent else None
    if not parent_payload:
        console.print("[yellow]⚠ Não foi possível obter o manifesto original para criar a versão do Bob.[/yellow]")
        return None

    remaining_quantity = float(parent_payload["quantity"]) - transferred_quantity
    if remaining_quantity <= 0:
        console.print("[yellow]⚠ Transferência consumiu todo o manifesto; não há quantidade restante para novo manifesto do Bob.[/yellow]")
        return None

    bob_manifest_id = f"manifest-derived-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    root_manifest_id = parent_payload.get("root_manifest_id") or parent_manifest_id

    payload = {
        "manifest_id": bob_manifest_id,
        "good_type": parent_payload["good_type"],
        "quantity": remaining_quantity,
        "unit": parent_payload["unit"],
        "ingredients": parent_payload["ingredients"],
        "origin": parent_payload["origin"],
        "sustainability": parent_payload["sustainability"],
        "owner_user_id": "bob",
        "root_manifest_id": root_manifest_id,
        "parent_manifest_id": parent_manifest_id,
        "source_record_id": transfer_record_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    console.print(
        f"[dim]Criando manifesto derivado do Bob com {remaining_quantity} {parent_payload['unit']}...[/dim]"
    )
    console.print(f"[dim]Root manifesto original: {root_manifest_id}[/dim]")
    console.print(f"[dim]ID automático do manifesto derivado: {bob_manifest_id}[/dim]")

    try:
        body, payload_hash = create_signed_api_request(
            payload=payload,
            user_private_key=private_key,
            manager_private_key=manager_private_key,
            role="TRANSPORTER",
            contract_address=contract_address,
            item_id=payload["manifest_id"],
            timestamp_iso=payload["timestamp"],
        )
    except RuntimeError as exc:
        console.print(f"[red]✗ {exc}[/red]")
        return None

    console.print(f"[yellow]BOB MANIFEST HASH:[/yellow] {payload_hash}")
    result = post_json(f"{base_url}/manifests", body)
    if not result:
        console.print("[red]✗ Falha ao criar manifesto derivado do Bob[/red]")
        return None

    console.print("[green]✓ Manifesto derivado do Bob criado e ancorado![/green]")
    tx_hash = result.get("tx_hash") or result.get("anchor", {}).get("tx_hash")
    if tx_hash:
        console.print(f"[bold cyan]TXID do manifesto Bob:[/bold cyan] {tx_hash}")
        console.print(f"[dim]Explorer: https://sepolia.etherscan.io/tx/{tx_hash}[/dim]")

    return bob_manifest_id


# ============================================================
# Registos
# ============================================================

def resolve_record_manifest_id(base_url: str, last_manifest_id: str | None) -> str | None:
    """Usar sempre o último manifesto disponível para criar records."""
    if last_manifest_id:
        console.print(f"[dim]Manifesto usado automaticamente: {last_manifest_id}[/dim]")
        return last_manifest_id

    latest = get_json(f"{base_url}/manifests")
    manifest_id = latest.get("payload", {}).get("manifest_id", "") if latest else ""
    if manifest_id:
        console.print(f"[dim]Manifesto usado automaticamente: {manifest_id}[/dim]")
        return manifest_id

    console.print("[red]✗ Não existe último manifesto disponível para criar o registo[/red]")
    return None


def ensure_manifest_verified_before_record(manifest_id: str) -> bool:
    """Bloquear criação de records sobre manifestos corrompidos."""
    console.print(f"[dim]Verificando manifesto '{manifest_id}' contra a blockchain...[/dim]")
    is_valid, data, reason = get_verified_resource_status("manifests", manifest_id)

    if is_valid:
        tx_hash = data.get("tx_hash") if data else None
        console.print("[green]✓ Manifesto íntegro e confirmado na blockchain[/green]")
        if tx_hash:
            console.print(f"[dim]Manifest TX: {tx_hash}[/dim]")
        return True

    console.print(f"[red]✗ Manifesto inválido: {reason}[/red]")
    if data:
        verification = data.get("verification") or {}
        console.print(f"[dim]Hash local == hash guardado: {verification.get('hash_matches')}[/dim]")
        console.print(f"[dim]Hash local == hash blockchain: {verification.get('blockchain_hash_matches')}[/dim]")
        console.print(f"[dim]TX blockchain válida: {verification.get('blockchain_tx_valid')}[/dim]")
        console.print(f"[dim]Item ID blockchain coincide: {verification.get('blockchain_item_matches')}[/dim]")
    console.print("[red]✗ Registo cancelado para evitar associar operação a manifesto corrompido[/red]")
    return False


def select_pending_transfer_for_receipt(base_url: str) -> dict | None:
    """Selecionar uma TRANSFER Bob -> Charlie ainda não confirmada por RECEIVED."""
    console.print("[dim]A procurar TRANSFERs sem confirmação RECEIVED associada...[/dim]")
    result = get_json(f"{base_url}/records/pending-transfers")
    transfers = result.get("transfers", []) if result else []
    valid_transfers = [
        transfer
        for transfer in transfers
        if (transfer.get("verification") or {}).get("overall_valid") is True
    ]

    if not valid_transfers:
        if transfers:
            console.print("[red]✗ Existem TRANSFERs pendentes, mas nenhuma é válida na blockchain[/red]")
            console.print("[red]✗ Charlie não pode confirmar uma receção sem TRANSFER íntegra[/red]")
        else:
            console.print("[red]✗ Não existem mais registos TRANSFER para confirmar[/red]")
        return None

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("#", style="cyan", width=4)
    table.add_column("Record ID", style="white")
    table.add_column("Manifesto", style="white")
    table.add_column("Quantidade", justify="right")

    for index, transfer in enumerate(valid_transfers, start=1):
        payload = transfer.get("payload", {})
        table.add_row(
            str(index),
            payload.get("record_id", ""),
            payload.get("manifest_id", ""),
            str(payload.get("quantity", "")),
        )

    console.print(table)

    if len(valid_transfers) == 1:
        console.print("[dim]Selecionada automaticamente a única TRANSFER pendente.[/dim]")
        return valid_transfers[0]

    selected = Prompt.ask(
        "[bold]TRANSFER a confirmar[/bold]",
        choices=[str(index) for index in range(1, len(valid_transfers) + 1)],
        default="1",
    )
    return valid_transfers[int(selected) - 1]


def _record_payload_is_valid(record: dict) -> bool:
    return (record.get("verification") or {}).get("overall_valid") is True


def display_record_lookup_tables(base_url: str) -> None:
    """Mostrar tabelas de TRANSFER e RECEIVED para ajudar a escolher registos."""
    result = get_json(f"{base_url}/records/lookup")
    if not result:
        console.print("[red]✗ Não foi possível obter as tabelas de registos[/red]")
        return

    received_records = result.get("received", [])
    confirmed_transfer_ids = {
        payload.get("related_record_id")
        for record in received_records
        if (payload := record.get("payload", {})).get("related_record_id")
    }

    def build_table(title: str, records: list[dict], *, show_confirmation: bool = False) -> Table:
        table = Table(title=title, show_header=True, header_style="bold cyan")
        table.add_column("#", style="cyan", width=4)
        table.add_column("Record ID", style="white")
        table.add_column("Manifesto", style="white")
        table.add_column("Quantidade", justify="right")
        if show_confirmation:
            table.add_column("Confirmado", style="white")
        table.add_column("Estado", style="white")

        if not records:
            empty_row = ["-", "sem registos", "-", "-"]
            if show_confirmation:
                empty_row.append("-")
            empty_row.append("-")
            table.add_row(*empty_row)
            return table

        for index, record in enumerate(records, start=1):
            payload = record.get("payload", {})
            status = "[green]válido[/green]" if _record_payload_is_valid(record) else "[red]inválido[/red]"
            row = [
                str(index),
                payload.get("record_id", ""),
                payload.get("manifest_id", ""),
                str(payload.get("quantity", "")),
            ]
            if show_confirmation:
                confirmed = payload.get("record_id") in confirmed_transfer_ids
                row.append("[green]sim[/green]" if confirmed else "[yellow]não[/yellow]")
            row.append(status)
            table.add_row(*row)
        return table

    console.print()
    console.print(build_table("Registos TRANSFER", result.get("transfers", []), show_confirmation=True))
    console.print()
    console.print(build_table("Registos RECEIVED / DELIVERED", received_records))


def show_manifest_chain_and_get_max_transfer(base_url: str, manifest_id: str) -> float | None:
    """Mostrar cadeia root -> derivados e devolver máximo transferível."""
    chain_data = get_json(f"{base_url}/manifests/{manifest_id}/chain")
    if not chain_data:
        console.print("[red]✗ Não foi possível obter a cadeia de manifestos[/red]")
        return None

    root_manifest_id = chain_data.get("root_manifest_id", manifest_id)
    max_quantity = float(chain_data.get("max_transfer_quantity", 0))
    unit = chain_data.get("unit", "")

    console.print("\n[bold cyan]⛓ Cadeia de Manifestos[/bold cyan]")
    console.print(f"[dim]Root: {root_manifest_id}[/dim]")

    chain = chain_data.get("chain", [])
    for index, item in enumerate(chain):
        connector = "└─" if index == len(chain) - 1 else "├─"
        marker = "[bold green]*[/bold green]" if item.get("manifest_id") == manifest_id else " "
        quantity = float(item.get("quantity", 0))
        transferred = float(item.get("transferred_quantity", 0))
        available = float(item.get("available_quantity", 0))
        unit_label = item.get("unit", unit)

        console.print(
            f"{connector} {marker} [bold]{item.get('manifest_id')}[/bold] "
            f"quantidade: [bold]{quantity:g}[/bold] {unit_label}"
        )
        if item.get("parent_manifest_id"):
            console.print(f"   root: {item.get('root_manifest_id')} | parent: {item.get('parent_manifest_id')}")
        for transfer in item.get("transfers", []):
            console.print(
                f"   └─ TRANSFER {transfer.get('record_id')}: {float(transfer.get('quantity', 0)):g} {unit_label}"
            )
        if item.get("manifest_id") == manifest_id:
            console.print(
                f"   disponível para Bob: {quantity:g} - {transferred:g} = "
                f"[bold]{available:g}[/bold] {unit_label}"
            )

    console.print(f"[bold yellow]Quantidade máxima que Bob pode transferir agora:[/bold yellow] {max_quantity:g} {unit}")
    return max_quantity


def create_record_interactive_for_role(
    base_url: str,
    private_key: str,
    role: str,
    last_manifest_id: str | None = None,
    last_record_id: str | None = None,
) -> tuple[str, str | None] | None:
    """Cria um registo filtrando os tipos permitidos pelo papel do utilizador."""

    allowed_types = ROLE_TO_RECORD_TYPES.get(role, [])

    if not allowed_types:
        console.print(f"[red]✗ Papel sem permissões configuradas: {role}[/red]")
        return None

    console.print("\n[bold cyan]📝 Criar Novo Registo de Operação[/bold cyan]")
    console.print(f"[dim]Papel atual: {role}[/dim]")

    choice_map: dict[str, str] = {}

    console.print("\n[bold]Tipo de Operação Permitido:[/bold]")

    for index, record_type in enumerate(allowed_types, start=1):
        key = str(index)
        choice_map[key] = record_type
        label = RECORD_TYPE_LABELS.get(record_type, record_type)
        console.print(f"  [cyan]{key}[/cyan] - {record_type} ({label})")

    if len(allowed_types) == 1:
        record_type = allowed_types[0]
        console.print(f"[dim]Selecionado automaticamente: {record_type}[/dim]")
    else:
        selected = Prompt.ask("Escolha", choices=list(choice_map.keys()), default="1")
        record_type = choice_map[selected]

    manifest_id = ""
    quantity: float | None = None
    related_record_id = None
    record_id_default = f"record-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    if record_type == "RECEIVED":
        transfer_record = select_pending_transfer_for_receipt(base_url)
        transfer_payload = transfer_record.get("payload") if transfer_record else None
        if not transfer_payload or transfer_payload.get("record_type") != "TRANSFER":
            console.print("[red]✗ O record indicado não é uma TRANSFER válida Bob -> Charlie[/red]")
            return None

        related_record_id = transfer_payload["record_id"]
        manifest_id = transfer_payload["manifest_id"]
        quantity = float(transfer_payload["quantity"])
        record_id_default = f"received-{related_record_id}"
        console.print(f"[dim]TRANSFER selecionada: {related_record_id}[/dim]")
        console.print(f"[dim]Manifesto preenchido automaticamente: {manifest_id}[/dim]")
        console.print(f"[dim]Quantidade preenchida automaticamente: {quantity}[/dim]")

    if record_type != "RECEIVED":
        manifest_id = resolve_record_manifest_id(base_url, last_manifest_id) or ""

    if not manifest_id:
        console.print("[red]✗ Erro: ID do manifesto é obrigatório[/red]")
        return None

    if not ensure_manifest_verified_before_record(manifest_id):
        return None

    max_transfer_quantity = None
    if record_type == "TRANSFER" and role == "TRANSPORTER":
        max_transfer_quantity = show_manifest_chain_and_get_max_transfer(base_url, manifest_id)
        if max_transfer_quantity is None:
            return None
        if max_transfer_quantity <= 0:
            console.print("[red]✗ Não existe quantidade disponível para nova transferência[/red]")
            return None

    if quantity is None:
        quantity_default = f"{max_transfer_quantity:g}" if max_transfer_quantity is not None else "50"
        while True:
            quantity = float(Prompt.ask("[bold]Quantidade[/bold]", default=quantity_default))
            if max_transfer_quantity is None or quantity <= max_transfer_quantity:
                break
            console.print(
                f"[red]✗ Quantidade inválida: máximo permitido é {max_transfer_quantity:g}[/red]"
            )
            quantity_default = f"{max_transfer_quantity:g}"
    sender_user_id = None

    if record_type == "TRANSFER":
        console.print("[dim]Fluxo configurado: Bob transfere, Charlie recebe.[/dim]")
    elif record_type == "RECEIVED":
        sender_user_id = BOB_ADDRESS
        console.print("[dim]Fluxo configurado: Charlie confirma receção enviada pelo endereço público do Bob.[/dim]")

    record_id = Prompt.ask("[bold]ID do Registo[/bold]", default=record_id_default)

    notes = Prompt.ask("[bold]Notas[/bold] (opcional)", default="")

    if not Confirm.ask("\n[bold]Confirmar criação de registo?[/bold]", default=True):
        console.print("[yellow]⊘ Cancelado[/yellow]")
        return None

    manager_private_key = request_and_validate_manager_private_key()
    if not manager_private_key:
        console.print("[red]✗ Criação cancelada: Supply Manager não validado[/red]")
        return None

    payload = {
        "record_id": record_id,
        "record_type": record_type,
        "manifest_id": manifest_id,
        "quantity": quantity,
        "sender_user_id": sender_user_id,
        "related_record_id": related_record_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "notes": notes,
    }
    payload = {key: value for key, value in payload.items() if value is not None}

    console.print("\n[dim]Assinando payload do registo...[/dim]")

    contract_address = read_contract_address_from_env() or Prompt.ask("Contract address (0x...)")
    try:
        body, payload_hash = create_signed_api_request(
            payload=payload,
            user_private_key=private_key,
            manager_private_key=manager_private_key,
            role=role,
            contract_address=contract_address,
            item_id=payload["record_id"],
            timestamp_iso=payload["timestamp"],
        )
    except RuntimeError as exc:
        console.print(f"[red]✗ {exc}[/red]")
        return None

    console.print(f"[yellow]PAYLOAD HASH:[/yellow] {payload_hash}")
    console.print("[yellow]SIGNED ANCHOR TX:[/yellow] pronta para broadcast no backend")
    console.print(f"[yellow]USER SIGNATURE:[/yellow] {body['auth']['signature']}")
    console.print(f"[yellow]MANAGER SIGNATURE:[/yellow] {body['auth']['manager_signature']}")

    console.print(f"\n[dim]Enviando para {base_url}/records...[/dim]")
    result = post_json(f"{base_url}/records", body)

    if result:
        console.print("[green]✓ Registo criado com sucesso![/green]")
        tx_hash = result.get("tx_hash") or result.get("anchor", {}).get("tx_hash")
        if tx_hash:
            console.print(f"[bold cyan]TXID da transação:[/bold cyan] {tx_hash}")
            console.print(f"[dim]Explorer: https://sepolia.etherscan.io/tx/{tx_hash}[/dim]")
        if record_type == "TRANSFER" and role == "TRANSPORTER":
            derived_manifest_id = create_bob_manifest_after_transfer(
                base_url=base_url,
                private_key=private_key,
                manager_private_key=manager_private_key,
                parent_manifest_id=manifest_id,
                transfer_record_id=record_id,
                transferred_quantity=quantity,
                contract_address=contract_address,
            )
            if derived_manifest_id:
                return record_id, derived_manifest_id
        return record_id, None

    console.print("[red]✗ Erro ao criar registo[/red]")
    return None


# ============================================================
# Verificação
# ============================================================

def verify_data() -> None:
    """Verifica dados contra o backend obtendo a verificação criptográfica integrada no GET."""

    console.print("\n[bold cyan]🔍 Verificar Dados[/bold cyan]")

    endpoint_choice = Prompt.ask(
        "O que deseja verificar? Manifestos (m) ou Registos (r)",
        choices=["m", "r"],
        default="r",
    )

    endpoint_map = {
        "m": "manifests",
        "r": "records",
    }

    endpoint_path = endpoint_map[endpoint_choice.lower()]
    item_label = "Manifesto" if endpoint_choice == "m" else "Registo"

    item_id = ""
    if endpoint_choice == "r":
        while True:
            lookup_choice = Prompt.ask(
                "Como quer escolher o registo? Último (u), ID específico (i), ou tabelas (t)",
                choices=["u", "i", "t"],
                default="u",
            )
            if lookup_choice == "u":
                item_id = ""
                break
            if lookup_choice == "i":
                item_id = Prompt.ask(f"ID de {item_label}", default="")
                if item_id:
                    break
                console.print("[yellow]Indique um ID ou escolha outra opção.[/yellow]")
                continue
            display_record_lookup_tables(BASE_URL)
    else:
        item_id = Prompt.ask(f"ID de {item_label} (Enter para usar o último)", default="")

    # Fazer GET que já inclui verificação criptográfica integrada
    url = f"{BASE_URL}/{endpoint_path}/{item_id}" if item_id else f"{BASE_URL}/{endpoint_path}"
    data = get_json(url)

    if not data:
        console.print("[red]✗ Não foi possível obter os dados[/red]")
        return

    if "error" in data:
        console.print(f"[red]✗ Erro: {data['error']}[/red]")
        return

    # Extrair verificação que vem integrada no GET
    verification = data.get("verification")

    if not verification:
        console.print("[red]✗ Erro: dados de verificação não encontrados[/red]")
        return

    # Extrair resultado da verificação
    payload_hash_blockchain = data.get("payload_hash", "N/A")
    payload_hash_current = data.get("payload_hash_current", "N/A")
    
    hash_match = payload_hash_blockchain == payload_hash_current
    is_valid = verification.get("overall_valid") is True
    
    signature_valid = verification.get("signature_valid")
    manager_public_key_valid = verification.get("manager_public_key_valid")
    manager_signature_valid = verification.get("manager_signature_valid")

    # ========== BANNER PRINCIPAL ==========
    if is_valid:
        banner_content = (
            "[bold green]✓ VÁLIDO[/bold green]\n"
            "[dim green]Dados íntegros e verificados na blockchain[/dim green]"
        )
        banner_style = "bold green"
    else:
        banner_content = (
            "[bold red]✗ INVÁLIDO[/bold red]\n"
            "[dim red]Dados comprometidos ou não verificáveis[/dim red]"
        )
        banner_style = "bold red"

    console.print(
        Panel(
            banner_content,
            title="[bold]RESULTADO DA VERIFICAÇÃO[/bold]",
            border_style=banner_style,
            padding=(1, 3),
        )
    )

    # ========== DADOS ==========
    console.print("\n[bold cyan]📋 Dados do " + item_label + ":[/bold cyan]")
    payload = data.get("payload", {})
    console.print(json.dumps(payload, indent=2, ensure_ascii=False))

    tx_hash = data.get("tx_hash") or data.get("anchor", {}).get("tx_hash")
    if tx_hash:
        tx_creator = verification.get("blockchain_from_address") or "N/A"
        console.print(
            Panel(
                f"[bold]Hash da transação:[/bold]\n[bold cyan]{tx_hash}[/bold cyan]\n\n"
                f"[bold]Criada por:[/bold]\n[cyan]{tx_creator}[/cyan]\n\n"
                f"[dim]https://sepolia.etherscan.io/tx/{tx_hash}[/dim]",
                title="[bold]🔗 TXID Blockchain[/bold]",
                border_style="cyan",
                padding=(1, 2),
            )
        )

    # ========== HASH PAYLOAD ==========
    match_icon = "[bold green]✓[/bold green]" if hash_match else "[bold red]✗[/bold red]"
    match_status = "[green]Igual (íntegro)[/green]" if hash_match else "[red]Diferente (alterado)[/red]"
    
    console.print(
        Panel(
            f"[bold yellow]{payload_hash_current}[/bold yellow]\n\n"
            f"{match_icon} Comparação com blockchain: {match_status}",
            title="[bold]🔗 Payload Hash (Recalculado Agora)[/bold]",
            border_style="yellow",
            padding=(1, 2),
        )
    )

    def status_text(value: bool | None) -> str:
        if value is True:
            return "[green]✓ Válido[/green]"
        if value is False:
            return "[red]✗ Inválido[/red]"
        return "[yellow]⚠ Não disponível[/yellow]"

    signature_table = Table(show_header=True, header_style="bold cyan")
    signature_table.add_column("Verificação", style="cyan")
    signature_table.add_column("Resultado", style="white")
    signature_table.add_row(
        "Assinatura user ↔ chave pública user",
        status_text(signature_valid),
    )
    signature_table.add_row(
        "Assinatura manager ↔ chave pública manager",
        status_text(manager_signature_valid),
    )
    console.print(
        Panel(
            signature_table,
            title="[bold]🔐 Assinaturas[/bold]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    # ========== RESUMO FINAL ==========
    console.print()
    if is_valid:
        console.print(
            Panel(
                "[bold green]🎉 Dados autenticados e íntegros![/bold green]\n"
                "[dim]Hash, blockchain, user e Supply Manager confirmados.[/dim]",
                border_style="green",
                padding=(1, 2),
            )
        )
    else:
        console.print(
            Panel(
                "[bold red]⚠️  ALERTA: Dados inválidos![/bold red]\n"
                "[dim red]Hash, transação ou assinaturas não correspondem aos dados guardados.[/dim red]",
                border_style="red",
                padding=(1, 2),
            )
        )


# ============================================================
# Ataque / Tamper
# ============================================================

def simulate_attack(
    *,
    role: str,
    last_manifest_id: str | None = None,
    last_record_id: str | None = None,
) -> None:
    """Simula um ataque alterando dados na base de dados."""

    console.print("\n[bold red]⚠️ Simular Ataque / Alteração de Dados[/bold red]")

    if role == "PRODUCER":
        endpoint = "manifests"
        item_label = "Manifesto"
        item_id_key = "manifest_id"
        default_item_id = last_manifest_id
        console.print("[dim]Alice/Producer só pode alterar manifestos.[/dim]")
    else:
        endpoint = "records"
        item_label = "Registo"
        item_id_key = "record_id"
        default_item_id = last_record_id
        console.print("[dim]Transporter/Receiver só podem alterar registos.[/dim]")

    item_id = Prompt.ask(
        f"ID de {item_label} a ser alterado (Enter para usar o último)",
        default=default_item_id or "",
    )
    if not item_id:
        latest = get_json(f"{BASE_URL}/{endpoint}")
        item_id = latest.get("payload", {}).get(item_id_key, "")

    if not item_id:
        console.print(f"[red]✗ Não foi possível determinar o último {item_label.lower()}[/red]")
        return

    new_quantity = Prompt.ask("Nova quantidade falsa")

    data = put_json(
        f"{BASE_URL}/{endpoint}/{item_id}/tamper",
        {"new_quantity": float(new_quantity)},
    )
    if not data:
        return

    console.print(f"[bold red]✓ {data.get('message', 'Alterado com sucesso')}[/bold red]")
    console.print(
        "[dim]Agora usa a opção 2, 'Verificar Dados', para mostrar que a integridade falha.[/dim]"
    )


# ============================================================
# Menu principal
# ============================================================

def build_menu_options(role: str) -> dict[str, tuple[str, str]]:
    """Constrói o menu com base no papel do utilizador."""

    options: dict[str, tuple[str, str]] = {}
    next_option = 1

    if role == "PRODUCER":
        options[str(next_option)] = (
            "create_manifest",
            "Criar Manifesto",
        )
        next_option += 1

    # O produtor cria apenas manifestos; o record PRODUCED deixou de ser necessário.
    if role in ROLE_TO_RECORD_TYPES and role != "PRODUCER":
        action_label = "Criar registo da sua função"
        if role == "TRANSPORTER":
            action_label = "Transferir"
        elif role == "RECEIVER":
            action_label = "Confirmar receção"
        options[str(next_option)] = (
            "create_record",
            action_label,
        )
        next_option += 1

    options[str(next_option)] = ("verify", "Verificar Dados")
    next_option += 1

    options[str(next_option)] = ("switch_user", "Trocar Utilizador")
    next_option += 1

    options[str(next_option)] = ("attack", "[red]Simular Ataque[/red] / Alterar DB")
    next_option += 1

    options[str(next_option)] = ("exit", "Sair")

    return options


def run_app(initial_user_id: str | None) -> None:
    """Executa a aplicação CLI."""

    if not initial_user_id:
        console.print("[red]✗ Falha na autenticação inicial[/red]")
        return

    current_user_id = initial_user_id
    last_manifest_id: str | None = None
    last_record_id: str | None = None

    while True:
        user = USERS[current_user_id]
        role = user["role"]
        private_key = user["priv"]
        
        if not private_key:
            console.print("[red]✗ Erro: chave privada não autenticada[/red]")
            return
        
        show_header(user)

        console.print("\n[bold]O que deseja fazer?[/bold]\n")

        options = build_menu_options(role)

        for key, (_, label) in options.items():
            console.print(f"  [cyan]{key}[/cyan] - {label}")

        if last_manifest_id:
            console.print(f"\n[dim]Último manifesto: {last_manifest_id}[/dim]")
        if last_record_id:
            console.print(f"[dim]Último registo: {last_record_id}[/dim]")

        choice = Prompt.ask("\nEscolha", choices=list(options.keys()), default="1")
        action = options[choice][0]

        if action == "create_manifest":
            manifest_id, _ = create_manifest_interactive(
                base_url=BASE_URL,
                private_key=private_key,
            )

            if manifest_id:
                last_manifest_id = manifest_id

        elif action == "create_record":
            record_result = create_record_interactive_for_role(
                base_url=BASE_URL,
                private_key=private_key,
                role=role,
                last_manifest_id=last_manifest_id,
                last_record_id=last_record_id,
            )
            if record_result:
                record_id, derived_manifest_id = record_result
                last_record_id = record_id
                if derived_manifest_id:
                    last_manifest_id = derived_manifest_id

        elif action == "verify":
            verify_data()

        elif action == "switch_user":
            new_user_id = select_user(default=current_user_id)
            if new_user_id:
                current_user_id = new_user_id
            continue

        elif action == "attack":
            simulate_attack(
                role=role,
                last_manifest_id=last_manifest_id,
                last_record_id=last_record_id,
            )

        elif action == "exit":
            console.print("[yellow]Até logo! 👋[/yellow]")
            sys.exit(0)

        input("\n[dim]Pressione Enter para continuar...[/dim]")


def main() -> None:
    """Ponto de entrada da aplicação."""

    # Verificar e configurar o blockchain no startup
    if not initialize_blockchain_setup():
        console.print("[red]✗ Não foi possível inicializar o blockchain[/red]")
        sys.exit(1)

    user_id = select_user(default="1")
    
    if not user_id:
        console.print("[red]✗ Falha na seleção e autenticação do utilizador[/red]")
        sys.exit(1)

    try:
        run_app(user_id)
    except KeyboardInterrupt:
        console.print("\n[yellow]Aplicação encerrada pelo utilizador[/yellow]")
        sys.exit(0)


if __name__ == "__main__":
    main()
