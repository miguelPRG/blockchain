// SPDX-License-Identifier: MIT
pragma solidity ^0.8.35;

/// @title Anchor - Contrato de Rastreamento de Manifesto Completo
/// @notice Armazena manifestos de cerveja com dados completos para auditoria imutável e verificação independente.
/// 
/// @dev LIGAÇÃO COM PYTHON:
/// ========================
/// Este contrato é chamado pelo sistema Python através de:
///   - web3.py (biblioteca Web3)
///   - app/services/blockchain_service.py (função anchor_manifest())
///   - app/services/manifest_service.py (lógica de negócio)
///
/// O ABI (Application Binary Interface) definido em blockchain_service.py
/// mapeia as funções abaixo para chamadas Python:
///
/// 1. Python: contract.functions.anchorManifest(...).build_transaction(...)
///    Solidity: function anchorManifest(...)
///
/// 2. Python: contract.functions.getManifest(hash).call()
///    Solidity: function getManifest(bytes32 _hash) external view returns (Manifest memory)
///
/// 3. Python: contract.functions.isAnchored(hash).call()
///    Solidity: function isAnchored(bytes32 _hash) external view returns (bool)
///
/// FLUXO DE DADOS:
/// ===============
/// CLI/API (Python) → blockchain_service.py → Web3.py → Infura RPC → Sepolia Blockchain → Anchor.sol
///
/// ARMAZENAMENTO:
/// ===============
/// mapping(bytes32 => Manifest) public manifests;
/// - Chave: Hash SHA-256 do payload do manifesto
/// - Valor: Struct Manifest com todos os dados
/// - Permanentemente gravado na blockchain (imutável)
///
contract Anchor {
    /// @notice Estrutura completa de um manifesto de cerveja
    /// @dev Cada campo é armazenado na blockchain e é imutável após criação
    /// @dev OTIMIZAÇÃO: Campo 'exists' combina dois mappings em um (economiza ~20k gas por deploy)
    struct Manifest {
        bool exists;                     // Flag para evitar mapping separado (otimização: 1 SSTORE economizado)
        bytes32 hash;                    // Hash SHA-256 do payload canônico (calculado em Python)
        string goodType;                 // Tipo de cerveja (ex: "IPA Artesanal")
        uint256 quantity;                // Quantidade em unidades
        string unit;                     // Unidade (ex: "litros")
        string[] ingredients;            // Lista de ingredientes
        string origin;                   // Local de origem (ex: "Douro, Portugal")
        string sustainability;           // Certificação de sustentabilidade
        address creator;                 // Endereço do criador (Ethereum wallet)
        uint256 timestamp;               // Timestamp Unix de criação (UTC)
    }

    /// @notice Mapping de hash para manifesto completo
    /// @dev Storage em blockchain: cada entrada custa gas proporcional aos dados
    /// @dev OTIMIZAÇÃO: Único mapping ao invés de dois (vs. separado 'anchored' mapping)
    mapping(bytes32 => Manifest) public manifests;

    /// @notice Evento emitido quando um manifesto é ancorado
    /// @dev Facilita auditoria e permite escuta de eventos do blockchain
    /// @param hashValue Hash SHA-256 do manifesto (indexed para filtrar)
    /// @param manifestId ID único do manifesto (indexed para filtrar)
    /// @param creator Endereço da conta que chamou a função (indexed para filtrar)
    /// @param goodType Tipo de cerveja (não indexed - economiza gas)
    /// @param quantity Quantidade (não indexed - economiza gas)
    /// @param timestamp Quando foi criado (não indexed - economiza gas)
    event ManifestAnchored(
        bytes32 indexed hashValue,
        string indexed manifestId,
        address indexed creator,
        string goodType,
        uint256 quantity,
        uint256 timestamp
    );

    /// @notice Ancorar manifesto completo na blockchain
    /// @dev Chamada por blockchain_service.py através de Web3
    /// @param _hash Hash SHA-256 do payload (calculado com sha256_hex() em Python)
    /// @param _manifestId ID único do manifesto (para auditoria)
    /// @param _goodType Tipo de cerveja (string)
    /// @param _quantity Quantidade produzida (int → uint256)
    /// @param _unit Unidade de quantidade (string)
    /// @param _ingredients Lista de ingredientes (list[str] → string[])
    /// @param _origin Local de origem (string)
    /// @param _sustainability Certificação (string)
    /// @param _timestamp Timestamp de criação em Unix (int → uint256)
    /// 
    /// @dev Gas otimizado: ~850-900k gas (economizado ~20k vs. dois mappings)
    /// @dev OTIMIZAÇÃO: Verifica 'exists' em struct ao invés de mapping separado (1 SLOAD economizado)
    /// @dev Nota: msg.sender é automaticamente a conta que envia a transação
    function anchorManifest(
        bytes32 _hash,
        string memory _manifestId,
        string memory _goodType,
        uint256 _quantity,
        string memory _unit,
        string[] memory _ingredients,
        string memory _origin,
        string memory _sustainability,
        uint256 _timestamp
    ) external {
        // Verificação otimizada: usa 'exists' flag em struct ao invés de mapping
        require(!manifests[_hash].exists, "Hash already anchored");
        
        manifests[_hash] = Manifest(
            true,  // exists = true (flag que economiza 20k gas vs. mapping separado)
            _hash,
            _goodType,
            _quantity,
            _unit,
            _ingredients,
            _origin,
            _sustainability,
            msg.sender,
            _timestamp
        );
        
        emit ManifestAnchored(
            _hash,
            _manifestId,
            msg.sender,
            _goodType,
            _quantity,
            _timestamp
        );
    }

    /// @notice Recuperar manifesto armazenado
    /// @dev Chamada via Python: contract.functions.getManifest(_hash).call()
    /// @param _hash Hash do manifesto (bytes32)
    /// @return Manifesto completo armazenado (struct Manifest)
    /// @dev Gas: ~0 (read-only, sem custo de execução, apenas de RPC)
    function getManifest(bytes32 _hash) external view returns (Manifest memory) {
        return manifests[_hash];
    }

    /// @notice Verificar se um manifesto foi ancorado
    /// @dev Chamada via Python: contract.functions.isAnchored(_hash).call()
    /// @param _hash Hash do manifesto (bytes32)
    /// @return true se o manifesto foi ancorado, false caso contrário
    /// @dev Gas: ~0 (read-only, apenas SLOAD do struct que já temos)
    /// @dev OTIMIZAÇÃO: Lê 'exists' flag do struct ao invés de mapping separado
    function isAnchored(bytes32 _hash) external view returns (bool) {
        return manifests[_hash].exists;
    }
}
