// src/frontend/explorer/src/components/blocks/BlockList.tsx
import { Link } from 'react-router-dom';
import { Block } from '../../types';
import { timeAgo } from '../../utils/time';

interface BlockListProps {
  blocks: Block[];
}

export function BlockList({ blocks }: BlockListProps) {
  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <div className="p-4 border-b">
        <h2 className="text-xl font-semibold">Latest Blocks</h2>
      </div>
      <div className="divide-y">
        {blocks.map((block) => (
          <Link
            key={block.height}
            to={`/block/${block.height}`}
            className="p-4 hover:bg-gray-50 flex items-center justify-between"
          >
            <div>
              <div className="font-medium">Block #{block.height}</div>
              <div className="text-sm text-gray-500">
                Validator: {block.validator}
              </div>
            </div>
            <div className="text-right">
              <div>{block.transactions} txns</div>
              <div className="text-sm text-gray-500">
                {timeAgo(block.timestamp)}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}