# Blockchain Supply Chain - Client

Cliente isolado para o sistema de blockchain supply chain.

## Descrição

Este projeto contém os clientes para interagir com o backend FastAPI:
- **cli_user.py** - Interface CLI para usuários (Alice, Bob, Charlie)
- **verify_blockchain.py** - Verificação de transações na blockchain

## Separação de Segurança

Os clientes comunicam **APENAS via HTTP** com a API do backend em `app/`. Nenhum acesso direto aos módulos do backend é permitido.

## Instalação

```bash
cd client/
uv sync
```

## Uso

### CLI Interativa

```bash
uv run python cli_user.py
```

Permite:
- Selecionar usuário (Alice/Bob/Charlie)
- Criar manifestos de cerveja
- Criar registros de operação
- Verificar integridade de dados
- Simular ataques para testes

### Verificação de Blockchain

```bash
uv run python verify_blockchain.py 0xTRANSACTION_HASH
```

Obtém e mostra dados da transação via Etherscan.

## Dependências

- `rich` - Terminal UI
- `dotenv` - Carregamento de variáveis de ambiente (opcional)

## Como Funciona

```
client/
  ├── cli_user.py
  │   ├─ GET /config/status
  │   ├─ POST /config/authenticate-manager
  │   ├─ POST /manifests
  │   └─ POST /records
  │
  └── verify_blockchain.py
      └─ GET /verification/transaction/{hash}
```

Todos os dados transitam via HTTP, sem acesso direto ao código do backend.
