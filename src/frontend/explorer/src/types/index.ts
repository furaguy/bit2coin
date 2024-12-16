// src/frontend/explorer/src/types/index.ts

export interface Block {
    height: number;
    hash: string;
    timestamp: string;
    validator: string;
    transactions: number;
    size: number;
    previous_hash: string;
  }
  
  export interface Transaction {
    hash: string;
    block_height: number;
    from_address: string;
    to_address: string;
    amount: number;
    timestamp: string;
    status: string;
  }
  
  export interface Address {
    address: string;
    balance: number;
    total_transactions: number;
    last_active: string;
  }