"""Serviço de deployment do contrato Anchor na blockchain Sepolia."""

import logging
import sys
from pathlib import Path
from web3 import Web3
import solcx
from rich import print as rprint

from app.core.settings import settings

logger = logging.getLogger(__name__)


def is_contract_deployed(contract_address: str) -> bool:
    """Verificação se contrato está publicado e no formato esperado (com itemId)."""
    try:
        w3 = Web3(Web3.HTTPProvider(settings.sepolia_rpc_url))
        if not w3.is_connected():
            return False
        code = w3.eth.get_code(contract_address)
        if not code or len(code) <= 2:
            return False

        # Valida versão esperada do contrato: getAnchorDetails com itemId (4 retornos).
        details_v2_abi = [
            {
                "inputs": [{"internalType": "bytes32", "name": "_payloadHash", "type": "bytes32"}],
                "name": "getAnchorDetails",
                "outputs": [
                    {"internalType": "bool", "name": "exists", "type": "bool"},
                    {"internalType": "uint256", "name": "timestamp", "type": "uint256"},
                    {"internalType": "address", "name": "creator", "type": "address"},
                    {"internalType": "string", "name": "itemId", "type": "string"},
                ],
                "stateMutability": "view",
                "type": "function",
            }
        ]
        contract = w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=details_v2_abi)
        contract.functions.getAnchorDetails(bytes(32)).call()
        return True
    except Exception:
        return False


def auto_deploy_if_needed(verbose: bool = False, manager_key: str | None = None) -> str | None:
    """Fazer deployment automático se ainda não estiver publicado.
    
    Returns:
        Endereço do contrato (novo ou existente), ou None se falhou
    """
    if not manager_key:
        raise ValueError("manager_key is required for deployment")

    logger.info("Iniciando deployment automático")
    if verbose:
        rprint("\n[bold yellow]⚙️ Iniciando deployment automático...[/bold yellow]")
    
    try:
        project_root = Path(__file__).parent.parent
        solidity_file = project_root / "contracts" / "Anchor.sol"
        
        if verbose:
            rprint("[dim]📝 Compilando contrato...[/dim]")
        compiled = compile_contract(solidity_file)
        
        if verbose:
            rprint("[dim]🚀 Deploying na Sepolia...[/dim]")
        contract_address = deploy_contract(compiled, manager_key)
        
        if verbose:
            rprint(f"[green]✅ Contrato publicado: {contract_address}[/green]")
        
        logger.info(f"Contrato publicado com sucesso: {contract_address}")
        return contract_address
    except Exception as e:
        logger.error(f"Erro no deployment automático: {e}", exc_info=True)
        sys.stderr.write(f"\n[DEPLOY ERROR] {e}\n")
        sys.stderr.flush()
        if verbose:
            rprint(f"[red]✗ Erro: {e}[/red]")
        return None


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


