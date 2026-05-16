// SPDX-License-Identifier: MIT
pragma solidity >=0.8.35 <0.9.0;

contract Anchor {
    mapping(bytes32 => bool) public anchoredHashes;
    mapping(bytes32 => uint256) public hashTimestamps;
    mapping(bytes32 => address) public hashCreators;
    mapping(bytes32 => string) public hashItemIds;

    event HashAnchored(
        bytes32 indexed payloadHash,
        address indexed creator,
        uint256 timestamp,
        string itemId
    );

    function anchorHash(bytes32 _payloadHash, uint256 _timestamp, string calldata _itemId) external {
        require(!anchoredHashes[_payloadHash], "Hash already anchored");
        require(bytes(_itemId).length > 0, "Item ID required");

        anchoredHashes[_payloadHash] = true;
        hashTimestamps[_payloadHash] = _timestamp;
        hashCreators[_payloadHash] = msg.sender;
        hashItemIds[_payloadHash] = _itemId;

        emit HashAnchored(_payloadHash, msg.sender, _timestamp, _itemId);
    }

    function isAnchored(bytes32 _payloadHash) external view returns (bool) {
        return anchoredHashes[_payloadHash];
    }
    
    function getAnchorDetails(bytes32 _payloadHash) external view returns (bool exists, uint256 timestamp, address creator, string memory itemId) {
        return (anchoredHashes[_payloadHash], hashTimestamps[_payloadHash], hashCreators[_payloadHash], hashItemIds[_payloadHash]);
    }
}