"""Serviço de deployment do contrato Anchor na blockchain Sepolia."""

import logging
import sys
from pathlib import Path
from web3 import Web3
import solcx
from rich import print as rprint
from rich.panel import Panel
from rich.prompt import Confirm

from app.core.settings import settings

logger = logging.getLogger(__name__)


def is_contract_deployed() -> bool:
    """Verificação simples (interna) se contrato está publicado."""
    try:
        w3 = Web3(Web3.HTTPProvider(settings.sepolia_rpc_url))
        if not w3.is_connected():
            return False
        code = w3.eth.get_code(settings.contract_address)
        return code and len(code) > 2
    except Exception:
        return False


def auto_deploy_if_needed(verbose: bool = False) -> bool:
    """Fazer deployment automático se ainda não estiver publicado."""
    if is_contract_deployed():
        if verbose:
            rprint("[green]✓ Contrato já publicado[/green]")
        return True
    
    logger.info("Iniciando deployment automático")
    if verbose:
        rprint("\n[bold yellow]⚙️ Iniciando deployment automático...[/bold yellow]")
    
    try:
        project_root = Path(__file__).parent.parent.parent
        solidity_file = project_root / "contracts" / "Anchor.sol"
        env_file = project_root / ".env"
        
        if verbose:
            rprint("[dim]📝 Compilando contrato...[/dim]")
        compiled = compile_contract(solidity_file)
        
        if verbose:
            rprint("[dim]🚀 Deploying na Sepolia...[/dim]")
        contract_address = deploy_contract(compiled)
        
        if verbose:
            rprint("[dim]📝 Atualizando .env...[/dim]")
        update_env_file(contract_address, env_file)
        
        if verbose:
            rprint(f"[green]✅ Contrato publicado: {contract_address}[/green]")
        
        logger.info(f"Contrato publicado com sucesso: {contract_address}")
        return True
    except Exception as e:
        logger.error(f"Erro no deployment automático: {e}", exc_info=True)
        sys.stderr.write(f"\n[DEPLOY ERROR] {e}\n")
        sys.stderr.flush()
        if verbose:
            rprint(f"[red]✗ Erro: {e}[/red]")
        return False


def compile_contract(solidity_file: Path) -> dict:
    """Compilar contrato Solidity."""
    logger.info(f"Compilando contrato: {solidity_file}")
    rprint("\n[bold cyan]📝 Compilando contrato...[/bold cyan]")
    
    if not solidity_file.exists():
        logger.error(f"Contrato não encontrado: {solidity_file}")
        raise FileNotFoundError(f"Contrato não encontrado: {solidity_file}")
    
    try:
        rprint("[yellow]⏳ Instalando compilador Solidity 0.8.35...[/yellow]")
        logger.debug("Instalando solcx 0.8.35")
        solcx.install_solc("0.8.35")
        
        with open(solidity_file, 'r') as f:
            contract_source = f.read()
        
        logger.debug(f"Arquivo lido: {len(contract_source)} bytes")
        
        input_json = {
            "language": "Solidity",
            "sources": {
                "Anchor.sol": {
                    "content": contract_source
                }
            },
            "settings": {
                "outputSelection": {
                    "*": {
                        "*": ["abi", "evm.bytecode", "metadata"]
                    }
                }
            }
        }
        
        logger.debug("Chamando solcx.compile_standard")
        compiled = solcx.compile_standard(
            input_json,
            solc_version="0.8.35"
        )
        
        logger.debug(f"Compilação bem-sucedida. Contratos: {list(compiled.get('contracts', {}).keys())}")
        rprint("[green]✓ Compilado![/green]")
        return compiled
    except Exception as e:
        logger.error(f"Erro na compilação: {e}", exc_info=True)
        sys.stderr.write(f"\n[COMPILE ERROR] {e}\n")
        sys.stderr.flush()
        rprint(f"[red]✗ Erro na compilação: {e}[/red]")
        raise


