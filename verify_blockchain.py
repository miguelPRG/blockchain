#!/usr/bin/env python3
"""
Script para decodificar transações e dados armazenados no smart contract Anchor.

Uso: 
  python verify_blockchain.py <tx_hash>
  python verify_blockchain.py --contract
"""

import sys
from web3 import Web3
from rich import print as rprint
from rich.panel import Panel
from rich.table import Table

from app.core.settings import settings
from app.services.blockchain_service import ANCHOR_ABI

def decode_tx_data(tx_hash: str) -> dict | None:
    """Decodificar dados de uma transação usando o ABI."""
    try:
        if not settings.sepolia_rpc_url:
            rprint("[red]✗ SEPOLIA_RPC_URL não configurada[/red]")
            return None
        
        w3 = Web3(Web3.HTTPProvider(settings.sepolia_rpc_url))
        
        if not w3.is_connected():
            rprint("[red]✗ Erro ao conectar a Sepolia[/red]")
            return None
        
        # Normalizar hash
        if not tx_hash.startswith("0x"):
            tx_hash = "0x" + tx_hash
        
        rprint(f"\n[dim]Buscando transação: {tx_hash}[/dim]")
        
        # Obter informações da transação
        tx = w3.eth.get_transaction(tx_hash)
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        
        if not tx or not receipt:
            rprint("[red]✗ Transação não encontrada[/red]")
            return None
        
        # Verificar se é para o contrato correto
        if tx["to"].lower() != settings.contract_address.lower():
            rprint(f"[red]✗ Transação não é para o contrato {settings.contract_address}[/red]")
            return None
        
        # Decodificar input data usando o ABI
        input_data = tx["input"]
        
        if input_data == "0x":
            return {
                "tx_hash": tx_hash,
                "status": receipt["status"],
                "function": "Constructor",
                "data": {},
            }
        
        # Encontrar a função correta no ABI
        function_signature = input_data[:10]  # 0x + 4 bytes (8 hex chars)
        
        # Criar contrato instance apenas para decodificar
        contract = w3.eth.contract(abi=ANCHOR_ABI)
        
        try:
            # Tentar decodificar usando decode_function_input
            func_obj, func_params = contract.decode_function_input(input_data)
            
            # Converter parâmetros para formato legível
            decoded_params = {}
            for key, value in func_params.items():
                if isinstance(value, bytes):
                    # Tentar decodificar como UTF-8, se falhar mostrar hex
                    try:
                        decoded_params[key] = value.decode('utf-8')
                    except:
                        decoded_params[key] = value.hex()
                elif isinstance(value, list):
                    # Lista de strings
                    decoded_params[key] = []
                    for item in value:
                        if isinstance(item, bytes):
                            try:
                                decoded_params[key].append(item.decode('utf-8'))
                            except:
                                decoded_params[key].append(item.hex())
                        else:
                            decoded_params[key].append(str(item))
                else:
                    decoded_params[key] = str(value)
            
            return {
                "tx_hash": tx_hash,
                "status": receipt["status"],
                "function": func_obj.fn_name,
                "block": receipt["blockNumber"],
                "gas_used": receipt["gasUsed"],
                "data": decoded_params,
            }
        except Exception as e:
            rprint(f"[red]✗ Erro ao decodificar: {e}[/red]")
            return None
            
    except Exception as e:
        rprint(f"[red]✗ Erro: {e}[/red]")
        return None


def display_decoded_tx(tx_data: dict):
    """Mostrar dados decodificados."""
    rprint(Panel(
        "[bold cyan]📋 TRANSAÇÃO DECODIFICADA[/bold cyan]",
        title="[bold]Sepolia Testnet[/bold]",
        border_style="cyan"
    ))
    
    # Info básica
    info_table = Table(show_header=True, header_style="bold cyan")
    info_table.add_column("Campo", style="cyan", width=20)
    info_table.add_column("Valor", style="white")
    
    info_table.add_row("TX Hash", tx_data["tx_hash"][:20] + "...")
    info_table.add_row("Função", tx_data["function"])
    info_table.add_row("Status", "[green]✅ SUCESSO[/green]" if tx_data["status"] == 1 else "[red]❌ FALHOU[/red]")
    
    if "block" in tx_data:
        info_table.add_row("Bloco", str(tx_data["block"]))
        info_table.add_row("Gas Usado", str(tx_data["gas_used"]))
    
    rprint(info_table)
    
    # Dados da função
    if tx_data["data"]:
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
        "[bold cyan]🔍 Decoder de Transações Anchor[/bold cyan]",
        border_style="cyan"
    ))
    
    if len(sys.argv) < 2:
        rprint("\n[yellow]Uso:[/yellow]")
        rprint("  python verify_blockchain.py <tx_hash>")
        rprint("  python verify_blockchain.py --contract")
        rprint("\n[yellow]Exemplos:[/yellow]")
        rprint("  python verify_blockchain.py f430c9da1b767163dcde35f51922672944336144d5b4345b9142e3252acb0a2c")
        rprint("  python verify_blockchain.py 0xf430c9da1b767163dcde35f51922672944336144d5b4345b9142e3252acb0a2c")
        rprint("  python verify_blockchain.py --contract")
        sys.exit(1)
    
    if sys.argv[1] == "--contract":
        if not settings.contract_address or settings.contract_address == "0x0000000000000000000000000000000000000000":
            rprint("[red]✗ CONTRACT_ADDRESS não configurada[/red]")
            sys.exit(1)
        
        url = f"https://sepolia.etherscan.io/address/{settings.contract_address}"
        rprint(f"\n[green]Contrato:[/green]\n  {url}\n")
    else:
        tx_hash = sys.argv[1]
        tx_data = decode_tx_data(tx_hash)
        
        if tx_data:
            display_decoded_tx(tx_data)
            rprint(f"\n[dim]Explorer: https://sepolia.etherscan.io/tx/{tx_data['tx_hash']}[/dim]")
        else:
            sys.exit(1)

if __name__ == "__main__":
    main()
