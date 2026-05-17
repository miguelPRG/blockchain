"""CLI interativa para assinatura de manifestos/registos e testagem de blockchain com múltiplos utilizadores."""

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
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # dotenv is optional; if not installed, environment variables must be set externally
    pass

# Adicionar PYTHONPATH para importar do app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from app.core.hashing import sha256_hex
from app.core.security import sign_hash, get_public_key_from_private, address_from_public_key


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


# ============================================================
# Utilizadores de teste (carregam chaves privadas a partir do ambiente)
# ============================================================
# Se estiver a usar um ficheiro .env, instale e use `python-dotenv` ou exporte
# as variáveis `PRIVATE_KEY_1`, `PRIVATE_KEY_2`, `PRIVATE_KEY_3` no seu ambiente.

def _env_priv(key: str, default: str) -> str:
    """Lê uma chave privada do ambiente; garante prefixo 0x se necessário."""
    v = os.getenv(key)
    if v:
        return v if v.startswith("0x") else f"0x{v}"
    return default

USERS = {
    "1": {
        "name": "Alice (Producer)",
        "role": "PRODUCER",
        "priv": _env_priv(
            "ALICE_KEY",
            "0x00000000000000000000000000000000000000000000000000000000"
        ),
    },
    "2": {
        "name": "Bob (Transporter)",
        "role": "TRANSPORTER",
        "priv": _env_priv(
            "BOB_KEY",
            "0x11111111111111111111111111111111111111111111111111111111"
        ),
    },
    "3": {
        "name": "Charlie (Receiver)",
        "role": "RECEIVER",
        "priv": _env_priv(
            "CHARLIE_KEY",
            "0x22222222222222222222222222222222222222222222222222222222"
        ),
    },
}


ROLE_TO_RECORD_TYPES = {
    "PRODUCER": ["PRODUCED"],
    "TRANSPORTER": ["TRANSFER", "DELIVERY"],
    "RECEIVER": ["RECEIVED"],
}


RECORD_TYPE_LABELS = {
    "PRODUCED": "Produção",
    "TRANSFER": "Transferência",
    "RECEIVED": "Receção",
    "DELIVERY": "Entrega",
}


# ============================================================
# Funções auxiliares
# ============================================================

def strip_0x(value: str) -> str:
    """Remove o prefixo 0x caso exista."""
    return value[2:] if value.startswith("0x") else value


def get_public_key(private_key: str) -> str:
    """Obtém a chave pública a partir da chave privada."""
    return f"0x{get_public_key_from_private(strip_0x(private_key))}"


def get_address(public_key: str) -> str:
    """Obtém o endereço do utilizador a partir da chave pública."""
    return address_from_public_key(public_key)


def post_json(url: str, payload: dict) -> dict:
    """Envia uma carga JSON para a API e devolve a resposta JSON."""
    try:
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
        public_key = get_public_key(private_key)
        address = get_address(public_key)

        console.print(f"[bold green]👤 Utilizador Ativo:[/bold green] {current_user['name']}")
        console.print(f"[dim]Papel: {current_user['role']}[/dim]")
        console.print(f"[dim]Endereço: {address}[/dim]\n")


def select_user(default: str = "1") -> str:
    """Permite selecionar um utilizador."""
    console.print("\n[bold cyan]Selecione o Utilizador:[/bold cyan]")

    for key, user in USERS.items():
        console.print(f"  [cyan]{key}[/cyan] - {user['name']}")

    choice = Prompt.ask("Escolha", choices=list(USERS.keys()), default=default)

    # Mostrar endereço do utilizador escolhido imediatamente
    chosen = USERS.get(choice)
    if chosen:
        priv = chosen.get("priv")
        try:
            pub = get_public_key(priv)
            addr = get_address(pub)
            console.print(f"\n[dim]Endereço selecionado:[/dim] {addr}\n")
        except Exception:
            # Fallback: não bloquear se houver erro a derivar chave
            pass

    return choice


# ============================================================
# Manifestos
# ============================================================

