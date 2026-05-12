"""CLI interativa para assinatura de manifestos/registros e testagem de blockchain."""

from __future__ import annotations

import json
import sys
import logging
from datetime import datetime, timezone
from urllib import request as urlrequest
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from app.core.hashing import sha256_hex
from app.core.security import sign_hash, get_public_key_from_private, address_from_public_key
from app.core.settings import settings
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
# Carregar .env no início da aplicação

def load_keys() -> tuple[str, str]:
    """Carregar chaves do .env."""
    private_key = settings.private_key_for_deploy.strip()
    
    if not private_key:
        console.print("[red]✗ Erro: PRIVATE_KEY_FOR_DEPLOY não configurada em .env[/red]")
        sys.exit(1)
    
    # Adicionar prefixo 0x se não tiver
    if not private_key.startswith("0x"):
        private_key = f"0x{private_key}"
    
    try:
        public_key = get_public_key_from_private(private_key[2:])  # Remove 0x para processar
        public_key = f"0x{public_key}"
        
        console.print(f"[green]✓ Chaves carregadas do .env[/green]")
        console.print(f"[dim]Chave Privada: {private_key[:10]}...{private_key[-4:]}[/dim]")
        console.print(f"[dim]Chave Pública: {public_key[:10]}...{public_key[-4:]}[/dim]\n")
        
        return private_key, public_key
    except Exception as e:
        console.print(f"[red]✗ Erro ao carregar chaves:[/red] {e}")
        sys.exit(1)


def post_json(url: str, payload: dict) -> dict:
    """Enviar carga JSON para API e analisar resposta JSON."""
    try:
        req = urlrequest.Request(url=url, method="POST", data=json.dumps(payload).encode("utf-8"))
        req.add_header("Content-Type", "application/json")
        with urlrequest.urlopen(req) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        console.print(f"[red]✗ Erro na requisição:[/red] {e}")
        return {}


def show_header():
    """Mostrar cabeçalho da aplicação."""
    console.clear()
    console.print(Panel(
        "[bold cyan]🍺 Rastreador de Cerveja Artesanal[/bold cyan]\n"
        "[dim]Sistema de Blockchain para Supply Chain[/dim]",
        title="[bold]Blockchain CLI[/bold]",
        border_style="cyan"
    ))


