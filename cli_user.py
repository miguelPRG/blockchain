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
from app.core.security import sign_hash, get_public_key_from_private
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


def show_header():
    """Mostrar cabeçalho da aplicação."""
    console.clear()
    console.print(Panel(
        "[bold cyan]🍺 Rastreador de Cerveja Artesanal[/bold cyan]\n"
        "[dim]Sistema de Blockchain para Supply Chain[/dim]",
        title="[bold]Blockchain CLI[/bold]",
        border_style="cyan"
    ))


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
    console.print(f"[yellow]PAYLOAD: {json.dumps(payload, ensure_ascii=False, indent=2)}[/yellow]")
    
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
        return manifest_id, payload_hash
    else:
        console.print("[red]✗ Erro ao criar manifesto[/red]")
        return None, None


def create_record_interactive(base_url: str, private_key: str, public_key: str, last_manifest_id: str | None = None) -> str | None:
    """Criar registro de operação de forma interativa. Retorna record_id."""
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
    
    # Pedir o ID do manifesto
    console.print(f"\n[bold]Manifesto:[/bold]")
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
    if not Confirm.ask("\n[bold]Confirmar criação de registro?[/bold]", default=True):
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
        return record_id
    else:
        console.print("[red]✗ Erro ao criar registro[/red]")
    
    return None


def show_info() -> None:
    """Mostrar informações sobre a aplicação."""
    console.print("\n[bold cyan]ℹ️ Informações do Sistema[/bold cyan]\n")
    
    info_table = Table(title="Blockchain CLI", show_header=True, header_style="bold cyan")
    info_table.add_column("Item", style="cyan")
    info_table.add_column("Descrição", style="white")
    
    info_table.add_row("Aplicação", "Rastreador de Cerveja Artesanal")
    info_table.add_row("Blockchain", "Ethereum Sepolia Testnet")
    info_table.add_row("Protocolo", "ECDSA + SHA-256")
    info_table.add_row("Armazenamento", "Blockchain-Only (Única Fonte de Verdade)")
    info_table.add_row("API", "FastAPI em http://127.0.0.1:8000")
    
    console.print(info_table)
    
    console.print("\n[bold yellow]⚠️ Segurança:[/bold yellow]")
    console.print("  • Nunca partilhe sua chave privada")
    console.print("  • Use uma chave privada diferente para cada operação")
    console.print("  • Mantenha o .env seguro (nunca em Git)")
    
    console.print("\n[bold cyan]🔍 Debugar:[/bold cyan]")
    console.print("  • Recuperar manifesto: [cyan]http://127.0.0.1:8000/manifests/{manifest_id}[/cyan]")
    console.print("  • Recuperar registo: [cyan]http://127.0.0.1:8000/records/{record_id}[/cyan]")
    console.print("  • Configuração: [cyan]http://127.0.0.1:8000/config/contract-address[/cyan]")
    console.print("  • Docs: [cyan]http://127.0.0.1:8000/docs[/cyan]")
    console.print("  • Explorer Sepolia: [cyan]https://sepolia.etherscan.io[/cyan]")

def show_menu(base_url: str, private_key: str, public_key: str, last_manifest_id: str | None = None, last_manifest_hash: str | None = None) -> None:
    """Mostrar menu principal interativo."""
    show_header()
    
    console.print("\n[bold]O que deseja fazer?[/bold]\n")
    console.print("  [cyan]1[/cyan] - Criar Manifesto (novo lote)")
    console.print("  [cyan]2[/cyan] - Criar Registro (operação)")
    console.print("  [cyan]3[/cyan] - Informações do Sistema")
    console.print("  [cyan]4[/cyan] - Sair")
    
    if last_manifest_id:
        console.print(f"\n[dim]Último manifesto: {last_manifest_id}[/dim]")
    
    choice = Prompt.ask("\nEscolha", choices=["1", "2", "3", "4"], default="1")
    
    if choice == "1":
        manifest_id, manifest_hash = create_manifest_interactive(base_url, private_key, public_key)
        if manifest_id:
            last_manifest_id = manifest_id
    elif choice == "2":
        record_id = create_record_interactive(base_url, private_key, public_key, last_manifest_id)
        if record_id:
            last_manifest_id = last_manifest_id  # Manter o ID do manifesto
    elif choice == "3":
        show_info()
    elif choice == "4":
        console.print("[yellow]Até logo! 👋[/yellow]")
        sys.exit(0)
    
    # Voltar ao menu
    input("\n[dim]Pressione Enter para continuar...[/dim]")
    show_menu(base_url, private_key, public_key, last_manifest_id, None)


def main():
    """Ponto de entrada da aplicação."""
    # Carregar chaves do .env
    private_key, public_key = load_keys()
    
    # Servidor de API sempre em localhost
    base_url = "http://127.0.0.1:8000"
    console.print(f"[dim]API: {base_url}[/dim]\n")
    
    try:
        show_menu(base_url, private_key, public_key)
    except KeyboardInterrupt:
        console.print("\n[yellow]Aplicação encerrada pelo utilizador[/yellow]")
        sys.exit(0)


if __name__ == "__main__":
    main()