def create_manifest_interactive(
    base_url: str,
    private_key: str,
    public_key: str,
) -> tuple[str | None, str | None]:
    """
    Cria um manifesto de forma interativa.

    Como a criação do manifesto representa o nascimento do lote,
    o sistema pode também criar um registo PRODUCED opcionalmente.
    """

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

    creator = get_address(public_key)

    payload = {
        "manifest_id": manifest_id,
        "good_type": good_type,
        "quantity": quantity,
        "unit": unit,
        "ingredients": ingredients,
        "origin": origin,
        "sustainability": sustainability,
        "creator": creator,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    console.print("\n[dim]Calculando hash SHA-256 do manifesto...[/dim]")

    payload_hash = sha256_hex(payload)
    signature = sign_hash(strip_0x(private_key), payload_hash)

    console.print(f"[yellow]PAYLOAD HASH:[/yellow] {payload_hash}")
    console.print(f"[yellow]SIGNATURE:[/yellow] {signature}")

    body = {
        "payload": payload,
        "auth": {
            "public_key": public_key,
            "signature": signature,
            "role": "PRODUCER",
        },
    }

    console.print(f"\n[dim]Enviando para {base_url}/manifests...[/dim]")
    result = post_json(f"{base_url}/manifests", body)

    if not result:
        console.print("[red]✗ Erro ao criar manifesto[/red]")
        return None, None

    console.print("[green]✓ Manifesto criado com sucesso![/green]")

    if Confirm.ask(
        "[bold]Criar também o registo PRODUCED automaticamente?[/bold]",
        default=False,
    ):
        produced_result = create_produced_record_automatically(
            base_url=base_url,
            private_key=private_key,
            public_key=public_key,
            manifest_id=manifest_id,
            quantity=quantity,
            unit=unit,
        )

        if produced_result:
            console.print("[green]✓ Registo PRODUCED criado automaticamente![/green]")
        else:
            console.print(
                "[yellow]⚠ Manifesto criado, mas falhou a criação automática do registo PRODUCED.[/yellow]"
            )

    return manifest_id, payload_hash


def create_produced_record_automatically(
    base_url: str,
    private_key: str,
    public_key: str,
    manifest_id: str,
    quantity: float,
    unit: str,
) -> str | None:
    """Cria automaticamente o registo PRODUCED associado ao manifesto."""

    user_address = get_address(public_key)

    payload = {
        "record_id": f"produced-{manifest_id}",
        "record_type": "PRODUCED",
        "manifest_id": manifest_id,
        "quantity": quantity,
        "unit": unit,
        "user": user_address,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "notes": "Registo PRODUCED criado automaticamente com o manifesto.",
    }

    payload_hash = sha256_hex(payload)
    signature = sign_hash(strip_0x(private_key), payload_hash)

    body = {
        "payload": payload,
        "auth": {
            "public_key": public_key,
            "signature": signature,
            "role": "PRODUCER",
        },
    }

    console.print("[dim]Criando registo PRODUCED automático...[/dim]")
    result = post_json(f"{base_url}/records", body)

    if result:
        return payload["record_id"]

    return None


# ============================================================
# Registos
# ============================================================

def create_record_interactive_for_role(
    base_url: str,
    private_key: str,
    public_key: str,
    role: str,
    last_manifest_id: str | None = None,
) -> str | None:
    """Cria um registo filtrando os tipos permitidos pelo papel do utilizador."""

    allowed_types = ROLE_TO_RECORD_TYPES.get(role, [])

    if not allowed_types:
        console.print(f"[red]✗ Papel sem permissões configuradas: {role}[/red]")
        return None

    console.print("\n[bold cyan]📝 Criar Novo Registo de Operação[/bold cyan]")
    console.print(f"[dim]Papel atual: {role}[/dim]")

    record_id = Prompt.ask(
        "[bold]ID do Registo[/bold]",
        default=f"record-{datetime.now().strftime('%Y%m%d%H%M%S')}",
    )

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

    if last_manifest_id:
        console.print(f"[dim]Último manifesto usado: {last_manifest_id}[/dim]")

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

    user_address = get_address(public_key)

    payload = {
        "record_id": record_id,
        "record_type": record_type,
        "manifest_id": manifest_id,
        "quantity": quantity,
        "unit": unit,
        "user": user_address,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "notes": notes,
    }

    console.print("\n[dim]Calculando hash SHA-256 do registo...[/dim]")

    payload_hash = sha256_hex(payload)
    signature = sign_hash(strip_0x(private_key), payload_hash)

    console.print(f"[yellow]PAYLOAD HASH:[/yellow] {payload_hash}")
    console.print(f"[yellow]SIGNATURE:[/yellow] {signature}")

    body = {
        "payload": payload,
        "auth": {
            "public_key": public_key,
            "signature": signature,
            "role": role,
        },
    }

    console.print(f"\n[dim]Enviando para {base_url}/records...[/dim]")
    result = post_json(f"{base_url}/records", body)

    if result:
        console.print("[green]✓ Registo criado com sucesso![/green]")
        return record_id

    console.print("[red]✗ Erro ao criar registo[/red]")
    return None


# ============================================================
# Verificação
# ============================================================

def verify_data(base_url: str) -> None:
    """Verifica dados contra o backend, sem inventar assinatura nova."""

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

    endpoint_path = endpoint_map[endpoint_choice]
    item_label = "Manifesto" if endpoint_choice == "m" else "Registo"

    item_id = Prompt.ask(f"ID de {item_label}")

    data = get_json(f"{base_url}/{endpoint_path}/{item_id}")

    if not data:
        console.print("[red]✗ Não foi possível obter os dados para verificação[/red]")
        return

    if "error" in data:
        console.print(f"[red]✗ Erro: {data['error']}[/red]")
        return

    returned_payload = data.get("payload") or data

    signature = (
        data.get("signature")
        or data.get("auth", {}).get("signature")
    )

    stored_public_key = (
        data.get("public_key")
        or data.get("auth", {}).get("public_key")
    )

    tx_hash = (
        data.get("tx_hash")
        or data.get("transaction_hash")
        or data.get("blockchain_tx")
    )

    if not signature:
        console.print("[red]✗ Erro: assinatura ausente nos dados guardados[/red]")
        return

    if not stored_public_key:
        console.print("[red]✗ Erro: chave pública ausente nos dados guardados[/red]")
        return

    expected_hash = sha256_hex(returned_payload)

    body = {
        "payload": returned_payload,
        "expected_hash": expected_hash,
        "public_key": stored_public_key,
        "signature": signature,
        "tx_hash": tx_hash,
        "item_id": item_id,
    }

    console.print("\n[dim]Enviando para /verify...[/dim]")
    result = post_json(f"{base_url}/verify", body)

    if result:
        console.print(
            Panel(
                json.dumps(result, indent=2, ensure_ascii=False),
                title="[bold green]Resultado da Verificação[/bold green]",
                border_style="green",
            )
        )
    else:
        console.print("[red]✗ Falha ao verificar os dados[/red]")


# ============================================================
# Ataque / Tamper
# ============================================================

def simulate_attack(base_url: str) -> None:
    """Simula um ataque alterando dados na base de dados."""

    console.print("\n[bold red]⚠️ Simular Ataque / Alteração de Dados[/bold red]")

    endpoint_choice = Prompt.ask(
        "O que deseja alterar? Manifestos (m) ou Registos (r)",
        choices=["m", "r"],
        default="r",
    )

    endpoint_map = {
        "m": "manifests",
        "r": "records",
    }

    endpoint = endpoint_map[endpoint_choice]
    item_label = "Manifesto" if endpoint_choice == "m" else "Registo"

    item_id = Prompt.ask(f"ID de {item_label} a ser alterado")
    new_quantity = Prompt.ask("Nova quantidade falsa")

    try:
        new_quantity_float = float(new_quantity)

        body = {
            "new_quantity": new_quantity_float,
        }

        req = urlrequest.Request(
            url=f"{base_url}/{endpoint}/{item_id}/tamper",
            method="PUT",
            data=json.dumps(body).encode("utf-8"),
        )
        req.add_header("Content-Type", "application/json")

        with urlrequest.urlopen(req) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))

        console.print(f"[bold red]✓ {data.get('message', 'Alterado com sucesso')}[/bold red]")
        console.print(
            "[dim]Agora usa a opção 'Verificar Dados' para mostrar que a integridade falha.[/dim]"
        )

    except Exception as e:
        console.print(f"[red]✗ Erro ao simular ataque: {e}[/red]")


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

    # O produtor não cria PRODUCED manualmente porque isso já acontece
    # automaticamente ao criar o manifesto.
    if role in ROLE_TO_RECORD_TYPES and role != "PRODUCER":
        options[str(next_option)] = (
            "create_record",
            "Criar registo da sua função",
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


def run_app(base_url: str, initial_user_id: str) -> None:
    """Executa a aplicação CLI."""

    current_user_id = initial_user_id
    last_manifest_id: str | None = None

    while True:
        user = USERS[current_user_id]
        role = user["role"]
        private_key = user["priv"]
        public_key = get_public_key(private_key)

        show_header(user)

        console.print("\n[bold]O que deseja fazer?[/bold]\n")

        options = build_menu_options(role)

        for key, (_, label) in options.items():
            console.print(f"  [cyan]{key}[/cyan] - {label}")

        if last_manifest_id:
            console.print(f"\n[dim]Último manifesto: {last_manifest_id}[/dim]")

        choice = Prompt.ask("\nEscolha", choices=list(options.keys()), default="1")
        action = options[choice][0]

        if action == "create_manifest":
            manifest_id, _ = create_manifest_interactive(
                base_url=base_url,
                private_key=private_key,
                public_key=public_key,
            )

            if manifest_id:
                last_manifest_id = manifest_id

        elif action == "create_record":
            create_record_interactive_for_role(
                base_url=base_url,
                private_key=private_key,
                public_key=public_key,
                role=role,
                last_manifest_id=last_manifest_id,
            )

        elif action == "verify":
            verify_data(base_url)

        elif action == "switch_user":
            current_user_id = select_user(default=current_user_id)
            continue

        elif action == "attack":
            simulate_attack(base_url)

        elif action == "exit":
            console.print("[yellow]Até logo! 👋[/yellow]")
            sys.exit(0)

        input("\n[dim]Pressione Enter para continuar...[/dim]")


def main() -> None:
    """Ponto de entrada da aplicação."""

    base_url = "http://127.0.0.1:8000"

    user_id = select_user(default="1")

    try:
        run_app(base_url, user_id)
    except KeyboardInterrupt:
        console.print("\n[yellow]Aplicação encerrada pelo utilizador[/yellow]")
        sys.exit(0)


if __name__ == "__main__":
    main()