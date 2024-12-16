// src/frontend/wallet/src/pages/SendPage.tsx
import { SendForm } from '../components/send/SendForm';
import { SendTransactionRequest } from '../types';

export function SendPage() {
  const handleSend = async (data: SendTransactionRequest) => {
    // TODO: Replace with actual API call
    console.log('Sending transaction:', data);
  };

  return (
    <div className="max-w-lg mx-auto">
      <h1 className="text-2xl font-bold mb-6">Send B2C</h1>
      <SendForm onSend={handleSend} />
    </div>
  );
}