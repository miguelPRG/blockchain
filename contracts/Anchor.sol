// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title Anchor - contrato minimalista de ancoragem de hash
/// @notice Armazena hashes de registro imutáveis para verificação independente fora da cadeia.
contract Anchor {
    event HashAnchored(bytes32 indexed hashValue, string indexed manifestId, address indexed anchoredBy);

    mapping(bytes32 => bool) public anchored;

    function anchorHash(bytes32 _hash, string memory _manifestId) external {
        require(!anchored[_hash], "Hash already anchored");
        anchored[_hash] = true;
        emit HashAnchored(_hash, _manifestId, msg.sender);
    }
}
