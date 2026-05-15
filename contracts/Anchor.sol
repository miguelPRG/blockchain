// SPDX-License-Identifier: MIT
pragma solidity >=0.8.35 <0.9.0;


contract Anchor {
    struct Manifest {
        bool exists;
        bytes32 _payload_hash;
        string manifestId;
        string goodType;
        uint256 quantity;
        string unit;
        string[] ingredients;
        string origin;
        string sustainability;
        address creator;
        uint256 timestamp;
    }

    struct Record {
        bool exists;
        bytes32 _payload_hash;
        string recordId;
        string manifestId;
        string recordType;
        uint256 quantity;
        string unit;
        address user;
        uint256 timestamp;
    }

    // Mappings Corrigidos
    mapping(string => Manifest) public manifestIdToManifest;
    mapping(bytes32 => string) public payloadHashToManifestId; // Removido '_' inicial para bater com o uso
    mapping(string => Record) public recordIdToRecord;
    mapping(bytes32 => string) public payloadHashToRecordId; // Removido '_' inicial para bater com o uso

    event ManifestCreated(
        string indexed manifestId,
        bytes32 indexed _payload_hash,
        address indexed creator,
        string goodType,
        uint256 quantity,
        uint256 timestamp
    );

    event RecordCreated(
        string indexed recordId,
        string indexed manifestId,
        bytes32 indexed _payload_hash,
        string recordType,
        address user,
        uint256 timestamp
    );

    event RecordRejected(
        string indexed recordId,
        string indexed manifestId,
        string reason,
        address user
    );

    function createManifest(
        string memory _manifestId,
        bytes32 _payload_hash,
        string memory _goodType,
        uint256 _quantity,
        string memory _unit,
        string[] memory _ingredients,
        string memory _origin,
        string memory _sustainability,
        uint256 _timestamp
    ) external {
        require(!manifestIdToManifest[_manifestId].exists, "Manifest ID already exists");
        // Ajustado para o nome correto do mapping
        require(bytes(payloadHashToManifestId[_payload_hash]).length == 0, "Payload hash already used");

        manifestIdToManifest[_manifestId] = Manifest(
            true,
            _payload_hash,
            _manifestId,
            _goodType,
            _quantity,
            _unit,
            _ingredients,
            _origin,
            _sustainability,
            msg.sender,
            _timestamp
        );

        // Ajustado para o nome correto do mapping
        payloadHashToManifestId[_payload_hash] = _manifestId;

        emit ManifestCreated(
            _manifestId,
            _payload_hash,
            msg.sender,
            _goodType,
            _quantity,
            _timestamp
        );
    }

    function createRecord(
        string memory _recordId,
        string memory _manifestId,
        bytes32 _payload_hash,
        string memory _recordType,
        uint256 _quantity,
        string memory _unit,
        uint256 _timestamp
    ) external {
        if (!manifestIdToManifest[_manifestId].exists) {
            emit RecordRejected(
                _recordId,
                _manifestId,
                "Manifest does not exist on blockchain",
                msg.sender
            );
            revert("Manifest does not exist on blockchain");
        }

        require(!recordIdToRecord[_recordId].exists, "Record ID already exists");
        // Ajustado para o nome correto do mapping
        require(bytes(payloadHashToRecordId[_payload_hash]).length == 0, "Record payload hash already used");

        recordIdToRecord[_recordId] = Record(
            true,
            _payload_hash,
            _recordId,
            _manifestId,
            _recordType,
            _quantity,
            _unit,
            msg.sender,
            _timestamp
        );

        // Ajustado para o nome correto do mapping
        payloadHashToRecordId[_payload_hash] = _recordId;

        emit RecordCreated(
            _recordId,
            _manifestId,
            _payload_hash,
            _recordType,
            msg.sender,
            _timestamp
        );
    }

    function manifestExists(string memory _manifestId) external view returns (bool) {
        return manifestIdToManifest[_manifestId].exists;
    }

    function getManifestById(string memory _manifestId) external view returns (Manifest memory) {
        require(manifestIdToManifest[_manifestId].exists, "Manifest not found");
        return manifestIdToManifest[_manifestId];
    }

    function getRecordById(string memory _recordId) external view returns (Record memory) {
        require(recordIdToRecord[_recordId].exists, "Record not found");
        return recordIdToRecord[_recordId];
    }

    function isAnchored(bytes32 _payload_hash) external view returns (bool) {
        // Ajustado para o nome correto do mapping
        return bytes(payloadHashToManifestId[_payload_hash]).length > 0;
    }
}