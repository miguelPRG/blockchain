# Rastreamento de Cadeia de Suprimentos em Blockchain - Cerveja Artesanal

Arquitetura híbrida para rastreabilidade acadêmica de cadeia de suprimentos:
- Armazenamento operacional fora da cadeia em SQLite.
- Ancoragem de hash na cadeia em Ethereum Sepolia.
- Autenticação mútua com assinaturas ECDSA.
- Verificação independente de integridade sem confiar no gerenciador.e Suprimentos

## Instalação

1. Crie e ative um ambiente virtual Python 3.14+.
2. Preencha `.env`:
   - `SEPOLIA_RPC_URL`: seu endpoint Sepolia do Alchemy ou Chainstack.
   - `CONTRACT_ADDRESS`: endereço implantado de `Anchor.sol`.
   - `PRIVATE_KEY_FOR_DEPLOY`: chave privada da conta usada para tx de ancoragem.

## Executar API

- Inicie o servidor:
  - `uvicorn app.main:app --reload`
- Abra a documentação:
  - [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Os logs de inicialização exibem o status de conexão Sepolia.

## Notas sobre Sepolia

- Crie uma conta gratuita do Alchemy e gere uma chave HTTP RPC Sepolia.
- Adicione a chave a `.env` como `SEPOLIA_RPC_URL`.
- Obtenha ETH de teste em uma torneira Sepolia (Alchemy, Infura ou torneira pública), depois financie sua conta de ancoragem.
- Implante `contracts/Anchor.sol` e coloque o endereço do contrato implantado em `.env`.

## Uso da CLI

- Gerar chaves:
  - `python cli_user.py gen-keys`
- Criar manifesto:
  - `python cli_user.py create-manifest --manifest-id lot-001 --quantity 1000 --ingredients agua malte lupulo --origin "Minas Gerais" --creator <address> --public-key <pub> --private-key <priv>`
- Criar registro:
  - `python cli_user.py create-record --record-id rec-001 --record-type PRODUCED --manifest-id lot-001 --quantity 1000 --user <address> --public-key <pub> --private-key <priv>`

## Script de Verificação Independente

Use `verify.py` com JSON de carga e evidência criptográfica:

`python verify.py --payload-file payload.json --signature <sig> --public-key <pub> --expected-hash <hash> --tx-hash <tx>`
