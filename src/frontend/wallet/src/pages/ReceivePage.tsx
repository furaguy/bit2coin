// src/frontend/wallet/src/pages/ReceivePage.tsx
import { useState } from 'react';
import { Copy, Download } from 'lucide-react';

export function ReceivePage() {
  const [copied, setCopied] = useState(false);
  const address = '0x1234...5678'; // TODO: Get from wallet

  const handleCopy = async () => {
    await navigator.clipboard.writeText(address);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="max-w-lg mx-auto">
      <h1 className="text-2xl font-bold mb-6">Receive B2C</h1>
      
      <div className="bg-white rounded-lg shadow p-6">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Your Wallet Address
            </label>
            <div className="flex">
              <input
                type="text"
                readOnly
                value={address}
                className="flex-1 p-2 border rounded-l bg-gray-50"
              />
              <button
                onClick={handleCopy}
                className="px-4 py-2 bg-blue-600 text-white rounded-r hover:bg-blue-700"
              >
                <Copy className="w-4 h-4" />
              </button>
            </div>
            {copied && (
              <p className="text-sm text-green-600 mt-1">Address copied!</p>
            )}
          </div>

          <div className="border-2 border-dashed rounded-lg p-8 text-center">
            <div className="bg-gray-100 w-48 h-48 mx-auto mb-4">
              {/* QR Code placeholder */}
            </div>
            <button className="text-blue-600 hover:text-blue-800">
              <Download className="w-4 h-4 inline mr-2" />
              Download QR Code
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}