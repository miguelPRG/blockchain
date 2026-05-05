# 🍺 Rastreamento de Supplay Chain em Blockchain - Cerveja Artesanal

Uma plataforma acadêmica de rastreabilidade completa para supplay chain que combina a eficiência operacional de armazenamento fora da cadeia (off-chain) com a imutabilidade de um blockchain público.

## 📋 Objetivo do Projeto

Este projeto implementa um sistema híbrido de rastreamento focado em **cerveja artesanal**, permitindo:

- ✅ **Rastreabilidade completa**: Acompanhar cada lote desde a produção até à distribuição
- ✅ **Imutabilidade**: Hashes ancorados em Ethereum Mainnet garantem integridade
- ✅ **Autenticação mútua**: Assinaturas ECDSA garantem autenticidade de operações
- ✅ **Verificação independente**: Qualquer terceiro pode validar a integridade sem confiar no gerenciador
- ✅ **Custo otimizado**: Armazenamento eficiente fora da cadeia com ancoragem seletiva no blockchain

### Caso de Uso Real

Um cervejeiro artesanal pode registrar:
1. **Manifestos** (lotes de produção): ingredientes, quantidade, origem
2. **Registros de operação**: cada transformação (produção, embalagem, transporte, venda)
3. Cada operação é assinada digitalmente e o hash é ancorado no blockchain
4. Consumidores finais podem verificar a autenticidade usando `verify.py`

---

## 🏗️ Arquitetura e Organização

### Estrutura em Camadas

```
┌─────────────────────────────────────────┐
│  API REST (FastAPI) + CLI               │  ← Interface de usuário
├─────────────────────────────────────────┤
│  Services Layer                         │  ← Lógica de negócio
│  (Manifests, Records, Verification)    │
├─────────────────────────────────────────┤
│  CRUD + Database Access                 │  ← Acesso a dados
├─────────────────────────────────────────┤
│  Core (Security, Hashing, Settings)    │  ← Utilidades
├─────────────────────────────────────────┤
│  SQLite (Local) + Ethereum Mainnet      │  ← Persistência
└─────────────────────────────────────────┘
```

#### Blockchain do Ethereum Mainnet

**Ethereum Mainnet** é a rede principal (produção) do Ethereum, onde as transações são imutáveis e verificáveis globalmente. Escolhida por:

- ✅ **Imutabilidade garantida**: Hashes ancorados em Mainnet nunca podem ser alterados
- ✅ **Auditoria pública**: Qualquer pessoa pode verificar a integridade consultando a blockchain
- ✅ **Sem terceiros**: Não depende de servidores centralizados - o blockchain é a "fonte de verdade"
- ✅ **Padrão industrial**: Mainnet é usada em sistemas reais de supply chain (vs testnets que são apenas para testes)

*Alternativa considerada: Testnet (Sepolia) - mas para produção precisamos de Mainnet para garantir confiança real.*

### Fluxo de Dados

1. **Criação de Operação**: Usuário submete manifesto/registro via API ou CLI
2. **Assinatura**: Payload é hasheado (SHA-256) e assinado com ECDSA
3. **Armazenamento Local**: Dados armazenados em SQLite com hash
4. **Ancoragem (opcional)**: Hash é ancorado no smart contract Anchor em Mainnet
5. **Verificação**: Qualquer terceiro pode verificar integridade e assinatura

---

## 🗂️ Estrutura de Pastas

```
blockchain/
├── app/                          # 📦 Pacote principal da aplicação
│   ├── __init__.py
│   ├── main.py                  # 🚀 Ponto de entrada FastAPI
│   │
│   ├── core/                    # 🔧 Núcleo da aplicação
│   │   ├── __init__.py
│   │   ├── database.py          # Configuração SQLAlchemy
│   │   ├── hashing.py           # SHA-256 hashing
│   │   ├── security.py          # ECDSA signing/verification
│   │   └── settings.py          # Variáveis de ambiente
│   │
│   ├── models/                  # 🗄️ Modelos SQLAlchemy (ORM)
│   │   ├── __init__.py
│   │   ├── manifest.py          # Modelo de manifesto
│   │   └── record.py            # Modelo de registro operacional
│   │
│   ├── schemas/                 # 📝 Schemas Pydantic (validação/serialização)
│   │   ├── __init__.py
│   │   ├── auth.py              # Auth payload (public_key, signature)
│   │   ├── common.py            # Schemas reutilizáveis
│   │   ├── manifest.py          # Request/response manifesto
│   │   ├── record.py            # Request/response registro
│   │   └── verification.py      # Verificação independente
│   │
│   ├── crud/                    # 🔌 CRUD operations (database)
│   │   ├── __init__.py
│   │   ├── manifest.py          # Operações de manifesto
│   │   └── record.py            # Operações de registro
│   │
│   ├── services/                # 💼 Lógica de negócio
│   │   ├── __init__.py
│   │   ├── blockchain_service.py # Integração Web3/Mainnet
│   │   ├── manifest_service.py   # Regras de manifesto
│   │   ├── record_service.py     # Regras de registro
│   │   └── verification_service.py # Verificação criptográfica
│   │
│   └── routers/                 # 🛣️ Endpoints FastAPI
│       ├── __init__.py
│       ├── health.py            # GET /health
│       ├── manifests.py         # POST/GET manifestos
│       ├── records.py           # POST/GET registros
│       └── verification.py      # POST para verificação independente
│
├── contracts/                   # 📄 Smart Contracts
│   └── Anchor.sol              # Contrato Ethereum Mainnet (Solidity)
│
├── cli_user.py                 # 💻 CLI interativa para testagem de blockchain
├── verify.py                   # ✅ Script independente de verificação
├── pyproject.toml              # 📦 Dependências e metadados
└── README.md                   # 📖 Esta documentação
```

