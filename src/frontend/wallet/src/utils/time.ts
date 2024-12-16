// src/frontend/wallet/src/utils/time.ts
export const timeAgo = (timestamp: string): string => {
    const now = new Date().getTime();
    const past = new Date(timestamp).getTime();
    const diff = now - past;
  
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
  
    if (days > 0) return `${days} days ago`;
    if (hours > 0) return `${hours} hours ago`;
    if (minutes > 0) return `${minutes} minutes ago`;
    return `${seconds} seconds ago`;
  };