def deploy_contract(compiled: dict, manager_key: str) -> str:
    """Fazer deploy do contrato na Sepolia."""
    logger.info("Iniciando deployment do contrato")
    rprint("\n[bold cyan]🚀 Iniciando deployment...[/bold cyan]")
    
    if not settings.sepolia_rpc_url:
        logger.error("SEPOLIA_RPC_URL não configurada")
        raise ValueError("SEPOLIA_RPC_URL não configurada")
    if not manager_key:
        logger.error("MANAGER_KEY não configurada")
        raise ValueError("MANAGER_KEY não configurada")
    
    logger.debug(f"Conectando a: {settings.sepolia_rpc_url}")
    w3 = Web3(Web3.HTTPProvider(settings.sepolia_rpc_url))
    if not w3.is_connected():
        logger.error("Falha ao conectar a Sepolia")
        raise ConnectionError("Não consegui conectar a Sepolia")
    
    logger.debug("Conectado com sucesso a Sepolia")
    rprint("[green]✓ Conectado a Sepolia![/green]")
    
    account = w3.eth.account.from_key(manager_key)
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
        
        # Obter saldo e nonce
        nonce = w3.eth.get_transaction_count(account.address)
        balance_wei = w3.eth.get_balance(account.address)
        balance_eth = w3.from_wei(balance_wei, 'ether')
        
        logger.info(f"Saldo da conta: {balance_eth:.6f} ETH ({balance_wei} wei)")
        rprint(f"[cyan]Saldo da conta: {balance_eth:.6f} ETH[/cyan]")
        
        if balance_eth < 0.001:
            raise ValueError(f"Saldo insuficiente: {balance_eth:.6f} ETH (mínimo: 0.001 ETH)")
        
        # Obter gas price
        gas_price = w3.eth.gas_price
        logger.debug(f"Gas Price RPC: {gas_price} wei ({w3.from_wei(gas_price, 'gwei'):.2f} gwei)")
        
        # Usar gas price razoável (5-20 gwei para Sepolia)
        min_gas_price = w3.to_wei(5, 'gwei')
        max_gas_price = w3.to_wei(50, 'gwei')
        
        if gas_price < min_gas_price:
            gas_price = min_gas_price
            logger.info(f"Gas price aumentado para {w3.from_wei(gas_price, 'gwei'):.2f} gwei")
        elif gas_price > max_gas_price:
            gas_price = w3.to_wei(10, 'gwei')  # Usar um valor fixo se estiver muito alto
            logger.info(f"Gas price reduzido para {w3.from_wei(gas_price, 'gwei'):.2f} gwei")
        
        rprint(f"[dim]Nonce: {nonce}, Gas Price: {w3.from_wei(gas_price, 'gwei'):.2f} gwei[/dim]")
        
        # Tentar estimar gas com RETRY
        gas_limit = None
        for attempt in range(3):
            try:
                logger.debug(f"Estimando gas (tentativa {attempt + 1}/3)...")
                
                # Construir tx SEM gas para estimação
                tx = Contract.constructor().build_transaction({
                    "from": account.address,
                    "nonce": nonce,
                    "gasPrice": gas_price,
                })
                
                estimated_gas = w3.eth.estimate_gas(tx)
                gas_limit = int(estimated_gas * 1.15)  # 15% de margem
                logger.info(f"Gas estimado: {estimated_gas}, com margem: {gas_limit}")
                rprint(f"[green]✓ Gas estimado: {gas_limit}[/green]")
                break
            
            except Exception as estimate_err:
                logger.warning(f"Falha na estimação (tentativa {attempt + 1}): {estimate_err}")
                if attempt < 2:
                    import time
                    wait = (attempt + 1) * 2
                    logger.info(f"Aguardando {wait}s antes de tentar novamente...")
                    rprint(f"[yellow]⏳ Aguardando {wait}s antes de tentar novamente...[/yellow]")
                    time.sleep(wait)
        
        # Se estimação falhou completamente, usar fallback conservador
        if gas_limit is None:
            gas_limit = 2500000  # Fallback para Anchor.sol
            logger.info(f"Usando fallback de gas: {gas_limit}")
            rprint(f"[yellow]Usando fallback de gas: {gas_limit}[/yellow]")
        
        # Verificar custo total
        total_cost_wei = gas_limit * gas_price
        total_cost_eth = w3.from_wei(total_cost_wei, 'ether')
        
        logger.info(f"Custo total estimado: {total_cost_eth:.6f} ETH")
        rprint(f"[dim]Custo total: {total_cost_eth:.6f} ETH[/dim]")
        
        if balance_wei < total_cost_wei:
            raise ValueError(
                f"Saldo insuficiente:\n"
                f"  Saldo: {balance_eth:.6f} ETH\n"
                f"  Custo: {total_cost_eth:.6f} ETH\n"
                f"  Diferença: {(total_cost_eth - balance_eth):.6f} ETH"
            )
        
        # Construir e enviar transação
        logger.debug("Construindo transação final...")
        tx = Contract.constructor().build_transaction({
            "from": account.address,
            "nonce": nonce,
            "gas": gas_limit,
            "gasPrice": gas_price,
        })
        
        rprint("\n[bold]🔐 Assinando e enviando transação...[/bold]")
        logger.info("Assinando transação")
        signed_tx = w3.eth.account.sign_transaction(tx, manager_key)
        
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


