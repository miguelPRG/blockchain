# 🍺 Blockchain Supply Chain System

Sistema híbrido de blockchain para rastreabilidade de cerveja artesanal com FastAPI backend e clientes CLI isolados.

## 🎯 Arquitetura

Projeto estruturado em **dois projetos uv independentes**:

```
blockchain/
├── app/                    ← Backend FastAPI (servidor)
│   ├── pyproject.toml
│   ├── core/
│   ├── services/
│   ├── routers/
│   ├── contracts/          ← Smart contracts Solidity
│   └── main.py
│
├── client/                 ← Clientes (isolados via HTTP)
│   ├── pyproject.toml
│   ├── cli_user.py         ← Interface CLI
│   └── verify_blockchain.py ← Verificação de blockchain
│
└── pyproject.toml          ← Workspace root
```

## 🔐 Separação de Segurança

- **Backend** (`app/`): Centraliza toda lógica, smart contracts e validação
- **Clientes** (`client/`): Comunicam **APENAS via HTTP**, sem acesso ao código backend
- **Sem violações**: Clientes não importam módulos do backend

## 🚀 Quick Start

### Backend

```bash
cd app/
uv sync
uv run fastapi dev main.py
```

API disponível em `http://127.0.0.1:8000`

### Client

Em outro terminal:

```bash
cd client/
uv sync
uv run python cli_user.py
```

## 📦 Dependências

### App (Backend)
- FastAPI 0.136.1
- Web3 7.16.0
- Pydantic Settings 2.14.1
- SQLAlchemy 2.0+
- ECDSA 0.19.2
- Rich 15.0.0
- py-solc-x ≤2.0.5

### Client (Clientes)
- Rich 15.0.0
- (Comunica via HTTP - sem dependências de blockchain)

## 📋 Project Structure

- `app/` - Backend FastAPI (servidor centralizado)
  - `core/` - Utilities: database, hashing, security, settings
  - `crud/` - Database operations
  - `models/` - SQLAlchemy models
  - `routers/` - API endpoints
  - `schemas/` - Pydantic schemas
  - `services/` - Business logic
  - `contracts/` - Smart contracts Solidity
- `client/` - Clientes isolados
  - `cli_user.py` - Terminal UI para múltiplos usuários
  - `verify_blockchain.py` - Verificação de transações

## 🔗 API Endpoints

```
/config/
  GET    /status              - Status da configuração
  POST   /authenticate-manager - Autenticar Supply Manager
  GET    /contract-address    - Endereço do contrato
  POST   /contract-address    - Atualizar endereço

/verification/
  GET    /contract/{address}  - Verificar contrato na blockchain
  GET    /transaction/{hash}  - Dados da transação
  GET    /contract-status     - Status completo com Etherscan

/manifests/
  POST   /                    - Criar manifesto
  GET    /{id}                - Obter manifesto
  GET    /{id}/verify         - Verificar manifesto

/records/
  POST   /                    - Criar registro
  GET    /{id}                - Obter registro
  GET    /{id}/verify         - Verificar registro

/health/
  GET    /status              - Status da API
```

## 👥 Usuários de Teste

- **Alice (Producer)**: `0x7Ac8041347b40a6F1ee3e9e9f82C1370afdbea50`
- **Bob (Transporter)**: `0x69aF73CF609DdA4112d1e9f1FA337281202457F4`
- **Charlie (Receiver)**: `0x7832aE65a53e5c359992F6B4320736238b8cb4DE`
- **Supply Manager**: `0x9D77a7336C19eE8975Eb6267c2aF384B90C73455`

## 🔧 Configuração

### .env

```
SEPOLIA_RPC_URL=https://sepolia.infura.io/v3/YOUR_KEY
CONTRACT_ADDRESS=0x...           # Opcional - auto-configurable
MANAGER_KEY=0x...                # Opcional - auth em runtime
```

## 📖 Documentação

- [Backend API](app/README.md)
- [Client CLI](client/README.md)

## 🧪 Testes

```bash
# Criar manifesto
python client/cli_user.py

# Verificar transação
python client/verify_blockchain.py 0xTX_HASH

# Simular ataque (verificar detecção)
# Usar opção no CLI
```

## 📄 License

MIT

## 👨‍💻 Development

Workspace uv com dois projetos independentes:

```bash
# Sincronizar ambos os projetos
uv sync

# Apenas backend
cd app && uv sync

# Apenas client
cd client && uv sync
```
