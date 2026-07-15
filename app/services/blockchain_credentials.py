"""
VettedMe Blockchain Integration

Stores verifiable credentials on Ethereum/Polygon for:
- Decentralized storage (immutable, permanent)
- User ownership (self-sovereign identity)
- Cross-platform portability
- Tamper-proof audit trail

Supported Networks:
- Ethereum Mainnet (production, high cost)
- Polygon (recommended: low gas fees, fast)
- Ethereum Goerli (testnet)
- Polygon Mumbai (testnet)

Smart Contract: ERC-721 NFT-based credentials
Standard: W3C Verifiable Credentials + EIP-721
"""

import os
import json
import hashlib
from typing import Dict, Optional
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.orm import Session

# For production, install: pip install web3 eth-account
# from web3 import Web3
# from eth_account import Account

class BlockchainCredentialService:
    """
    Service for storing and verifying credentials on blockchain.
    
    Architecture:
    1. Credential is verified off-chain (via VettedMe)
    2. Hash of credential + signature is stored on-chain
    3. Full credential data remains in VettedMe database
    4. Blockchain serves as tamper-proof proof-of-existence
    
    This hybrid approach:
    - Maintains privacy (no PII on public chain)
    - Provides immutability (blockchain proof)
    - Reduces gas costs (only hash stored)
    - Enables revocation (off-chain check)
    """
    
    def __init__(self, network: str = "polygon"):
        """
        Initialize blockchain service.
        
        Args:
            network: "ethereum", "polygon", "goerli", or "mumbai"
        """
        self.network = network
        self.enabled = os.getenv("BLOCKCHAIN_ENABLED", "false").lower() == "true"
        
        # Network configurations
        self.networks = {
            "ethereum": {
                "name": "Ethereum Mainnet",
                "rpc_url": "https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY",
                "chain_id": 1,
                "explorer": "https://etherscan.io"
            },
            "polygon": {
                "name": "Polygon",
                "rpc_url": "https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY",
                "chain_id": 137,
                "explorer": "https://polygonscan.com"
            },
            "goerli": {
                "name": "Goerli Testnet",
                "rpc_url": "https://eth-goerli.g.alchemy.com/v2/YOUR_KEY",
                "chain_id": 5,
                "explorer": "https://goerli.etherscan.io"
            },
            "mumbai": {
                "name": "Polygon Mumbai Testnet",
                "rpc_url": "https://polygon-mumbai.g.alchemy.com/v2/YOUR_KEY",
                "chain_id": 80001,
                "explorer": "https://mumbai.polygonscan.com"
            }
        }
        
        # Smart contract address (deployed once per network)
        self.contract_address = os.getenv(
            f"VETTEDME_CONTRACT_{network.upper()}",
            "0x0000000000000000000000000000000000000000"
        )
        
        # In production, initialize Web3
        # rpc_url = self.networks[network]["rpc_url"]
        # self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        # self.contract = self.w3.eth.contract(
        #     address=self.contract_address,
        #     abi=VETTEDME_CREDENTIAL_ABI
        # )
    
    def mint_credential_nft(
        self,
        passport_id: UUID,
        badge_id: UUID,
        credential_hash: str,
        signature: str
    ) -> Dict:
        """
        Mint an NFT representing a verified credential on-chain.
        
        Process:
        1. Compute credential hash (SHA256)
        2. Sign hash with VettedMe private key
        3. Submit transaction to smart contract
        4. Return transaction hash + token ID
        
        Args:
            passport_id: UUID of the passport
            badge_id: UUID of the credential badge
            credential_hash: SHA256 hash of credential data
            signature: Ed25519 signature from VettedMe
        
        Returns:
            dict: {
                "success": bool,
                "tx_hash": str,
                "token_id": int,
                "explorer_url": str,
                "network": str,
                "gas_used": int,
                "gas_price_gwei": float
            }
        """
        if not self.enabled:
            # Development mode - return mock response
            return {
                "success": True,
                "tx_hash": f"0x{hashlib.sha256(str(badge_id).encode()).hexdigest()}",
                "token_id": int(str(badge_id)[:8], 16) % 1000000,
                "explorer_url": f"{self.networks[self.network]['explorer']}/tx/0x{hashlib.sha256(str(badge_id).encode()).hexdigest()}",
                "network": self.networks[self.network]["name"],
                "gas_used": 85000,
                "gas_price_gwei": 25.0,
                "block_number": 12345678,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        # Production implementation
        # try:
        #     # Get wallet (in production, use secure key management)
        #     private_key = os.getenv("VETTEDME_BLOCKCHAIN_PRIVATE_KEY")
        #     account = Account.from_key(private_key)
        #     
        #     # Prepare transaction
        #     nonce = self.w3.eth.get_transaction_count(account.address)
        #     
        #     # Build transaction
        #     tx = self.contract.functions.mintCredential(
        #         str(passport_id),
        #         str(badge_id),
        #         credential_hash,
        #         signature
        #     ).build_transaction({
        #         'from': account.address,
        #         'nonce': nonce,
        #         'gas': 200000,
        #         'maxFeePerGas': self.w3.to_wei('50', 'gwei'),
        #         'maxPriorityFeePerGas': self.w3.to_wei('2', 'gwei'),
        #     })
        #     
        #     # Sign transaction
        #     signed_tx = self.w3.eth.account.sign_transaction(tx, private_key)
        #     
        #     # Send transaction
        #     tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        #     
        #     # Wait for receipt
        #     receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        #     
        #     # Parse token ID from logs
        #     token_id = self.contract.events.CredentialMinted().process_receipt(receipt)[0]['args']['tokenId']
        #     
        #     return {
        #         "success": True,
        #         "tx_hash": tx_hash.hex(),
        #         "token_id": token_id,
        #         "explorer_url": f"{self.networks[self.network]['explorer']}/tx/{tx_hash.hex()}",
        #         "network": self.networks[self.network]["name"],
        #         "gas_used": receipt['gasUsed'],
        #         "gas_price_gwei": self.w3.from_wei(receipt['effectiveGasPrice'], 'gwei'),
        #         "block_number": receipt['blockNumber']
        #     }
        # 
        # except Exception as e:
        #     return {
        #         "success": False,
        #         "error": str(e)
        #     }
    
    def verify_credential_on_chain(
        self,
        token_id: int
    ) -> Dict:
        """
        Verify a credential exists on-chain and is not revoked.
        
        Args:
            token_id: NFT token ID
        
        Returns:
            dict: {
                "exists": bool,
                "revoked": bool,
                "passport_id": str,
                "badge_id": str,
                "credential_hash": str,
                "minted_at": str,
                "block_number": int
            }
        """
        if not self.enabled:
            # Development mode - return mock response
            return {
                "exists": True,
                "revoked": False,
                "passport_id": "demo-passport-123",
                "badge_id": "demo-badge-456",
                "credential_hash": "0x" + hashlib.sha256(str(token_id).encode()).hexdigest(),
                "minted_at": datetime.now(timezone.utc).isoformat(),
                "block_number": 12345678,
                "network": self.networks[self.network]["name"]
            }
        
        # Production implementation
        # try:
        #     # Query contract
        #     credential_data = self.contract.functions.getCredential(token_id).call()
        #     
        #     return {
        #         "exists": True,
        #         "revoked": credential_data[4],  # revoked field
        #         "passport_id": credential_data[0],
        #         "badge_id": credential_data[1],
        #         "credential_hash": credential_data[2],
        #         "minted_at": datetime.fromtimestamp(credential_data[3], tz=timezone.utc).isoformat(),
        #         "block_number": credential_data[5],
        #         "network": self.networks[self.network]["name"]
        #     }
        # 
        # except Exception as e:
        #     return {
        #         "exists": False,
        #         "error": str(e)
        #     }
    
    def revoke_credential_on_chain(
        self,
        token_id: int,
        reason: str
    ) -> Dict:
        """
        Revoke a credential on-chain.
        
        Note: Revocation is permanent and cannot be undone.
        
        Args:
            token_id: NFT token ID
            reason: Reason for revocation
        
        Returns:
            dict: Transaction result
        """
        if not self.enabled:
            # Development mode
            return {
                "success": True,
                "tx_hash": f"0x{hashlib.sha256(f'revoke-{token_id}'.encode()).hexdigest()}",
                "revoked_at": datetime.now(timezone.utc).isoformat(),
                "reason": reason
            }
        
        # Production implementation
        # Similar to mint_credential_nft but calls revokeCredential(token_id, reason)
    
    def get_passport_credentials_on_chain(
        self,
        passport_id: UUID
    ) -> Dict:
        """
        Get all credentials for a passport from blockchain.
        
        Args:
            passport_id: UUID of the passport
        
        Returns:
            dict: {
                "passport_id": str,
                "total_credentials": int,
                "credentials": list[dict]
            }
        """
        if not self.enabled:
            # Development mode
            return {
                "passport_id": str(passport_id),
                "total_credentials": 2,
                "credentials": [
                    {
                        "token_id": 123456,
                        "badge_type": "IDENTITY",
                        "minted_at": "2026-01-15T10:30:00Z",
                        "revoked": False,
                        "tx_hash": "0x" + hashlib.sha256(b"tx1").hexdigest()
                    },
                    {
                        "token_id": 123457,
                        "badge_type": "HEALTHCARE",
                        "minted_at": "2026-07-01T14:22:00Z",
                        "revoked": False,
                        "tx_hash": "0x" + hashlib.sha256(b"tx2").hexdigest()
                    }
                ]
            }
        
        # Production implementation
        # Query contract for all credentials owned by passport


# ============================================================================
# Smart Contract ABI (for reference)
# ============================================================================

VETTEDME_CREDENTIAL_ABI = """
[
    {
        "inputs": [
            {"internalType": "string", "name": "passportId", "type": "string"},
            {"internalType": "string", "name": "badgeId", "type": "string"},
            {"internalType": "bytes32", "name": "credentialHash", "type": "bytes32"},
            {"internalType": "bytes", "name": "signature", "type": "bytes"}
        ],
        "name": "mintCredential",
        "outputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
        "name": "getCredential",
        "outputs": [
            {"internalType": "string", "name": "passportId", "type": "string"},
            {"internalType": "string", "name": "badgeId", "type": "string"},
            {"internalType": "bytes32", "name": "credentialHash", "type": "bytes32"},
            {"internalType": "uint256", "name": "mintedAt", "type": "uint256"},
            {"internalType": "bool", "name": "revoked", "type": "bool"},
            {"internalType": "uint256", "name": "blockNumber", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
            {"internalType": "string", "name": "reason", "type": "string"}
        ],
        "name": "revokeCredential",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "anonymous": false,
        "inputs": [
            {"indexed": true, "internalType": "uint256", "name": "tokenId", "type": "uint256"},
            {"indexed": true, "internalType": "string", "name": "passportId", "type": "string"},
            {"indexed": false, "internalType": "bytes32", "name": "credentialHash", "type": "bytes32"}
        ],
        "name": "CredentialMinted",
        "type": "event"
    },
    {
        "anonymous": false,
        "inputs": [
            {"indexed": true, "internalType": "uint256", "name": "tokenId", "type": "uint256"},
            {"indexed": false, "internalType": "string", "name": "reason", "type": "string"}
        ],
        "name": "CredentialRevoked",
        "type": "event"
    }
]
"""

# ============================================================================
# Solidity Smart Contract (for deployment)
# ============================================================================

VETTEDME_SOLIDITY_CONTRACT = """
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title VettedMeCredentials
 * @dev NFT-based verifiable credentials following W3C standards
 */
contract VettedMeCredentials is ERC721, Ownable {
    
    struct Credential {
        string passportId;
        string badgeId;
        bytes32 credentialHash;
        bytes signature;
        uint256 mintedAt;
        bool revoked;
        string revocationReason;
    }
    
    uint256 private _tokenIdCounter;
    mapping(uint256 => Credential) public credentials;
    mapping(string => uint256[]) public passportCredentials;
    
    event CredentialMinted(uint256 indexed tokenId, string indexed passportId, bytes32 credentialHash);
    event CredentialRevoked(uint256 indexed tokenId, string reason);
    
    constructor() ERC721("VettedMe Credential", "VMCRED") {}
    
    function mintCredential(
        string memory passportId,
        string memory badgeId,
        bytes32 credentialHash,
        bytes memory signature
    ) public onlyOwner returns (uint256) {
        uint256 tokenId = _tokenIdCounter++;
        
        credentials[tokenId] = Credential({
            passportId: passportId,
            badgeId: badgeId,
            credentialHash: credentialHash,
            signature: signature,
            mintedAt: block.timestamp,
            revoked: false,
            revocationReason: ""
        });
        
        passportCredentials[passportId].push(tokenId);
        
        _safeMint(msg.sender, tokenId);
        
        emit CredentialMinted(tokenId, passportId, credentialHash);
        
        return tokenId;
    }
    
    function revokeCredential(uint256 tokenId, string memory reason) public onlyOwner {
        require(_exists(tokenId), "Credential does not exist");
        require(!credentials[tokenId].revoked, "Credential already revoked");
        
        credentials[tokenId].revoked = true;
        credentials[tokenId].revocationReason = reason;
        
        emit CredentialRevoked(tokenId, reason);
    }
    
    function getCredential(uint256 tokenId) public view returns (
        string memory passportId,
        string memory badgeId,
        bytes32 credentialHash,
        uint256 mintedAt,
        bool revoked,
        uint256 blockNumber
    ) {
        require(_exists(tokenId), "Credential does not exist");
        Credential memory cred = credentials[tokenId];
        return (
            cred.passportId,
            cred.badgeId,
            cred.credentialHash,
            cred.mintedAt,
            cred.revoked,
            block.number
        );
    }
    
    function getPassportCredentials(string memory passportId) public view returns (uint256[] memory) {
        return passportCredentials[passportId];
    }
}
"""
