"""CLI interativa para assinatura de manifestos/registos e testagem de blockchain com múltiplos utilizadores."""

from __future__ import annotations

import json
import sys
import logging
import os
from pathlib import Path
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

# Adicionar PYTHONPATH para importar da raiz
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Importações de funções criptográficas compartilhadas
from shared.hashing import sha256_hex
from shared.security import sign_hash, get_public_key_from_private, address_from_private_key


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

# URL da API FastAPI
BASE_URL = "http://127.0.0.1:8000"
SUPPLY_MANAGER_ADDRESS = "0x9D77a7336C19eE8975Eb6267c2aF384B90C73455"


# ============================================================
# Funções de Inicialização - Verificar e Autenticar Contrato
# ============================================================

def deploy_contract_via_api() -> str | None:
    """
    Fazer deployment de um novo contrato via API.
    
    Requer que o Supply Manager tenha sido autenticado.
    
    Returns:
        Endereço do contrato, ou None se falhou
    """
    try:
        req = urlrequest.Request(
            url=f"{BASE_URL}/config/deploy-contract",
            method="POST",
            data=b"{}",
        )
        req.add_header("Content-Type", "application/json")
        
        with urlrequest.urlopen(req) as resp:  # noqa: S310
            result = json.loads(resp.read().decode("utf-8"))
            
            if result.get("success"):
                contract_addr = result.get("contract_address")
                console.print(f"[bold green]✓ Contrato deployado:[/bold green] {contract_addr}")
                console.print(f"[dim]Explorer: {result.get('explorer_url')}[/dim]")
                return contract_addr
            else:
                console.print(f"[red]✗ Falha no deployment[/red]")
                return None
    
    except urlrequest.HTTPError as e:
        try:
            error_detail = json.loads(e.read().decode("utf-8"))
            console.print(f"[red]✗ Erro:[/red] {error_detail.get('detail', str(error_detail))}")
        except Exception:
            console.print(f"[red]✗ Erro HTTP {e.code}:[/red] {e.reason}")
        return None
    
    except Exception as e:
        console.print(f"[red]✗ Erro ao fazer deployment:[/red] {e}")
        return None


def validate_contract_via_api(contract_address: str) -> bool:
    """
    Validar se um contrato existe e está deployado na blockchain.
    
    Args:
        contract_address: Endereço do contrato a validar
    
    Returns:
        True se contrato é válido, False caso contrário
    """
    try:
        payload = {"contract_address": contract_address}
        req = urlrequest.Request(
            url=f"{BASE_URL}/config/validate-contract",
            method="POST",
            data=json.dumps(payload).encode("utf-8"),
        )
        req.add_header("Content-Type", "application/json")
        
        with urlrequest.urlopen(req) as resp:  # noqa: S310
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("success"):
                console.print(f"[bold green]✓ Contrato Validado:[/bold green] {contract_address}")
                console.print(f"[dim]Explorer: {result.get('explorer_url')}[/dim]")
                return True
            else:
                console.print(f"[red]✗ Falha na validação[/red]")
                return False
    
    except urlrequest.HTTPError as e:
        try:
            error_detail = json.loads(e.read().decode("utf-8"))
            console.print(f"[red]✗ Erro:[/red] {error_detail.get('detail', str(error_detail))}")
        except Exception:
            console.print(f"[red]✗ Erro HTTP {e.code}:[/red] {e.reason}")
        return False
    
    except Exception as e:
        console.print(f"[red]✗ Erro ao validar:[/red] {e}")
        return False


def read_contract_address_from_env() -> str | None:
    """
    Ler CONTRACT_ADDRESS do ficheiro .env local.
    
    Returns:
        Endereço do contrato, ou None se não existir
    """
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        content = env_file.read_text()
        for line in content.split("\n"):
            if line.startswith("CONTRACT_ADDRESS="):
                addr = line.split("=", 1)[1].strip()
                if addr and addr != "0x0000000000000000000000000000000000000000":
                    return addr
    return None


def save_contract_address_to_env(address: str) -> None:
    """
    Guardar CONTRACT_ADDRESS no ficheiro .env local.
    
    Args:
        address: Endereço do contrato
    """
    env_file = Path(__file__).parent / ".env"
    
    if env_file.exists():
        content = env_file.read_text()
        lines = content.split("\n")
        
        found = False
        for i, line in enumerate(lines):
            if line.startswith("CONTRACT_ADDRESS="):
                lines[i] = f"CONTRACT_ADDRESS={address}"
                found = True
                break
        
        if not found:
            lines.append(f"CONTRACT_ADDRESS={address}")
        
        env_file.write_text("\n".join(lines))
    else:
        # Criar novo .env
        env_file.write_text(f"CONTRACT_ADDRESS={address}\n")


