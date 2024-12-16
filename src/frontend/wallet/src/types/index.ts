// src/frontend/wallet/src/types/index.ts

export interface WalletInfo {
    address: string;
    balance: string;
    transactions: WalletTransaction[];
  }
  
  export interface WalletTransaction {
    hash: string;
    type: 'send' | 'receive';
    amount: string;
    address: string;
    timestamp: string;
    status: 'pending' | 'confirmed' | 'failed';
  }
  
  export interface SendTransactionRequest {
    to: string;
    amount: string;
    password: string;
  }