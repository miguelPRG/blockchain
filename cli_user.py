"""CLI interativa para assinatura de manifestos/registos e testagem de blockchain com múltiplos usuários."""

from __future__ import annotations

import json
import sys
import logging
import os
from datetime import datetime, timezone
from urllib import request as urlrequest
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table

# Adicionar PYTHONPATH para importar do app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from app.core.hashing import sha256_hex
from app.core.security import sign_hash, get_public_key_from_private, address_from_public_key
from app.core.hashing import canonical_json

# Configurar logging COM ficheiro
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/blockchain_cli_debug.log'),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

console = Console()

# Predefined dummy users for testing role-based authentication
USERS = {
    "1": {
        "name": "Alice (Producer)",
        "role": "PRODUCER",
        "priv": "0x1111111111111111111111111111111111111111111111111111111111111111",
    },
    "2": {
        "name": "Bob (Transporter)",
        "role": "TRANSPORTER",
        "priv": "0x2222222222222222222222222222222222222222222222222222222222222222",
    },
    "3": {
        "name": "Charlie (Receiver)",
        "role": "RECEIVER",
        "priv": "0x3333333333333333333333333333333333333333333333333333333333333333",
    },
}


ROLE_TO_RECORD_TYPES = {
    "TRANSPORTER": ["TRANSFER", "DELIVERY"],
    "RECEIVER": ["RECEIVED"],
}

def post_json(url: str, payload: dict) -> dict:
    """Enviar carga JSON para API e analisar resposta JSON."""
    try:
        req = urlrequest.Request(url=url, method="POST", data=json.dumps(payload).encode("utf-8"))
        req.add_header("Content-Type", "application/json")
        with urlrequest.urlopen(req) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))
    except urlrequest.HTTPError as e:
        try:
            error_detail = json.loads(e.read().decode("utf-8"))
            console.print(f"[red]✗ Erro HTTP {e.code}:[/red] {error_detail.get('detail', str(error_detail))}")
        except Exception:
            console.print(f"[red]✗ Erro HTTP {e.code}:[/red] {e.reason}")
        return {}
    except Exception as e:
        console.print(f"[red]✗ Erro na requisição:[/red] {e}")
        return {}


def show_header(current_user: dict | None = None):
    """Mostrar cabeçalho da aplicação."""
    console.clear()
    console.print(Panel(
        "[bold cyan]🍺 Rastreador de Cerveja Artesanal[/bold cyan]\n"
        "[dim]Sistema de Blockchain para Supply Chain[/dim]",
        title="[bold]Blockchain CLI[/bold]",
        border_style="cyan"
    ))
    if current_user:
        pub = f"0x{get_public_key_from_private(current_user['priv'][2:])}"
        addr = address_from_public_key(pub)
        console.print(f"[bold green]👤 Usuário Ativo:[/bold green] {current_user['name']}")
        console.print(f"[dim]Endereço: {addr}[/dim]\n")


def create_manifest_interactive(base_url: str, private_key: str, public_key: str) -> tuple[str | None, str | None]:
    """Criar manifesto de forma interativa. Retorna (manifest_id, payload_hash)."""
    console.print("\n[bold cyan]📋 Criar Novo Manifesto[/bold cyan]")
    console.print("[dim]Preencha os dados do lote de cerveja[/dim]\n")
        
    manifest_id = Prompt.ask("[bold]ID do Manifesto[/bold]", default=f"manifest-{datetime.now().strftime('%Y%m%d%H%M%S')}")
    good_type = Prompt.ask("[bold]Tipo de Cerveja[/bold]", default="IPA Artesanal")
    quantity = float(Prompt.ask("[bold]Quantidade[/bold]", default="100"))
    unit = Prompt.ask("[bold]Unidade[/bold]", default="litros")
    
    console.print("\n[bold]Ingredientes[/bold] (separe com espaço):")
    ingredients_str = Prompt.ask("Ex: água malte lúpulo", default="água malte lúpulo")
    ingredients = ingredients_str.split()
    
    origin = Prompt.ask("[bold]Origem[/bold]", default="Douro, Portugal")
    sustainability = Prompt.ask("[bold]Certificação[/bold]", default="Produção Responsável")
    
    # Confirmar
    if not Confirm.ask("\n[bold]Confirmar criação de manifesto?[/bold]", default=True):
        console.print("[yellow]⊘ Cancelado[/yellow]")
        return None, None
    
    # Construir payload
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
    
    # Assinar
    console.print("\n[dim]Calculando hash SHA-256...[/dim]")
    
    payload_hash = sha256_hex(payload)
    console.print(f"[yellow]PAYLOAD HASH: {payload_hash}[/yellow]")
    
    signature = sign_hash(private_key[2:], payload_hash)  # Remove 0x
    console.print(f"[yellow]SIGNATURE: {signature}[/yellow]")
    
    body = {
        "payload": payload,
        "auth": {
            "public_key": public_key,
            "signature": signature
        }
    }
    
    # Enviar
    console.print(f"\n[dim]Enviando para {base_url}/manifests...[/dim]")
    result = post_json(f"{base_url}/manifests", body)
    
    if result:
        console.print("[green]✓ Manifesto criado com sucesso![/green]")
        return manifest_id, payload_hash
    else:
        console.print("[red]✗ Erro ao criar manifesto[/red]")
        return None, None


