#!/usr/bin/env python3
"""
Script para verificar transações de blockchain via API.

Comunica APENAS com a API FastAPI - sem acesso direto ao app.

Uso: 
  python verify_blockchain.py <tx_hash>
  python verify_blockchain.py --contract
"""

import sys
import json
from urllib import request as urlrequest
from rich import print as rprint
from rich.panel import Panel
from rich.table import Table

# URL da API
BASE_URL = "http://127.0.0.1:8000"


def get_api_json(path: str, *, verbose: bool = False) -> dict | None:
    """Obter JSON da API com o mesmo tratamento usado pelo verificador."""
    if not path.startswith("/"):
        path = f"/{path}"

    try:
        if verbose:
            rprint(f"\n[dim]Consultando API: {path}[/dim]")

        req = urlrequest.Request(
            url=f"{BASE_URL}{path}",
            method="GET",
        )

        with urlrequest.urlopen(req) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))

        if data.get("error"):
            if verbose:
                rprint(f"[red]✗ Erro da API: {data.get('error')}[/red]")
            return None

        return data

    except urlrequest.HTTPError as e:
        if verbose:
            try:
                error_data = json.loads(e.read().decode("utf-8"))
                rprint(f"[red]✗ Erro HTTP {e.code}:[/red] {error_data.get('detail', str(error_data))}")
            except Exception:
                rprint(f"[red]✗ Erro HTTP {e.code}:[/red] {e.reason}")
        return None

    except Exception as e:
        if verbose:
            rprint(f"[red]✗ Erro ao consultar API:[/red] {e}")
        return None


def get_verified_resource_status(resource: str, item_id: str) -> tuple[bool, dict | None, str]:
    """Verificar um manifesto/registo através do GET integrado da API."""
    data = get_api_json(f"/{resource}/{item_id}")
    if not data:
        return False, None, f"{resource.rstrip('s').capitalize()} '{item_id}' não encontrado ou indisponível."

    verification = data.get("verification")
    if not verification:
        return False, data, "Resposta da API não contém dados de verificação."

    if verification.get("overall_valid") is not True:
        return False, data, "Falhou a verificação de integridade contra a blockchain."

    return True, data, "OK"


def get_transaction_data(tx_hash: str) -> dict | None:
    """
    Obter dados de uma transação via API.
    
    Chama GET /verification/transaction/{tx_hash}
    
    Args:
        tx_hash: Hash da transação (com ou sem 0x)
    
    Returns:
        Dicionário com dados da transação decodificada, ou None se erro
    """
    # Garantir prefixo 0x
    if not tx_hash.startswith("0x"):
        tx_hash = f"0x{tx_hash}"
    
    rprint(f"\n[dim]Consultando API para: {tx_hash}[/dim]")
    return get_api_json(f"/verification/transaction/{tx_hash}", verbose=True)



def display_decoded_tx(tx_data: dict):
    """Mostrar dados decodificados da transação."""
    rprint(Panel(
        "[bold cyan]📋 TRANSAÇÃO VERIFICADA[/bold cyan]",
        title="[bold]Sepolia Testnet (via API)[/bold]",
        border_style="cyan"
    ))
    
    # Info básica
    info_table = Table(show_header=True, header_style="bold cyan")
    info_table.add_column("Campo", style="cyan", width=20)
    info_table.add_column("Valor", style="white")
    
    tx_hash = tx_data.get("tx_hash", "N/A")
    info_table.add_row("TX Hash", tx_hash[:20] + "..." if len(tx_hash) > 20 else tx_hash)
    
    if "function" in tx_data:
        info_table.add_row("Função", tx_data.get("function", "N/A"))
    
    if "status" in tx_data:
        status = tx_data["status"]
        status_text = "[green]✅ SUCESSO[/green]" if status else "[red]❌ FALHOU[/red]"
        info_table.add_row("Status", status_text)
    
    if "block" in tx_data:
        info_table.add_row("Bloco", str(tx_data["block"]))
    
    if "gas_used" in tx_data:
        info_table.add_row("Gas Usado", str(tx_data["gas_used"]))
    
    if "exists_on_chain" in tx_data:
        exists_text = "[green]✓ Sim[/green]" if tx_data["exists_on_chain"] else "[red]✗ Não[/red]"
        info_table.add_row("Existe na Blockchain", exists_text)
    
    rprint(info_table)
    
    # Dados da função (se houver)
    if tx_data.get("data"):
        rprint("\n[bold cyan]📦 Parâmetros:[/bold cyan]")
        params_table = Table(show_header=True, header_style="bold cyan")
        params_table.add_column("Parâmetro", style="cyan")
        params_table.add_column("Valor", style="white", overflow="fold")
        
        for key, value in tx_data["data"].items():
            if isinstance(value, list):
                value_str = "[" + ", ".join(str(v) for v in value) + "]"
            else:
                value_str = str(value)
            
            params_table.add_row(key, value_str)
        
        rprint(params_table)



def main():
    """Programa principal."""
    rprint(Panel(
        "[bold cyan]🔍 Verificador de Transações Blockchain[/bold cyan]\n"
        "[dim]Comunicando via API FastAPI[/dim]",
        border_style="cyan"
    ))
    
    if len(sys.argv) < 2:
        rprint("\n[yellow]Uso:[/yellow]")
        rprint("  python verify_blockchain.py <tx_hash>")
        rprint("\n[yellow]Exemplos:[/yellow]")
        rprint("  python verify_blockchain.py f430c9da1b767163dcde35f51922672944336144d5b4345b9142e3252acb0a2c")
        rprint("  python verify_blockchain.py 0xf430c9da1b767163dcde35f51922672944336144d5b4345b9142e3252acb0a2c")
        sys.exit(1)
    
    tx_hash = sys.argv[1]
    tx_data = get_transaction_data(tx_hash)
    
    if tx_data:
        display_decoded_tx(tx_data)
        tx_hash_full = tx_data.get("tx_hash", tx_hash)
        rprint(f"\n[dim]Explorer URL: https://sepolia.etherscan.io/tx/{tx_hash_full}[/dim]")
    else:
        rprint("\n[red]✗ Não foi possível obter informações da transação[/red]")
        sys.exit(1)

if __name__ == "__main__":
    main()
