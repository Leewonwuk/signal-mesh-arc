// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @title AlphaLoopAgentRegistry
/// @author Leewonwuk (AlphaLoop)
/// @notice Minimal ERC-8004-aligned agent identity registry for AlphaLoop.
///         Four wallet identities emit `AgentRegistered` events pointing to
///         their `registration-v1` cards hosted at
///         https://signal-mesh.vercel.app/.well-known/agent-card/<role>.json
/// @dev    Intentionally small (< 60 lines) — the point of this contract is
///         not to be a universal registry; it is to put four verifiable
///         on-chain events on Arc testnet that a judge can grep for on
///         Arc Explorer and cross-reference against the served agent cards.
contract AlphaLoopAgentRegistry {
    event AgentRegistered(
        uint256 indexed agentId,
        address indexed wallet,
        string role,
        string agentURI,
        bytes32 contentHash
    );

    event AgentUpdated(
        uint256 indexed agentId,
        address indexed wallet,
        string agentURI,
        bytes32 contentHash
    );

    struct Agent {
        address wallet;
        string role;
        string agentURI;
        bytes32 contentHash;
        uint64 registeredAt;
    }

    mapping(uint256 => Agent) public agents;
    uint256 public nextAgentId = 1;
    address public operator;
    string public constant SPEC = "https://eips.ethereum.org/EIPS/eip-8004#registration-v1";
    string public constant PROJECT = "AlphaLoop";

    modifier onlyOperator() {
        require(msg.sender == operator, "not operator");
        _;
    }

    constructor() {
        operator = msg.sender;
    }

    function registerAgent(
        address wallet,
        string calldata role,
        string calldata agentURI,
        bytes32 contentHash
    ) external onlyOperator returns (uint256 agentId) {
        agentId = nextAgentId++;
        agents[agentId] = Agent({
            wallet: wallet,
            role: role,
            agentURI: agentURI,
            contentHash: contentHash,
            registeredAt: uint64(block.timestamp)
        });
        emit AgentRegistered(agentId, wallet, role, agentURI, contentHash);
    }

    function updateAgent(
        uint256 agentId,
        string calldata agentURI,
        bytes32 contentHash
    ) external onlyOperator {
        Agent storage a = agents[agentId];
        require(a.wallet != address(0), "unknown agentId");
        a.agentURI = agentURI;
        a.contentHash = contentHash;
        emit AgentUpdated(agentId, a.wallet, agentURI, contentHash);
    }

    function transferOperator(address newOperator) external onlyOperator {
        require(newOperator != address(0), "zero addr");
        operator = newOperator;
    }
}
