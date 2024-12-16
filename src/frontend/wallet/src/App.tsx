// src/frontend/wallet/src/App.tsx
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { Wallet, Send, Download } from 'lucide-react';
import { DashboardPage } from './pages/DashboardPage';
import { SendPage } from './pages/SendPage';
import { ReceivePage } from './pages/ReceivePage';

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-100">
        <nav className="bg-white shadow-lg">
          <div className="max-w-7xl mx-auto px-4">
            <div className="flex justify-between h-16">
              <div className="flex">
                <Link to="/" className="flex items-center text-xl font-bold">
                  <Wallet className="w-6 h-6 mr-2" />
                  B2C Wallet
                </Link>
              </div>
              <div className="flex space-x-4">
                <Link to="/send" className="flex items-center px-3 py-2 text-gray-700 hover:text-gray-900">
                  <Send className="w-5 h-5 mr-1" />
                  Send
                </Link>
                <Link to="/receive" className="flex items-center px-3 py-2 text-gray-700 hover:text-gray-900">
                  <Download className="w-5 h-5 mr-1" />
                  Receive
                </Link>
              </div>
            </div>
          </div>
        </nav>

        <main className="container mx-auto px-4 py-8">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/send" element={<SendPage />} />
            <Route path="/receive" element={<ReceivePage />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;