---

## 💻 Linguagens e Tecnologias

### Backend API
| Tecnologia | Versão | Propósito |
|-----------|--------|----------|
| **Python** | 3.12+ | Linguagem principal |
| **FastAPI** | 0.136.0 | Framework REST API |
| **SQLAlchemy** | 2.0.49 | ORM para SQLite |
| **Pydantic** | 2.13+ | Validação de dados |
| **Web3.py** | 7.15.0 | Integração Ethereum |
| **ECDSA** | 0.19.2 | Assinatura digital |

### Blockchain
| Tecnologia | Propósito |
|-----------|----------|
| **Solidity** | Smart contract de ancoragem |
| **Ethereum Mainnet** | Rede principal para ancoragem |
| **Smart Contract Anchor.sol** | Registra imutavelmente hashes SHA-256 |

### Ferramentas & Gestão
| Ferramenta | Propósito |
|-----------|----------|
| **UV** | Gerenciador de pacotes Python |
| **SQLite** | Banco de dados operacional |
| **Rich** | Output formatado em terminal |

---

## 🔐 Componentes Principais

### 1. **Core / Security** (`app/core/`)
- **`security.py`**: Funções ECDSA (geração de chaves, assinatura, verificação)
- **`hashing.py`**: Hash SHA-256 para payloads
- **`database.py`**: Setup SQLAlchemy + SQLite
- **`settings.py`**: Carregamento de variáveis de ambiente

### 2. **Models** (`app/models/`)
- **`manifest.py`**: Modelo ORM para manifestos (metadados de lote)
- **`record.py`**: Modelo ORM para registros operacionais

### 3. **Schemas** (`app/schemas/`)
- **`auth.py`**: Schema para autenticação (public_key + signature)
- **`manifest.py`**: Validação de payload de manifesto
- **`record.py`**: Validação de payload de registro
- **`verification.py`**: Schema para verificação independente

### 4. **Services** (`app/services/`)
- **`blockchain_service.py`**: Integração com Web3/Mainnet, ancoragem de hashes
- **`manifest_service.py`**: Regras de negócio para manifestos
- **`record_service.py`**: Regras de negócio para registros
- **`verification_service.py`**: Validação criptográfica

### 5. **Routers/Endpoints** (`app/routers/`)
- `GET /health` - Status da API
- `POST /manifests` - Criar novo manifesto
- `GET /manifests/{id}` - Obter manifesto
- `POST /records` - Criar novo registro
- `POST /verify` - Verificação independente

### 6. **Smart Contract** (`contracts/Anchor.sol`)
```solidity
// Contrato minimalista de ancoragem
// - Permite apenas uma vez por hash (evita duplicatas)
// - Emite evento com hash, manifestId e endereço ancorador
// - Dados imutáveis para auditoria
```

### 7. **CLI Interativa** (`cli_user.py`)
Interface de linha de comando interativa e amigável para testar o sistema:
- 📋 Criar Manifestos (novo lote de cerveja)
- 📝 Criar Registros (operações de transformação)
- ℹ️ Ver Informações do Sistema
- 🔐 Assinatura ECDSA automática com sua chave privada

### 8. **Verificador Independente** (`verify.py`)
- Carrega payload JSON
- Recomputa hash SHA-256
- Valida assinatura ECDSA
- Verifica ancoragem no blockchain (opcional)

---

## 🚀 Quick Start

### 1. Instalação

```bash
# Crie e ative ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: venv\Scripts\activate (Windows)

# Instale dependências
pip install -e .
```

### 2. Configuração (`.env`)

```env
MAINNET_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
CONTRACT_ADDRESS=0x...
PRIVATE_KEY_FOR_DEPLOY=0x...
```

### 3. Iniciar API

```bash
fastapi dev
# Acesse: http://127.0.0.1:8000/docs
```

### 4. Usar CLI Interativa

