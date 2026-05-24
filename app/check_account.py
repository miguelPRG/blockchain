#!/usr/bin/env python3
"""Verificador de diagnóstico da conta Supply Manager.

Este script verifica:
- Conexão ao RPC endpoint
- Saldo da conta
- Gas price atual
- Nonce da transação

Uso:
  python check_account.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from web3 import Web3
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Carregar .env
env_file = Path(__file__).parent / ".env"
load_dotenv(env_file)

console = Console()

SEPOLIA_RPC_URL = os.getenv("SEPOLIA_RPC_URL")
MANAGER_KEY = os.getenv("MANAGER_KEY")


def main():
    """Executar diagnóstico."""
    console.print("\n[bold cyan]🔍 Diagnóstico da Conta Supply Manager[/bold cyan]\n")
    
    # Verificar variáveis de ambiente
    if not SEPOLIA_RPC_URL:
        console.print("[red]✗ SEPOLIA_RPC_URL não configurada[/red]")
        sys.exit(1)
    
    if not MANAGER_KEY:
        console.print("[red]✗ MANAGER_KEY não configurada[/red]")
        sys.exit(1)
    
    console.print("[dim]RPC URL: {url}[/dim]".format(url=SEPOLIA_RPC_URL[:50] + "..."))
    console.print(f"[dim]Chave: {MANAGER_KEY[:10]}...{MANAGER_KEY[-10:]}[/dim]\n")
    
    # Conectar
    try:
        w3 = Web3(Web3.HTTPProvider(SEPOLIA_RPC_URL))
        if not w3.is_connected():
            console.print("[red]✗ Falha ao conectar ao RPC endpoint[/red]")
            sys.exit(1)
        console.print("[green]✓ Conectado ao RPC endpoint[/green]")
    except Exception as e:
        console.print(f"[red]✗ Erro ao conectar: {e}[/red]")
        sys.exit(1)
    
    # Obter conta
    try:
        account = w3.eth.account.from_key(MANAGER_KEY)
        console.print(f"[green]✓ Conta derivada[/green]")
    except Exception as e:
        console.print(f"[red]✗ Erro ao derivar conta: {e}[/red]")
        sys.exit(1)
    
    # Obter dados
    try:
        balance_wei = w3.eth.get_balance(account.address)
        balance_eth = w3.from_wei(balance_wei, 'ether')
        
        gas_price_wei = w3.eth.gas_price
        gas_price_gwei = w3.from_wei(gas_price_wei, 'gwei')
        
        nonce = w3.eth.get_transaction_count(account.address)
        
        # Mostrar em tabela
        table = Table(title="Estado da Conta", show_header=True, header_style="bold cyan")
        table.add_column("Propriedade", style="cyan")
        table.add_column("Valor", style="green")
        
        table.add_row("Endereço", account.address)
        table.add_row("Saldo (ETH)", f"{balance_eth:.6f}")
        table.add_row("Saldo (Wei)", f"{balance_wei:,}")
        table.add_row("Gas Price (Gwei)", f"{gas_price_gwei:.2f}")
        table.add_row("Gas Price (Wei)", f"{gas_price_wei:,}")
        table.add_row("Nonce", str(nonce))
        
        console.print(table)
        
        # Verificação de suficiência
        console.print()
        min_balance = 0.01
        if balance_eth >= min_balance:
            console.print(f"[green]✓ Saldo suficiente (>= {min_balance} ETH)[/green]")
        else:
            console.print(f"[red]✗ Saldo insuficiente (< {min_balance} ETH)[/red]")
        
        # Estimativa de custo de deployment
        deployment_gas = 2500000  # Fallback para Anchor.sol
        estimated_cost_wei = deployment_gas * gas_price_wei
        estimated_cost_eth = w3.from_wei(estimated_cost_wei, 'ether')
        
        console.print()
        console.print("[bold]Estimativa de Custo de Deployment:[/bold]")
        console.print(f"  Gas limite: {deployment_gas:,}")
        console.print(f"  Gas price: {gas_price_gwei:.2f} gwei")
        console.print(f"  Custo estimado: {estimated_cost_eth:.6f} ETH")
        
        if balance_eth >= estimated_cost_eth:
            console.print(f"  [green]✓ Saldo suficiente para deployment[/green]")
        else:
            shortage = estimated_cost_eth - balance_eth
            console.print(f"  [red]✗ Saldo insuficiente (faltam {shortage:.6f} ETH)[/red]")
        
        console.print()
    
    except Exception as e:
        console.print(f"[red]✗ Erro ao obter dados: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