def build_deploy_transaction(from_address: str) -> dict:
    """Construir a transação de deployment sem receber chave privada."""
    if not settings.sepolia_rpc_url:
        raise ValueError("SEPOLIA_RPC_URL não configurada")
    if not from_address or not from_address.startswith("0x"):
        raise ValueError("Endereço do deployer inválido")

    w3 = Web3(Web3.HTTPProvider(settings.sepolia_rpc_url))
    if not w3.is_connected():
        raise ConnectionError("Não consegui conectar a Sepolia")

    project_root = Path(__file__).parent.parent
    solidity_file = project_root / "contracts" / "Anchor.sol"
    compiled = compile_contract(solidity_file)

    contract_data = compiled["contracts"]["Anchor.sol"]["Anchor"]
    abi = contract_data["abi"]
    bytecode = contract_data["evm"]["bytecode"]["object"]

    checksum_from = Web3.to_checksum_address(from_address)
    contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    latest_block = w3.eth.get_block("latest")
    base_fee = latest_block.get("baseFeePerGas") or w3.eth.gas_price
    priority_fee = w3.eth.max_priority_fee if hasattr(w3.eth, "max_priority_fee") else w3.to_wei(2, "gwei")

    tx_base = {
        "from": checksum_from,
        "nonce": w3.eth.get_transaction_count(checksum_from, "pending"),
        "chainId": w3.eth.chain_id,
        "maxPriorityFeePerGas": int(priority_fee),
        "maxFeePerGas": int(base_fee * 2 + priority_fee),
        "type": 2,
    }

    gas_estimate_tx = contract.constructor().build_transaction(tx_base)
    gas_limit = int(w3.eth.estimate_gas(gas_estimate_tx) * 1.15)
    return contract.constructor().build_transaction({**tx_base, "gas": gas_limit})


def broadcast_signed_deploy_transaction(signed_transaction: str) -> str:
    """Publicar transação de deployment assinada localmente e devolver o contrato."""
    if not settings.sepolia_rpc_url:
        raise ValueError("SEPOLIA_RPC_URL não configurada")

    w3 = Web3(Web3.HTTPProvider(settings.sepolia_rpc_url))
    if not w3.is_connected():
        raise ConnectionError("Não consegui conectar a Sepolia")

    raw_tx = signed_transaction[2:] if signed_transaction.startswith("0x") else signed_transaction
    tx_hash = w3.eth.send_raw_transaction(bytes.fromhex(raw_tx))
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

    if receipt["status"] != 1:
        raise Exception("Transação de deployment falhou")
    if not receipt["contractAddress"]:
        raise Exception("Receipt não contém endereço do contrato")

    return receipt["contractAddress"]


def diagnose_account(manager_key: str | None = None) -> dict:
    """Diagnosticar estado da conta e rede."""
    result = {
        "connected": False,
        "account": None,
        "balance_eth": 0,
        "balance_wei": 0,
        "gas_price_gwei": 0,
        "nonce": 0,
        "error": None
    }
    
    try:
        if not settings.sepolia_rpc_url:
            result["error"] = "SEPOLIA_RPC_URL não configurada"
            return result
        if not manager_key:
            result["error"] = "MANAGER_KEY não configurada"
            return result
        
        w3 = Web3(Web3.HTTPProvider(settings.sepolia_rpc_url))
        
        if not w3.is_connected():
            result["error"] = "Falha ao conectar ao RPC endpoint"
            return result
        
        result["connected"] = True
        
        account = w3.eth.account.from_key(manager_key)
        result["account"] = account.address
        
        balance_wei = w3.eth.get_balance(account.address)
        result["balance_wei"] = balance_wei
        result["balance_eth"] = float(w3.from_wei(balance_wei, 'ether'))
        
        gas_price = w3.eth.gas_price
        result["gas_price_gwei"] = float(w3.from_wei(gas_price, 'gwei'))
        
        result["nonce"] = w3.eth.get_transaction_count(account.address)
        
        return result
    
    except Exception as e:
        result["error"] = str(e)
        return result