```bash
# Executar a aplicação CLI interativa
python cli_user.py

# Você será guiado por um menu interativo para:
# 1. Criar Manifestos (novos lotes)
# 2. Criar Registros (operações de transformação)
# 3. Ver Informações do Sistema
# 4. Sair
```

**Exemplo de uso (interativo):**
```
🍺 Rastreador de Cerveja Artesanal
Sistema de Blockchain para Supply Chain

O que deseja fazer?

  1 - Criar Manifesto (novo lote)
  2 - Criar Registro (operação)
  3 - Informações do Sistema
  4 - Sair

Escolha: 1
```

### 5. Verificar Integridade

```bash
python verify.py \
  --payload-file payload.json \
  --signature 0x... \
  --public-key 0x... \
  --expected-hash 0x... \
  --tx-hash 0x...
```

---

## 📊 Fluxo de Operação Típico

```Você exporta chaves do Metamask
   └─> Chave pública: compartilhável
   └─> Chave privada: mantém segura (apenas localmente)

2. Você cria manifesto (lote de produção) via CLI
   └─> FastAPI recebe payload + auth (signature)
   └─> Servidor valida assinatura com public_key
   └─> Armazena em SQLite com hash SHA-256
   └─> Âncora hash em Ethereum Mainnet usando PRIVATE_KEY_FOR_DEPLOY

3. Distribuidor cria registro (operação)
   └─> Mesmo fluxo: validação → armazenamento → ancoragem

4. Consumidor verifica integridade
   └─> Executa verify.py com payload + signature + hash esperado
   └─> Recomputa hash localmente
   └─> Valida assinatura
   └─> Verifica existência em blockchain
   └─> Verifica existência em blockchain (opcional)
   └─> Resultado: integridade confirmada ✅
```

---

## 🔍 Pontos-chave da Arquitetura

| Aspecto | Implementação |
|--------|-------------|
| **Armazenamento** | SQLite (off-chain) + Ethereum Mainnet (on-chain hashes) |
| **Autenticação** | ECDSA (chaves públicas/privadas) |
| **Integridade** | SHA-256 hashing + assinatura digital |
| **Verificação** | Script independente sem confiar no servidor |
| **Imutabilidade** | Dados ancorados no blockchain (read-only) |
| **Escalabilidade** | Apenas hashes no blockchain (não dados brutos) |

---

## 📝 Notas sobre Mainnet

⚠️ **CUIDADO**: Mainnet usa ETH real. Use com prudência!
### Setup Necessário:

1. **Conta Metamask**: Crie wallet no [Metamask](https://metamask.io/)
2. **Chave RPC Mainnet**: Obtenha em [Alchemy](https://www.alchemy.com/) ou [Infura](https://infura.io/)
3. **ETH para gas fees**: Certifique-se de ter ETH suficiente na wallet
4. **Deploy do Contrato**: Implante `contracts/Anchor.sol` em Mainnet e registre endereço em `.env`
5. **Chave Privada para Deploy**: 
   - Crie wallet dedicada para operações automáticas (recomendado)
   - Configure `PRIVATE_KEY_FOR_DEPLOY=0x...` no `.env`
   - Carregue ETH nessa wallet para transações

### Segurança:

- ⚠️ **NUNCA** comita `.env` com chaves privadas em Git
- ⚠️ **PROTEJA** sua `PRIVATE_KEY_FOR_DEPLOY` - qualquer pessoa com ela pode mover seus fundos
- ✅ Use diferentes wallets: uma para você (Metamask) e outra para servidor (PRIVATE_KEY_FOR_DEPLOY)
- **Backup seguro**: Proteja sua `PRIVATE_KEY_FOR_DEPLOY` - qualquer pessoa com ela pode mover seus fundos

---

## 📚 Estrutura Resumida de Responsabilidades

```
FastAPI (main.py)
├─ Recebe requisições HTTP
├─ Valida schemas Pydantic
└─ Delega para Services

Services (lógica de negócio)
├─ Verifica assinaturas
├─ Computa hashes
├─ Orquestra blockchain
└─ Delegam para CRUD

CRUD (acesso a dados)
├─ Queries ao SQLite
├─ Insere/atualiza registros
└─ Retorna DTOs

Core (utilidades)
├─ Segurança (ECDSA)
├─ Hashing (SHA-256)
├─ Settings (.env)
└─ Database connection

Smart Contract (blockchain)
└─ Armazena imutavelmente hashes
```

---

## 🎯 Resumo

Este projeto demonstra uma **arquitetura moderna de rastreabilidade** que equilibra:
- ✅ **Performance**: Dados operacionais rápidos em SQLite
- ✅ **Segurança**: Assinaturas criptográficas em cada operação
- ✅ **Confiança**: Verificação independente sem terceiros
- ✅ **Imutabilidade**: Hashes ancorados no blockchain público

Ideal para **sistemas de cadeia de suprimentos acadêmicos** e produção artesanal com requisitos de rastreabilidade e autenticidade.