def authenticate_manager_with_api(private_key: str) -> bool:
    """
    Autenticar o Supply Manager via API.
    Faz POST a /config/authenticate-manager
    
    Args:
        private_key: Chave privada do Supply Manager
    
    Returns:
        True se autenticação foi bem-sucedida, False caso contrário
    """
    try:
        payload = {"private_key": private_key}
        req = urlrequest.Request(
            url=f"{BASE_URL}/config/authenticate-manager",
            method="POST",
            data=json.dumps(payload).encode("utf-8"),
        )
        req.add_header("Content-Type", "application/json")
        
        with urlrequest.urlopen(req) as resp:  # noqa: S310
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("success"):
                console.print(f"[bold green]✓ {result.get('message')}[/bold green]")
                console.print(f"[dim]Endereço: {result.get('manager_address')}[/dim]")
                return True
            else:
                console.print(f"[red]✗ Falha na autenticação[/red]")
                return False
    
    except urlrequest.HTTPError as e:
        try:
            error_detail = json.loads(e.read().decode("utf-8"))
            console.print(f"[red]✗ Erro:[/red] {error_detail.get('detail', str(error_detail))}")
        except Exception:
            console.print(f"[red]✗ Erro HTTP {e.code}:[/red] {e.reason}")
        return False
    
    except Exception as e:
        console.print(f"[red]✗ Erro ao autenticar:[/red] {e}")
        return False


def initialize_blockchain_setup() -> bool:
    """
    Fluxo completo de inicialização:
    1. Pedir chave privada do Supply Manager e validar
    2. Autenticar no backend
    3. Verificar se existe CONTRACT_ADDRESS no .env local
       - Se existe: validar no backend
       - Se não existe: fazer deployment de novo contrato
    4. Guardar endereço do contrato no .env local
    
    Returns:
        True se sucesso, False se falhou
    """
    console.print("\n[bold cyan]🔐 Autenticação do Supply Manager[/bold cyan]")
    console.print(f"[dim]Endereço esperado: {SUPPLY_MANAGER_ADDRESS}[/dim]\n")
    
    # ========== PASSO 1: PEDIR E VALIDAR CHAVE PRIVADA ==========
    max_attempts = 3
    private_key = None
    
    for attempt in range(max_attempts):
        private_key_input = Prompt.ask(
            "[bold]Introduza a chave privada do Supply Manager[/bold]",
            password=True
        )
        
        if not private_key_input:
            console.print("[red]✗ Chave privada não pode estar vazia[/red]")
            continue
        
        # Garantir prefixo 0x
        if not private_key_input.startswith("0x"):
            private_key_input = f"0x{private_key_input}"
        
        # Validar localmente se a chave gera o endereço correto
        try:
            derived_address = address_from_private_key(private_key_input)
            if derived_address.lower() != SUPPLY_MANAGER_ADDRESS.lower():
                console.print(f"[red]✗ Endereço inválido[/red]")
                console.print(f"[dim]Esperado: {SUPPLY_MANAGER_ADDRESS}[/dim]")
                console.print(f"[dim]Obtido: {derived_address}[/dim]\n")
                remaining = max_attempts - attempt - 1
                if remaining > 0:
                    console.print(f"[yellow]Tentativas restantes: {remaining}[/yellow]\n")
                continue
            
            private_key = private_key_input
            console.print(f"[bold green]✓ Chave validada localmente[/bold green]\n")
            break
        
        except Exception as e:
            console.print(f"[red]✗ Erro ao validar chave:[/red] {e}\n")
            continue
    
    if not private_key:
        console.print("[red]✗ Falha na validação da chave privada[/red]")
        return False
    
    # ========== PASSO 2: AUTENTICAR NO BACKEND ==========
    console.print("[bold cyan]🔗 Autenticando no backend...[/bold cyan]\n")
    if not authenticate_manager_with_api(private_key):
        console.print("[red]✗ Falha na autenticação no backend[/red]")
        return False
    
    console.print("[bold green]✓ Supply Manager autenticado[/bold green]\n")
    
    # ========== PASSO 3: VERIFICAR/CRIAR CONTRATO ==========
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
                console.print("[bold cyan]📦 Fazendo Deployment do Contrato...[/bold cyan]\n")
                new_contract = deploy_contract_via_api()
                
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
        
        new_contract = deploy_contract_via_api()
        
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
        "expected_address": "0x7Ac8041347b40a6F1ee3e9e9f82C1370afdbea50",
        "priv": None,  # Será preenchido quando o utilizador fornecer a chave
        "public_key": None,  # Será derivado da chave privada
    },
    "2": {
        "name": "Bob (Transporter)",
        "id": "bob",
        "role": "TRANSPORTER",
        "expected_address": "0x69aF73CF609DdA4112d1e9f1FA337281202457F4",
        "priv": None,
        "public_key": None,
    },
    "3": {
        "name": "Charlie (Receiver)",
        "id": "charlie",
        "role": "RECEIVER",
        "expected_address": "0x7832aE65a53e5c359992F6B4320736238b8cb4DE",
        "priv": None,
        "public_key": None,
    },
}


