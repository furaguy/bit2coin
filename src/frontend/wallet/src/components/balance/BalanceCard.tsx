// src/frontend/wallet/src/components/balance/BalanceCard.tsx
import { useState } from 'react';
import { RefreshCw } from 'lucide-react';

interface BalanceCardProps {
  balance: string;
  onRefresh: () => void;
}

export function BalanceCard({ balance, onRefresh }: BalanceCardProps) {
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = async () => {
    setRefreshing(true);
    await onRefresh();
    setRefreshing(false);
  };

  return (
    <div className="bg-white rounded-lg shadow-lg p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-semibold">Your Balance</h2>
        <button 
          onClick={handleRefresh}
          className={`text-gray-500 ${refreshing ? 'animate-spin' : ''}`}
        >
          <RefreshCw className="w-5 h-5" />
        </button>
      </div>
      <div className="text-4xl font-bold mb-2">{balance} B2C</div>
      <div className="text-gray-500">≈ ${Number(balance) * 123.45}</div>
    </div>
  );
}