def create_record_interactive(base_url: str, private_key: str, public_key: str, last_manifest_id: str | None = None) -> str | None:
    """Criar registo de operação de forma interativa. Retorna record_id."""
    console.print("\n[bold cyan]📝 Criar Novo registo de Operação[/bold cyan]")
    
    record_id = Prompt.ask("[bold]ID do registo[/bold]", default=f"record-{datetime.now().strftime('%Y%m%d%H%M%S')}")
    
    # Escolher tipo
    console.print("\n[bold]Tipo de Operação:[/bold]")
    console.print("  [cyan]1[/cyan] - PRODUCED (Produção)")
    console.print("  [cyan]2[/cyan] - TRANSFER (Transferência)")
    console.print("  [cyan]3[/cyan] - RECEIVED (Recebimento)")
    console.print("  [cyan]4[/cyan] - DELIVERY (Entrega)")
    
    type_choice = Prompt.ask("Escolha", choices=["1", "2", "3", "4"], default="1")
    type_map = {"1": "PRODUCED", "2": "TRANSFER", "3": "RECEIVED", "4": "DELIVERY"}
    record_type = type_map[type_choice]
    
    # Pedir o ID do manifesto
    if last_manifest_id:
        console.print(f"[dim]Último ID: {last_manifest_id}[/dim]")
    manifest_id = Prompt.ask("[bold]ID do Manifesto[/bold]", default=last_manifest_id or "")
    
    if not manifest_id:
        console.print("[red]✗ Erro: ID do manifesto é obrigatório[/red]")
        return None
    
    quantity = float(Prompt.ask("[bold]Quantidade[/bold]", default="50"))
    unit = Prompt.ask("[bold]Unidade[/bold]", default="litros")
    notes = Prompt.ask("[bold]Notas[/bold] (opcional)", default="")
    
    # Confirmar
    if not Confirm.ask("\n[bold]Confirmar criação de registo?[/bold]", default=True):
        console.print("[yellow]⊘ Cancelado[/yellow]")
        return None
    
    # Construir payload
    payload = {
        "record_id": record_id,
        "record_type": record_type,
        "manifest_id": manifest_id,
        "quantity": quantity,
        "unit": unit,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "notes": notes,
    }
    
    # Assinar
    console.print("\n[dim]Calculando hash SHA-256...[/dim]")
    
    payload_hash = sha256_hex(payload)
    console.print(f"[yellow]PAYLOAD HASH: {payload_hash}[/yellow]")
    
    signature = sign_hash(private_key[2:], payload_hash)
    console.print(f"[yellow]SIGNATURE: {signature}[/yellow]")
    
    body = {
        "payload": payload,
        "auth": {
            "public_key": public_key,
            "signature": signature
        }
    }
    
    # Enviar
    console.print(f"\n[dim]Enviando para {base_url}/records...[/dim]")
    result = post_json(f"{base_url}/records", body)
    
    if result:
        console.print("[green]✓ registo criado com sucesso![/green]")
        return record_id
    else:
        console.print("[red]✗ Erro ao criar registo[/red]")
    
    return None


