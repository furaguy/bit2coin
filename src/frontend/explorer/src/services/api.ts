import axios from 'axios';
import { Block, Transaction, Address } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export const explorerApi = {
  async getLatestBlocks(limit: number = 10): Promise<Block[]> {
    const response = await axios.get(`${API_BASE_URL}/explorer/blocks/latest?limit=${limit}`);
    return response.data;
  },

  async getBlock(blockId: string): Promise<Block> {
    const response = await axios.get(`${API_BASE_URL}/explorer/blocks/${blockId}`);
    return response.data;
  },

  async getTransaction(hash: string): Promise<Transaction> {
    const response = await axios.get(`${API_BASE_URL}/explorer/transactions/${hash}`);
    return response.data;
  },

  async getAddress(address: string): Promise<Address> {
    const response = await axios.get(`${API_BASE_URL}/explorer/address/${address}`);
    return response.data;
  }
};