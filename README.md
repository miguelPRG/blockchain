# Esboco do Relatorio

## Sistema Implementado

Este projeto implementa um sistema hibrido de rastreabilidade de cadeia de fornecimento com dados operacionais guardados off-chain e provas de integridade ancoradas na blockchain Sepolia.

O sistema segue quatro componentes principais:

- Users: Alice, Bob e Charlie, cada um com uma wallet Ethereum e uma chave privada usada para assinar operacoes.
- Supply Chain Manager: backend FastAPI que valida pedidos, assinaturas, quantidades e transacoes blockchain.
- Repository: base de dados SQLite onde ficam guardados manifestos, records, assinaturas, hashes e referencias para transacoes.
- Blockchain: contrato inteligente `Anchor.sol`, usado apenas para guardar hashes criptograficos dos manifestos e records.

## Roles e Operacoes

Foram definidos tres utilizadores:

- Alice: producer. Cria manifestos e records `PRODUCED`.
- Bob: transporter. Cria records `TRANSFER`.
- Charlie: receiver. Cria records `RECEIVED`, usados como certificacao final de rececao.

Todos os utilizadores podem verificar manifestos e records especificos.

## Fluxo Principal

1. Alice cria um manifesto de bens com tipo, quantidade, origem, ingredientes, timestamp e outros metadados.
2. O manifesto e assinado por Alice e pelo Supply Chain Manager.
3. O hash canonico do manifesto e ancorado na blockchain.
4. Opcionalmente, e criado um record `PRODUCED` associado ao manifesto.
5. Bob cria um record `TRANSFER`, indicando a quantidade transferida.
6. O sistema valida se existe quantidade disponivel no repositorio.
7. O record `TRANSFER` e assinado por Bob e pelo Supply Chain Manager, guardado off-chain e ancorado na blockchain.
8. Depois da transferencia, e criado um novo manifesto derivado para Bob, com a quantidade restante.
9. Charlie confirma a rececao atraves de um record `RECEIVED`, referenciando o record `TRANSFER` de Bob.
10. O record `RECEIVED` e assinado por Charlie e pelo Supply Chain Manager, guardado off-chain e ancorado na blockchain.

## Assinaturas e Autenticacao

Cada manifesto ou record usa um envelope de assinatura comum:

- `payload`: dados funcionais do manifesto ou record.
- `auth.public_key`: chave publica do user.
- `auth.signature`: assinatura do user sobre o hash do payload.
- `auth.manager_public_key`: chave publica do Supply Chain Manager.
- `auth.manager_signature`: assinatura do manager sobre o mesmo hash.
- `signed_anchor_tx`: transacao blockchain assinada localmente pelo user.

As chaves privadas nunca sao enviadas ao backend. O CLI assina localmente o payload e a transacao blockchain. O backend recebe apenas chaves publicas, assinaturas e transacoes ja assinadas.

## Integridade e Blockchain

O sistema calcula um hash SHA-256 sobre uma representacao JSON canonica de cada manifesto ou record. Esse hash e:

- usado para validar as assinaturas digitais;
- guardado no repositorio;
- enviado para o contrato inteligente `Anchor.sol`;
- verificado novamente quando o dado e consultado.

Na blockchain fica apenas o hash, o timestamp e o identificador do item. Os dados completos permanecem off-chain.

## Verificacao

A verificacao de um manifesto ou record especifico inclui:

- recomputar o hash do payload guardado no repositorio;
- comparar o hash recomputado com o hash guardado;
- verificar a assinatura do user;
- verificar a assinatura do Supply Chain Manager;
- obter e decodificar a transacao blockchain;
- confirmar que o hash ancorado na blockchain corresponde ao payload;
- confirmar que o item ID da transacao corresponde ao manifesto ou record.

Se algum campo for alterado diretamente na base de dados, a recomputacao do hash deixa de coincidir com a assinatura e com a prova blockchain. Assim, discrepancias tornam-se detetaveis.

## Consistencia de Quantidades

O backend rejeita operacoes que excedam a quantidade disponivel.

Na transferencia, Bob apenas pode transferir uma quantidade menor ou igual a quantidade disponivel no manifesto. Na rececao, Charlie nao escolhe manualmente a quantidade: o CLI obtem o record `TRANSFER` de Bob e preenche automaticamente o `manifest_id` e a quantidade recebida.

Isto reduz erros manuais e garante que o record `RECEIVED` certifica exatamente a transferencia criada por Bob.

## Configuracao

As wallets sao configuradas por ficheiros `.env`.

No backend:

```env
SEPOLIA_RPC_URL=...
SUPPLY_MANAGER_ADDRESS=0x...
```

No cliente:

```env
ALICE_ADDRESS=0x...
BOB_ADDRESS=0x...
CHARLIE_ADDRESS=0x...
SUPPLY_MANAGER_ADDRESS=0x...
CONTRACT_ADDRESS=0x...
```

O backend nao precisa das wallets de Alice, Bob ou Charlie. O cliente usa esses enderecos para validar se a private key introduzida corresponde ao personagem escolhido. O backend precisa do endereco publico do Supply Chain Manager para validar que a assinatura do manager pertence a entidade correta.

## Evidencias a Anexar

Para a entrega, devem ser anexadas evidencias concretas:

- screenshot ou log da criacao de um manifesto;
- screenshot ou log de um record `PRODUCED`;
- screenshot ou log de um record `TRANSFER`;
- screenshot ou log de um record `RECEIVED`;
- hashes dos payloads;
- assinaturas do user e do manager;
- hashes das transacoes Sepolia;
- links Etherscan das transacoes;
- exemplo de verificacao valida;
- exemplo de tampering na base de dados e verificacao invalida.

## Decisoes de Implementacao

O sistema trata `RECEIVED` como certificacao final de entrega. Esta decisao mantem o fluxo simples e verificavel: Charlie, enquanto destinatario, assina a confirmacao de rececao, que inclui referencia para a transferencia de Bob, quantidade recebida, timestamp, assinaturas e prova blockchain.

O Supply Chain Manager nao e considerado confiavel. Por isso, a validade do sistema nao depende apenas da base de dados ou do backend. Qualquer parte pode recomputar hashes, verificar assinaturas e comparar os dados com a blockchain.