ROLE_TO_RECORD_TYPES = {
    "PRODUCER": ["PRODUCED"],
    "TRANSPORTER": ["TRANSFER", "DELIVERY"],
    "RECEIVER": ["DELIVERY"],
}


RECORD_TYPE_LABELS = {
    "PRODUCED": "Produção",
    "TRANSFER": "Transferência",
    "DELIVERY": "Entrega",
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
            derived_address = get_address_from_private_key(private_key)
            
            if derived_address.lower() == expected_address.lower():
                # Guardar a chave privada e derivar a chave pública
                user["priv"] = private_key
                user["public_key"] = get_public_key(private_key)
                
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


# ============================================================
# Funções auxiliares
# ============================================================

def strip_0x(value: str) -> str:
    """Remove o prefixo 0x caso exista."""
    return value[2:] if value.startswith("0x") else value


def get_public_key(private_key: str) -> str:
    """Obtém a chave pública a partir da chave privada."""
    return f"0x{get_public_key_from_private(strip_0x(private_key))}"


def get_address_from_private_key(private_key: str) -> str:
    """Obtém o endereço Ethereum correto a partir da chave privada."""
    return address_from_private_key(private_key)


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
        address = get_address_from_private_key(private_key)

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
    public_key: str,
    signer_id: str,
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

    creator = get_address_from_private_key(private_key)

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
            "signer_id": signer_id,
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
            signer_id=signer_id,
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
    signer_id: str,
) -> str | None:
    """Cria automaticamente o registo PRODUCED associado ao manifesto."""

    user_address = get_address_from_private_key(private_key)

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
            "signer_id": signer_id,
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
    signer_id: str,
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

    user_address = get_address_from_private_key(private_key)

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
            "signer_id": signer_id,
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

    item_id = Prompt.ask(f"ID de {item_label}")

    # Fazer GET que já inclui verificação criptográfica integrada
    data = get_json(f"{BASE_URL}/{endpoint_path}/{item_id}")

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
    
    # LÓGICA SIMPLES: Se hash é igual na blockchain, é VÁLIDO. PRONTO.
    hash_match = payload_hash_blockchain == payload_hash_current
    is_valid = hash_match
    
    signature_valid = data.get("verification", {}).get("signature_valid", False)

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

    # ========== RESUMO FINAL ==========
    console.print()
    if is_valid:
        console.print(
            Panel(
                "[bold green]🎉 Dados autenticados e íntegros![/bold green]\n"
                "[dim]Hash confirmado na blockchain - nenhuma alteração detectada.[/dim]",
                border_style="green",
                padding=(1, 2),
            )
        )
    else:
        console.print(
            Panel(
                "[bold red]⚠️  ALERTA: Dados inválidos![/bold red]\n"
                "[dim red]Hash não corresponde ao que está na blockchain - dados foram alterados![/dim red]",
                border_style="red",
                padding=(1, 2),
            )
        )


# ============================================================
# Ataque / Tamper
# ============================================================

def simulate_attack() -> None:
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

    endpoint = endpoint_map[endpoint_choice.lower()]
    item_label = "Manifesto" if endpoint_choice == "m" else "Registo"

    item_id = Prompt.ask(f"ID de {item_label} a ser alterado")
    new_quantity = Prompt.ask("Nova quantidade falsa")

    try:
        new_quantity_float = float(new_quantity)

        body = {
            "new_quantity": new_quantity_float,
        }

        req = urlrequest.Request(
            url=f"{BASE_URL}/{endpoint}/{item_id}/tamper",
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


def run_app(initial_user_id: str | None) -> None:
    """Executa a aplicação CLI."""

    if not initial_user_id:
        console.print("[red]✗ Falha na autenticação inicial[/red]")
        return

    current_user_id = initial_user_id
    last_manifest_id: str | None = None

    while True:
        user = USERS[current_user_id]
        role = user["role"]
        private_key = user["priv"]
        
        if not private_key:
            console.print("[red]✗ Erro: chave privada não autenticada[/red]")
            return
        
        public_key = user["public_key"]

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
                base_url=BASE_URL,
                private_key=private_key,
                public_key=public_key,
                signer_id=user["id"],
            )

            if manifest_id:
                last_manifest_id = manifest_id

        elif action == "create_record":
            create_record_interactive_for_role(
                base_url=BASE_URL,
                private_key=private_key,
                public_key=public_key,
                role=role,
                signer_id=user["id"],
                last_manifest_id=last_manifest_id,
            )

        elif action == "verify":
            verify_data()

        elif action == "switch_user":
            new_user_id = select_user(default=current_user_id)
            if new_user_id:
                current_user_id = new_user_id
            continue

        elif action == "attack":
            simulate_attack()

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