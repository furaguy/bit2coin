// src/frontend/explorer/src/pages/HomePage.tsx
import { useEffect, useState } from 'react';
import { SearchBar } from '../components/search/SearchBar';
import { BlockList } from '../components/blocks/BlockList';
import { explorerApi } from '../services/api';
import { Block } from '../types';

export function HomePage() {
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const blocksData = await explorerApi.getLatestBlocks(10);
        setBlocks(blocksData);
      } catch (error) {
        console.error('Error fetching blocks:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 10000); // Refresh every 10 seconds
    return () => clearInterval(interval);
  }, []);

  if (loading) return <div>Loading...</div>;

  return (
    <div className="space-y-8">
      <SearchBar />
      <BlockList blocks={blocks} />
    </div>
  );
}