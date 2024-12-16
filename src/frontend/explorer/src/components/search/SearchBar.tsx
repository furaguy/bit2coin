// src/frontend/explorer/src/components/search/SearchBar.tsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search } from 'lucide-react';

export function SearchBar() {
  const [query, setQuery] = useState('');
  const navigate = useNavigate();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.match(/^[0-9]+$/)) {
      navigate(`/block/${query}`);
    } else if (query.match(/^0x[a-fA-F0-9]{64}$/)) {
      navigate(`/tx/${query}`);
    } else if (query.match(/^0x[a-fA-F0-9]{40}$/)) {
      navigate(`/address/${query}`);
    }
  };

  return (
    <form onSubmit={handleSearch} className="w-full max-w-3xl mx-auto">
      <div className="relative">
        <input
          type="text"
          placeholder="Search by Block / Tx Hash / Address"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full p-4 pr-12 rounded-lg border focus:ring-2 focus:ring-blue-500"
        />
        <button type="submit" className="absolute right-4 top-4">
          <Search className="w-6 h-6 text-gray-400" />
        </button>
      </div>
    </form>
  );
}