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
from client.config import BASE_URL, SUPPLY_MANAGER_ADDRESS
from client.request_signing import create_signed_api_request
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
                console.print("[bold cyan]📦 Fazendo Deployment do Contrato...[/bold cyan]\n")
                new_contract = deploy_contract_locally()
                
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

        new_contract = deploy_contract_locally()
        
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
    "RECEIVER": ["RECEIVED"],
}


RECORD_TYPE_LABELS = {
    "PRODUCED": "Produção",
    "TRANSFER": "Transferência",
    "RECEIVED": "Receção",
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

    if Confirm.ask(
        "[bold]Criar também o registo PRODUCED automaticamente?[/bold]",
        default=False,
    ):
        produced_result = create_produced_record_automatically(
            base_url=base_url,
            private_key=private_key,
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
    manifest_id: str,
    quantity: float,
    unit: str,
) -> str | None:
    """Cria automaticamente o registo PRODUCED associado ao manifesto."""

    manager_private_key = request_and_validate_manager_private_key()
    if not manager_private_key:
        console.print("[red]✗ Registo PRODUCED cancelado: Supply Manager não validado[/red]")
        return None

    payload = {
        "record_id": f"produced-{manifest_id}",
        "record_type": "PRODUCED",
        "manifest_id": manifest_id,
        "quantity": quantity,
        "unit": unit,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "notes": "Registo PRODUCED criado automaticamente com o manifesto.",
    }

    contract_address = read_contract_address_from_env() or Prompt.ask("Contract address (0x...)")
    try:
        body, _ = create_signed_api_request(
            payload=payload,
            user_private_key=private_key,
            manager_private_key=manager_private_key,
            role="PRODUCER",
            contract_address=contract_address,
            item_id=payload["record_id"],
            timestamp_iso=payload["timestamp"],
        )
    except RuntimeError as exc:
        console.print(f"[red]✗ {exc}[/red]")
        return None

    console.print("[dim]Criando registo PRODUCED automático...[/dim]")
    result = post_json(f"{base_url}/records", body)

    if result:
        tx_hash = result.get("tx_hash") or result.get("anchor", {}).get("tx_hash")
        if tx_hash:
            console.print(f"[bold cyan]TXID da transação:[/bold cyan] {tx_hash}")
            console.print(f"[dim]Explorer: https://sepolia.etherscan.io/tx/{tx_hash}[/dim]")
        return payload["record_id"]

    return None


# ============================================================
# Registos
# ============================================================

def create_record_interactive_for_role(
    base_url: str,
    private_key: str,
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

    manager_private_key = request_and_validate_manager_private_key()
    if not manager_private_key:
        console.print("[red]✗ Criação cancelada: Supply Manager não validado[/red]")
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
        console.print(
            Panel(
                f"[bold cyan]{tx_hash}[/bold cyan]\n\n"
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
            record_id = create_record_interactive_for_role(
                base_url=BASE_URL,
                private_key=private_key,
                role=role,
                last_manifest_id=last_manifest_id,
            )
            if record_id:
                last_record_id = record_id

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
