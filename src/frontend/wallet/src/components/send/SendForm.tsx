// src/frontend/wallet/src/components/send/SendForm.tsx
import { useState } from 'react';
import { Send } from 'lucide-react';
import { SendTransactionRequest } from '../../types';

interface SendFormProps {
  onSend: (data: SendTransactionRequest) => Promise<void>;
}

export function SendForm({ onSend }: SendFormProps) {
  const [formData, setFormData] = useState({
    to: '',
    amount: '',
    password: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await onSend(formData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Transaction failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700">
          Recipient Address
        </label>
        <input
          type="text"
          value={formData.to}
          onChange={(e) => setFormData({ ...formData, to: e.target.value })}
          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm"
          required
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700">
          Amount (B2C)
        </label>
        <input
          type="number"
          step="0.000001"
          value={formData.amount}
          onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm"
          required
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700">
          Password
        </label>
        <input
          type="password"
          value={formData.password}
          onChange={(e) => setFormData({ ...formData, password: e.target.value })}
          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm"
          required
        />
      </div>

      {error && (
        <div className="text-red-600 text-sm">{error}</div>
      )}

      <button
        type="submit"
        disabled={loading}
        className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700"
      >
        {loading ? 'Sending...' : (
          <>
            <Send className="w-4 h-4 mr-2" />
            Send Transaction
          </>
        )}
      </button>
    </form>
  );
}