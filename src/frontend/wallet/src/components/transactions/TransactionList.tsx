// src/frontend/wallet/src/components/transactions/TransactionList.tsx
import { WalletTransaction } from '../../types';
import { timeAgo } from '../../utils/time';
import { Send, Download } from 'lucide-react';

interface TransactionListProps {
  transactions: WalletTransaction[];
}

export function TransactionList({ transactions }: TransactionListProps) {
  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <div className="p-4 border-b">
        <h2 className="text-xl font-semibold">Transaction History</h2>
      </div>
      <div className="divide-y">
        {transactions.map((tx) => (
          <div key={tx.hash} className="p-4 hover:bg-gray-50">
            <div className="flex justify-between">
              <div>
                <div className="flex items-center">
                  {tx.type === 'send' ? (
                    <Send className="w-4 h-4 mr-2 text-red-500" />
                  ) : (
                    <Download className="w-4 h-4 mr-2 text-green-500" />
                  )}
                  <span className="font-medium">
                    {tx.type === 'send' ? 'Sent' : 'Received'} {tx.amount} B2C
                  </span>
                </div>
                <div className="text-sm text-gray-500">
                  {tx.type === 'send' ? 'To: ' : 'From: '}{tx.address}
                </div>
              </div>
              <div className="text-right">
                <div className={tx.status === 'confirmed' ? 'text-green-600' : 'text-yellow-600'}>
                  {tx.status}
                </div>
                <div className="text-sm text-gray-500">
                  {timeAgo(tx.timestamp)}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}