// src/frontend/wallet/src/pages/DashboardPage.tsx
import { useState, useEffect } from 'react';
import { BalanceCard } from '../components/balance/BalanceCard';
import { TransactionList } from '../components/transactions/TransactionList';
import { WalletInfo } from '../types';
import { walletApi } from '../services/api';

export function DashboardPage() {
  const [walletInfo, setWalletInfo] = useState<WalletInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchWalletInfo = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Get wallet info using the API service
      const info = await walletApi.getWalletInfo();
      setWalletInfo(info);
    } catch (err) {
      console.error('Error fetching wallet info:', err);
      setError('Failed to load wallet information');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWalletInfo();

    // Refresh data every 30 seconds
    const interval = setInterval(fetchWalletInfo, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !walletInfo) return <div>Loading...</div>;
  if (error) return <div className="text-red-600">{error}</div>;
  if (!walletInfo) return <div>No wallet information available</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Wallet Dashboard</h1>
      <BalanceCard 
        balance={walletInfo.balance} 
        onRefresh={fetchWalletInfo}
      />
      <TransactionList transactions={walletInfo.transactions} />
    </div>
  );
}