def create_record_interactive_for_role(
    base_url: str,
    private_key: str,
    public_key: str,
    role: str,
    last_manifest_id: str | None = None,
) -> str | None:
    """Criar registo filtrando os tipos permitidos pelo papel do usuário."""
    allowed_types = ROLE_TO_RECORD_TYPES.get(role, [])
    if not allowed_types:
        console.print(f"[red]✗ Papel sem permissões configuradas: {role}[/red]")
        return None

    console.print("\n[bold cyan]📝 Criar Novo registo de Operação[/bold cyan]")
    console.print(f"[dim]Papel atual: {role}[/dim]")

    record_id = Prompt.ask("[bold]ID do registo[/bold]", default=f"record-{datetime.now().strftime('%Y%m%d%H%M%S')}")

    type_label = {
        "PRODUCED": "Produção",
        "TRANSFER": "Transferência",
        "RECEIVED": "Recebimento",
        "DELIVERY": "Entrega",
    }
    choice_map: dict[str, str] = {}

    console.print("\n[bold]Tipo de Operação Permitido:[/bold]")
    for idx, record_type in enumerate(allowed_types, start=1):
        key = str(idx)
        choice_map[key] = record_type
        console.print(f"  [cyan]{key}[/cyan] - {record_type} ({type_label.get(record_type, record_type)})")

    if len(allowed_types) == 1:
        record_type = allowed_types[0]
        console.print(f"[dim]Selecionado automaticamente: {record_type}[/dim]")
    else:
        selected = Prompt.ask("Escolha", choices=list(choice_map.keys()), default="1")
        record_type = choice_map[selected]

    if last_manifest_id:
        console.print(f"[dim]Último ID: {last_manifest_id}[/dim]")
    manifest_id = Prompt.ask("[bold]ID do Manifesto[/bold]", default=last_manifest_id or "")

    if not manifest_id:
        console.print("[red]✗ Erro: ID do manifesto é obrigatório[/red]")
        return None

    quantity = float(Prompt.ask("[bold]Quantidade[/bold]", default="50"))
    unit = Prompt.ask("[bold]Unidade[/bold]", default="litros")
    notes = Prompt.ask("[bold]Notas[/bold] (opcional)", default="")

    if not Confirm.ask("\n[bold]Confirmar criação de registo?[/bold]", default=True):
        console.print("[yellow]⊘ Cancelado[/yellow]")
        return None

    payload = {
        "record_id": record_id,
        "record_type": record_type,
        "manifest_id": manifest_id,
        "quantity": quantity,
        "unit": unit,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "notes": notes,
    }

    console.print("\n[dim]Calculando hash SHA-256...[/dim]")
    payload_hash = sha256_hex(payload)
    console.print(f"[yellow]PAYLOAD HASH: {payload_hash}[/yellow]")

    signature = sign_hash(private_key[2:], payload_hash)
    console.print(f"[yellow]SIGNATURE: {signature}[/yellow]")

    body = {
        "payload": payload,
        "auth": {
            "public_key": public_key,
            "signature": signature,
        },
    }

    console.print(f"\n[dim]Enviando para {base_url}/records...[/dim]")
    result = post_json(f"{base_url}/records", body)

    if result:
        console.print("[green]✓ registo criado com sucesso![/green]")
        return record_id

    console.print("[red]✗ Erro ao criar registo[/red]")
    return None

def verify_data(base_url: str, private_key: str, public_key: str):
    """Verificar payload contra o backend."""
    console.print("\n[bold cyan]🔍 Verificar Dados (Independente)[/bold cyan]")
    # Seleção: 'm' -> manifests, 'r' -> records
    endpoint_choice = Prompt.ask("O que deseja verificar? Manifestos (m) ou Registos (r)", choices=["m", "r"], default="r")
    endpoint_map = {"m": "manifests", "r": "records"}
    endpoint_path = endpoint_map.get(endpoint_choice.lower())
    item_label = "Manifesto" if endpoint_choice.lower() == "m" else "Registo"

    item_id = Prompt.ask(f"ID de {item_label}")

    try:
        req = urlrequest.Request(url=f"{base_url}/{endpoint_path}/{item_id}", method="GET")
        with urlrequest.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if "error" in data:
            console.print(f"[red]✗ Erro: {data['error']}[/red]")
            return

        # API returns a wrapper with 'payload', 'payload_hash' and 'anchor'
        returned_payload = data.get("payload") or data

        # Compute expected hash from the payload object
        expected_hash = sha256_hex(returned_payload)
        sig = sign_hash(private_key[2:], expected_hash)

        tx_hash = None
        if isinstance(data.get("anchor"), dict):
            tx_hash = data["anchor"].get("tx_hash")
        else:
            tx_hash = data.get("tx_hash")

        body = {
            "payload": returned_payload,
            "expected_hash": expected_hash,
            "public_key": public_key,
            "signature": sig,
            "tx_hash": tx_hash,
        }

        console.print("\n[dim]Enviando para /verify...[/dim]")
        result = post_json(f"{base_url}/verify", body)

        if result:
            console.print(Panel(json.dumps(result, indent=2), title="[bold green]Resultado da Verificação[/bold green]", border_style="green"))

    except Exception as e:
        console.print(f"[red]✗ Erro ao verificar: {e}[/red]")


