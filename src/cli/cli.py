# src/cli/cli.py
import argparse
import sys
from typing import List
from ..blockchain.blockchain import Blockchain
from ..wallet.wallet import Wallet
from ..network.node import Node
from ..consensus.proof_of_stake import ProofOfStake

class CLI:
    def __init__(self):
        self.blockchain = Blockchain()
        self.wallet = None
        self.node = None
        self.pos = ProofOfStake()

    def main(self, args: List[str]):
        parser = self.create_parser()
        args = parser.parse_args(args)
        
        if not hasattr(args, 'func'):
            parser.print_help()
            return
            
        args.func(args)

    def create_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description='bit2coin CLI')
        subparsers = parser.add_subparsers(title='commands', dest='command')

        # Wallet commands
        wallet_parser = subparsers.add_parser('wallet', help='Wallet operations')
        wallet_subparsers = wallet_parser.add_subparsers()

        create_wallet = wallet_subparsers.add_parser('create', help='Create new wallet')
        create_wallet.set_defaults(func=self.create_wallet)

        balance = wallet_subparsers.add_parser('balance', help='Get wallet balance')
        balance.add_argument('address', help='Wallet address')
        balance.set_defaults(func=self.get_balance)

        # Node commands
        node_parser = subparsers.add_parser('node', help='Node operations')
        node_subparsers = node_parser.add_subparsers()

        start_node = node_subparsers.add_parser('start', help='Start a node')
        start_node.add_argument('--host', default='127.0.0.1', help='Node host')
        start_node.add_argument('--port', type=int, default=5000, help='Node port')
        start_node.set_defaults(func=self.start_node)

        # Transaction commands
        tx_parser = subparsers.add_parser('tx', help='Transaction operations')
        tx_subparsers = tx_parser.add_subparsers()

        send_tx = tx_subparsers.add_parser('send', help='Send transaction')
        send_tx.add_argument('recipient', help='Recipient address')
        send_tx.add_argument('amount', type=float, help='Amount to send')
        send_tx.set_defaults(func=self.send_transaction)

        return parser

    def create_wallet(self, args):
        self.wallet = Wallet()
        print(f"Created new wallet")
        print(f"Address: {self.wallet.address}")
        print(f"Private key: {self.wallet.keypair.export_private_key()}")

    def get_balance(self, args):
        balance = self.blockchain.get_balance(args.address)
        print(f"Balance for {args.address}: {balance}")

    def start_node(self, args):
        self.node = Node(args.host, args.port, self.blockchain)
        print(f"Started node at {args.host}:{args.port}")
        self.node.start()

    def send_transaction(self, args):
        if not self.wallet:
            print("Error: No wallet loaded. Create or load a wallet first.")
            return
        
        tx = self.wallet.create_transaction(args.recipient, args.amount)
        if tx:
            if self.node:
                self.node.broadcast_transaction(tx)
            print(f"Transaction sent: {tx.transaction_id}")
        else:
            print("Error creating transaction. Check balance and parameters.")

def main():
    cli = CLI()
    cli.main(sys.argv[1:])

if __name__ == "__main__":
    main()