def create_manifest_interactive(base_url: str, private_key: str, public_key: str) -> None:
    """Criar manifesto de forma interativa."""
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
    
    # Derivar creator a partir da chave pública
    creator = address_from_public_key(public_key)
    console.print(f"[dim]Chave Pública: {public_key[:20]}...{public_key[-4:]}[/dim]")
    console.print(f"[dim]Criador derivado: {creator}[/dim]\n")
    
    # Confirmar
    if not Confirm.ask("\n[bold]Confirmar criação de manifesto?[/bold]", default=True):
        console.print("[yellow]⊘ Cancelado[/yellow]")
        return
    
    # Construir payload com creator já derivado
    payload = {
        "manifest_id": manifest_id,
        "good_type": good_type,
        "quantity": quantity,
        "unit": unit,
        "ingredients": ingredients,
        "origin": origin,
        "sustainability": sustainability,
        "creator": creator,  # Preenchido aqui, não na API
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    # Assinar
    console.print("\n[dim]Calculando hash SHA-256...[/dim]")
    console.print(f"[dim]Hashando payload...[/dim]")
    console.print(f"[yellow]PAYLOAD: {payload}[/yellow]")
    
    # Log do JSON canônico
    canonical = canonical_json(payload)
    console.print(f"[yellow]CANONICAL JSON:\n{canonical}[/yellow]")
    
    payload_hash = sha256_hex(payload)  # payload é dict, não precisa .model_dump()
    console.print(f"[yellow]PAYLOAD HASH: {payload_hash}[/yellow]")
    
    console.print(f"[dim]Hash: {payload_hash[:32]}...[/dim]")
    console.print("[dim]Assinando com ECDSA...[/dim]")
    signature = sign_hash(private_key[2:], payload_hash)  # Remove 0x para processar
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
    
    console.print(f"\n[dim]Logs guardados em: /tmp/blockchain_cli_debug.log[/dim]")
    
    if result:
        console.print("[green]✓ Manifesto criado com sucesso![/green]")
        console.print(Panel(json.dumps(result, indent=2), title="[bold green]Resposta[/bold green]", border_style="green"))
    else:
        console.print("[red]✗ Erro ao criar manifesto[/red]")


def create_record_interactive(base_url: str, private_key: str, public_key: str) -> None:
    """Criar registro de operação de forma interativa."""
    console.print("\n[bold cyan]📝 Criar Novo Registro de Operação[/bold cyan]")
    console.print("[dim]Registre uma transformação no lote[/dim]\n")
    
    record_id = Prompt.ask("[bold]ID do Registro[/bold]", default=f"record-{datetime.now().strftime('%Y%m%d%H%M%S')}")
    
    # Escolher tipo
    console.print("\n[bold]Tipo de Operação:[/bold]")
    console.print("  [cyan]1[/cyan] - PRODUCED (Produção)")
    console.print("  [cyan]2[/cyan] - TRANSFER (Transferência)")
    console.print("  [cyan]3[/cyan] - RECEIVED (Recebimento)")
    console.print("  [cyan]4[/cyan] - DELIVERY (Entrega)")
    
    type_choice = Prompt.ask("Escolha", choices=["1", "2", "3", "4"], default="1")
    type_map = {"1": "PRODUCED", "2": "TRANSFER", "3": "RECEIVED", "4": "DELIVERY"}
    record_type = type_map[type_choice]
    
    manifest_id = Prompt.ask("[bold]ID do Manifesto[/bold]")
    quantity = float(Prompt.ask("[bold]Quantidade[/bold]", default="50"))
    unit = Prompt.ask("[bold]Unidade[/bold]", default="litros")
    # Derivar user a partir da chave pública (como criador no manifesto)
    user = address_from_public_key(public_key)
    console.print(f"[dim]Utilizador derivado: {user}[/dim]")
    notes = Prompt.ask("[bold]Notas[/bold] (opcional)", default="")
    
    # Confirmar
    if not Confirm.ask("\n[bold]Confirmar criação de registro?[/bold]", default=True):
        console.print("[yellow]⊘ Cancelado[/yellow]")
        return
    
    # Construir payload
    payload = {
        "record_id": record_id,
        "record_type": record_type,
        "manifest_id": manifest_id,
        "quantity": quantity,
        "unit": unit,
        "user": user,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "notes": notes,
    }
    
    # Assinar
    console.print("\n[dim]Calculando hash SHA-256...[/dim]")
    console.print(f"[yellow]PAYLOAD (RECORD): {payload}[/yellow]")
    
    # Log do JSON canônico
    canonical = canonical_json(payload)
    console.print(f"[yellow]CANONICAL JSON:\n{canonical}[/yellow]")
    
    payload_hash = sha256_hex(payload)
    console.print(f"[yellow]PAYLOAD HASH: {payload_hash}[/yellow]")
    
    console.print(f"[dim]Hash: {payload_hash[:32]}...[/dim]")
    console.print("[dim]Assinando com ECDSA...[/dim]")
    signature = sign_hash(private_key[2:], payload_hash)  # Remove 0x para processar
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
    
    console.print(f"\n[dim]Logs guardados em: /tmp/blockchain_cli_debug.log[/dim]")
    
    if result:
        console.print("[green]✓ Registro criado com sucesso![/green]")
        console.print(Panel(json.dumps(result, indent=2), title="[bold green]Resposta[/bold green]", border_style="green"))
    else:
        console.print("[red]✗ Erro ao criar registro[/red]")


def show_info() -> None:
    """Mostrar informações sobre a aplicação."""
    console.print("\n[bold cyan]ℹ️ Informações do Sistema[/bold cyan]\n")
    
    info_table = Table(title="Blockchain CLI", show_header=True, header_style="bold cyan")
    info_table.add_column("Item", style="cyan")
    info_table.add_column("Descrição", style="white")
    
    info_table.add_row("Aplicação", "Rastreador de Cerveja Artesanal")
    info_table.add_row("Blockchain", "Ethereum Sepolia Testnet")
    info_table.add_row("Protocolo", "ECDSA + SHA-256")
    info_table.add_row("Armazenamento", "SQLite + Blockchain")
    info_table.add_row("API", "FastAPI em http://127.0.0.1:8000")
    
    console.print(info_table)
    
    console.print("\n[bold yellow]⚠️ Segurança:[/bold yellow]")
    console.print("  • Nunca partilhe sua chave privada")
    console.print("  • Use uma chave privada diferente para cada operação")
    console.print("  • Mantenha o .env seguro (nunca em Git)")

def show_menu(base_url: str, private_key: str, public_key: str) -> None:
    """Mostrar menu principal interativo."""
    show_header()
    
    console.print("\n[bold]O que deseja fazer?[/bold]\n")
    console.print("  [cyan]1[/cyan] - Criar Manifesto (novo lote)")
    console.print("  [cyan]2[/cyan] - Criar Registro (operação)")
    console.print("  [cyan]3[/cyan] - Informações do Sistema")
    console.print("  [cyan]4[/cyan] - Sair")
    
    choice = Prompt.ask("\nEscolha", choices=["1", "2", "3", "4"], default="1")
    
    if choice == "1":
        create_manifest_interactive(base_url, private_key, public_key)
    elif choice == "2":
        create_record_interactive(base_url, private_key, public_key)
    elif choice == "3":
        show_info()
    elif choice == "4":
        console.print("[yellow]Até logo! 👋[/yellow]")
        sys.exit(0)
    
    # Voltar ao menu
    input("\n[dim]Pressione Enter para continuar...[/dim]")
    show_menu(base_url, private_key, public_key)


def main():
    """Ponto de entrada da aplicação."""
    # Carregar chaves do .env
    private_key, public_key = load_keys()
    
    base_url = Prompt.ask(
        "[bold]URL da API[/bold]",
        default="http://127.0.0.1:8000"
    )
    
    try:
        show_menu(base_url, private_key, public_key)
    except KeyboardInterrupt:
        console.print("\n[yellow]Aplicação encerrada pelo utilizador[/yellow]")
        sys.exit(0)


if __name__ == "__main__":
    main()