def deploy_contract(compiled: dict) -> str:
    """Fazer deploy do contrato na Sepolia."""
    logger.info("Iniciando deployment do contrato")
    rprint("\n[bold cyan]🚀 Iniciando deployment...[/bold cyan]")
    
    if not settings.sepolia_rpc_url:
        logger.error("SEPOLIA_RPC_URL não configurada")
        raise ValueError("SEPOLIA_RPC_URL não configurada")
    if not settings.private_key_for_deploy:
        logger.error("PRIVATE_KEY_FOR_DEPLOY não configurada")
        raise ValueError("PRIVATE_KEY_FOR_DEPLOY não configurada")
    
    logger.debug(f"Conectando a: {settings.sepolia_rpc_url}")
    w3 = Web3(Web3.HTTPProvider(settings.sepolia_rpc_url))
    if not w3.is_connected():
        logger.error("Falha ao conectar a Sepolia")
        raise ConnectionError("Não consegui conectar a Sepolia")
    
    logger.debug("Conectado com sucesso a Sepolia")
    rprint("[green]✓ Conectado a Sepolia![/green]")
    
    account = w3.eth.account.from_key(settings.private_key_for_deploy)
    logger.debug(f"Conta: {account.address}")
    rprint(f"[dim]Conta: {account.address}[/dim]")
    
    # Extrair ABI e bytecode do formato compile_standard
    try:
        logger.debug("Extraindo ABI e bytecode")
        contract_data = compiled["contracts"]["Anchor.sol"]["Anchor"]
        abi = contract_data["abi"]
        bytecode = contract_data["evm"]["bytecode"]["object"]
        logger.debug(f"ABI tem {len(abi)} funções/eventos")
        logger.debug(f"Bytecode: {len(bytecode)} caracteres")
    except KeyError as e:
        logger.error(f"Erro ao extrair ABI/bytecode: {e}", exc_info=True)
        sys.stderr.write(f"\n[EXTRACT ERROR] {e}\n")
        sys.stderr.flush()
        raise ValueError(f"Erro ao extrair ABI/bytecode: {e}")
    
    try:
        logger.debug("Criando contrato Web3")
        Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
        nonce = w3.eth.get_transaction_count(account.address)
        gas_price = w3.eth.gas_price
        
        logger.debug(f"Nonce: {nonce}, Gas Price: {gas_price}")
        
        tx = Contract.constructor().build_transaction({
            "from": account.address,
            "nonce": nonce,
            "gas": 1500000,  # Fallback inicial (otimizado: ~1.1M-1.3M real, 1.5M seguro)
            "gasPrice": gas_price,
        })
        
        logger.debug("Estimando gas")
        try:
            estimated_gas = w3.eth.estimate_gas(tx)
            tx["gas"] = estimated_gas + 50000  # Margem de segurança 6%
            logger.debug(f"Gas estimado: {tx['gas']}")
        except Exception as e:
            logger.warning(f"Falha ao estimar gas: {e}. Usando fallback realista")
            # Fallback: estima conservadora baseada em contrato similar
            # Anchor.sol = ~1.1M-1.3M com struct otimizado
            tx["gas"] = 1500000
        
        rprint("\n[bold]🔐 Assinando e enviando transação...[/bold]")
        logger.info("Assinando transação")
        signed_tx = w3.eth.account.sign_transaction(tx, settings.private_key_for_deploy)
        
        logger.info("Enviando transação assinada")
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        logger.info(f"TX enviada: {tx_hash.hex()}")
        rprint(f"[cyan]TX: {tx_hash.hex()}[/cyan]")
        
        rprint("[bold yellow]⏳ Aguardando confirmação...[/bold yellow]")
        logger.info("Aguardando confirmação da transação")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        logger.debug(f"Receipt: {receipt}")
        
        if receipt["status"] != 1:
            logger.error("Transação de deployment falhou")
            raise Exception("Transação de deployment falhou")
        
        contract_address = receipt["contractAddress"]
        logger.info(f"Contrato deploiado: {contract_address}")
        rprint(f"[bold green]✅ Publicado: {contract_address}[/bold green]")
        return contract_address
    except Exception as e:
        logger.error(f"Erro no deploy: {e}", exc_info=True)
        sys.stderr.write(f"\n[DEPLOY TX ERROR] {e}\n")
        sys.stderr.flush()
        raise


def update_env_file(contract_address: str, env_file: Path) -> None:
    """Atualizar .env com contract address."""
    logger.info(f"Atualizando .env com: {contract_address}")
    content = env_file.read_text() if env_file.exists() else ""
    lines = content.split("\n")
    
    found = False
    for i, line in enumerate(lines):
        if line.startswith("CONTRACT_ADDRESS="):
            lines[i] = f"CONTRACT_ADDRESS={contract_address}"
            found = True
            break
    
    if not found:
        lines.append(f"CONTRACT_ADDRESS={contract_address}")
    
    env_file.write_text("\n".join(lines))
    logger.debug(f".env atualizado")
    rprint(f"[green]✓ .env atualizado[/green]")


def verify_deployment(contract_address: str) -> None:
    """Verificar se deployment funcionou."""
    logger.info(f"Verificando deployment: {contract_address}")
    rprint("\n[bold cyan]✔️ Verificando...[/bold cyan]")
    try:
        w3 = Web3(Web3.HTTPProvider(settings.sepolia_rpc_url))
        code = w3.eth.get_code(contract_address)
        if code and len(code) > 2:
            logger.info("Contrato verificado na blockchain")
            rprint("[green]✓ Verificado na blockchain![/green]")
        else:
            logger.error("Contrato não encontrado na blockchain")
            rprint("[red]✗ Contrato não encontrado[/red]")
    except Exception as e:
        logger.error(f"Erro na verificação: {e}", exc_info=True)
        rprint(f"[red]✗ Erro: {e}[/red]")


def deploy_anchor_contract() -> str | None:
    """Executar deployment completo."""
    project_root = Path(__file__).parent.parent.parent
    solidity_file = project_root / "contracts" / "Anchor.sol"
    env_file = project_root / ".env"
    
    rprint(Panel(
        "[bold cyan]🍺 Deploy Anchor → Sepolia[/bold cyan]",
        title="[bold]Deployment[/bold]",
        border_style="cyan"
    ))
    
    try:
        w3_temp = Web3()
        account = w3_temp.eth.account.from_key(settings.private_key_for_deploy)
        rprint(f"Conta: {account.address}")
    except:
        rprint("[yellow]⚠ Aviso: Não consegui ler conta[/yellow]")
    
    if not Confirm.ask("\nProsseguir?"):
        rprint("[red]Cancelado[/red]")
        return None
    
    try:
        compiled = compile_contract(solidity_file)
        contract_address = deploy_contract(compiled)
        update_env_file(contract_address, env_file)
        verify_deployment(contract_address)
        
        rprint(Panel(
            f"[bold green]✅ Sucesso![/bold green]\n\n"
            f"{contract_address}\n\n"
            f"https://sepolia.etherscan.io/address/{contract_address}",
            border_style="green"
        ))
        return contract_address
    except Exception as e:
        logger.error(f"Erro no deployment: {e}", exc_info=True)
        rprint(Panel(f"[bold red]❌ Erro[/bold red]\n\n{str(e)}", border_style="red"))
        return None


def main():
    """Entry point."""
    deploy_anchor_contract()


if __name__ == "__main__":
    main()