def simulate_attack(base_url: str):
    """Simular um ataque alterando dados na DB."""
    console.print("\n[bold red]⚠️ Simular Ataque (Alteração de Dados)[/bold red]")
    
    endpoint_choice = Prompt.ask("O que deseja alterar? Manifestos (m) ou Registos (r)", choices=["m", "r"], default="r")
    endpoint_map = {"m": "manifests", "r": "records"}
    endpoint = endpoint_map[endpoint_choice]
    item_label = "Manifesto" if endpoint_choice == "m" else "Registo"

    item_id = Prompt.ask(f"ID de {item_label} a ser alterado")
    new_quantity = Prompt.ask("Nova Quantidade Falsa")
    
    try:
        new_quantity_float = float(new_quantity)
        body = {"new_quantity": new_quantity_float}
        
        req = urlrequest.Request(url=f"{base_url}/{endpoint}/{item_id}/tamper", method="PUT", data=json.dumps(body).encode("utf-8"))
        req.add_header("Content-Type", "application/json")
        with urlrequest.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            
        console.print(f"[bold red]✓ {data.get('message', 'Alterado com sucesso')}[/bold red]")
        console.print("[dim]Agora use a opção 'Verificar Dados' para ver o sistema rejeitar a integridade![/dim]")
        
    except Exception as e:
        console.print(f"[red]✗ Erro ao simular ataque: {e}[/red]")


def show_menu(base_url: str, current_user_id: str, last_manifest_id: str | None = None) -> None:
    """Mostrar menu principal interativo."""
    user = USERS[current_user_id]
    role = user["role"]
    private_key = user["priv"]
    public_key = f"0x{get_public_key_from_private(private_key[2:])}"
    
    show_header(user)
    
    console.print("\n[bold]O que deseja fazer?[/bold]\n")

    options: dict[str, tuple[str, str]] = {}
    next_option = 1

    if role == "PRODUCER":
        options[str(next_option)] = ("create_manifest", "Criar Manifesto (novo lote)")
        next_option += 1

    if role in {"TRANSPORTER", "RECEIVER"}:
        options[str(next_option)] = ("create_record", "Criar registo (operação do seu papel)")
        next_option += 1

    options[str(next_option)] = ("verify", "Verificar Dados (Integridade)")
    next_option += 1
    options[str(next_option)] = ("switch_user", "Trocar Usuário")
    next_option += 1
    options[str(next_option)] = ("attack", "[red]Simular Ataque[/red] (Alterar DB)")
    next_option += 1
    options[str(next_option)] = ("exit", "Sair")

    for key, (_, label) in options.items():
        console.print(f"  [cyan]{key}[/cyan] - {label}")
    
    if last_manifest_id:
        console.print(f"\n[dim]Último manifesto: {last_manifest_id}[/dim]")
    
    choice = Prompt.ask("\nEscolha", choices=list(options.keys()), default="1")
    action = options[choice][0]

    if action == "create_manifest":
        manifest_id, _ = create_manifest_interactive(base_url, private_key, public_key)
        if manifest_id:
            last_manifest_id = manifest_id
    elif action == "create_record":
        _ = create_record_interactive_for_role(base_url, private_key, public_key, role, last_manifest_id)
    elif action == "verify":
        verify_data(base_url, private_key, public_key)
    elif action == "switch_user":
        console.print("\n[bold]Selecione o Usuário:[/bold]")
        for k, v in USERS.items():
            console.print(f"  [cyan]{k}[/cyan] - {v['name']}")
        new_user = Prompt.ask("Escolha", choices=list(USERS.keys()), default="1")
        show_menu(base_url, new_user, last_manifest_id)
        return
    elif action == "attack":
        simulate_attack(base_url)
    elif action == "exit":
        console.print("[yellow]Até logo! 👋[/yellow]")
        sys.exit(0)
    
    # Voltar ao menu
    input("\n[dim]Pressione Enter para continuar...[/dim]")
    show_menu(base_url, current_user_id, last_manifest_id)


def main():
    """Ponto de entrada da aplicação."""
    base_url = "http://127.0.0.1:8000"
    
    console.print("\n[bold cyan]Selecione o Usuário Inicial:[/bold cyan]")
    for k, v in USERS.items():
        console.print(f"  [cyan]{k}[/cyan] - {v['name']}")
        
    user_id = Prompt.ask("Escolha", choices=list(USERS.keys()), default="1")
    
    try:
        show_menu(base_url, user_id)
    except KeyboardInterrupt:
        console.print("\n[yellow]Aplicação encerrada pelo utilizador[/yellow]")
        sys.exit(0)


if __name__ == "__main__":
    main()
