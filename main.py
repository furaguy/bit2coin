# main.py
from src.blockchain.blockchain import Blockchain
from src.network.node import Node
from src.wallet.keys import KeyGenerator
from src.consensus.proof_of_stake import ProofOfStake

def main():
    # Initialize core components
    blockchain = Blockchain()
    pos_consensus = ProofOfStake()
    
    # Generate node and wallet
    node = Node()
    private_key, public_key = KeyGenerator.generate_keys()
    wallet_address = KeyGenerator.generate_address(public_key)

    # Register node as a validator
    pos_consensus.register_validator(wallet_address, initial_stake=1000)

    # Start network node
    node.blockchain = blockchain
    node.start()

    print(f"Bit2Coin Node Started. Address: {wallet_address}")

if __name__ == "__main__":
    main()