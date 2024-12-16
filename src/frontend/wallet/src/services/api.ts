// src/frontend/wallet/src/services/api.ts
import axios from 'axios';
import { WalletInfo, SendTransactionRequest } from '../types';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export const walletApi = {
  async getWalletInfo(): Promise<WalletInfo> {
    const response = await axios.get(`${BASE_URL}/wallet/info`);
    return response.data;
  },

  async sendTransaction(data: SendTransactionRequest): Promise<string> {
    const response = await axios.post(`${BASE_URL}/wallet/send`, data);
    return response.data.txHash;
  },

  async getBalance(): Promise<string> {
    const response = await axios.get(`${BASE_URL}/wallet/balance`);
    return response.data.balance;
  },

  async getTransactions(): Promise<any[]> {
    const response = await axios.get(`${BASE_URL}/wallet/transactions`);
    return response.data;
  }
};