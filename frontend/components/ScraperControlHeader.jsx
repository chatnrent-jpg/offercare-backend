import React, { useState } from 'react';

export default function ScraperControlHeader({ onRefreshComplete }) {
  const [syncing, setSyncing] = useState(false);

  const handleForceRefresh = async () => {
    setSyncing(true);
    try {
      // In production, this can fire a direct POST to a /api/v1/deploy/checklist or direct trigger endpoint
      const response = await fetch('/api/v1/deploy/checklist');
      if (response.ok && onRefreshComplete) {
        // Re-trigger global data telemetry pull upon successful loop exit
        onRefreshComplete();
      }
    } catch (err) {
      console.error("Manual background scrapers force sync failed:", err);
    } finally {
      // Small visual buffer spacer for smooth transition rendering
      setTimeout(() => setSyncing(false), 800);
    }
  };

  return (
    <header className="mb-8 flex flex-col sm:flex-row items-start sm:items-center justify-between border-b border-slate-800 pb-4 gap-4">
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">VettedMe Enterprise</h1>
        <p className="text-sm text-slate-400">Maryland OHCQ / DH Compliance Monitor Dashboard</p>
      </div>
      <div className="flex items-center gap-4 w-full sm:w-auto justify-between sm:justify-end">
        <button
          onClick={handleForceRefresh}
          disabled={syncing}
          className={`flex items-center gap-2 text-xs font-semibold py-2 px-4 rounded-lg border text-white transition shadow-md ${
            syncing 
              ? 'bg-slate-800 border-slate-700 cursor-not-allowed opacity-60' 
              : 'bg-slate-800 border-slate-700 hover:bg-slate-700 active:scale-95'
          }`}
        >
          <svg className={`h-3.5 w-3.5 text-emerald-400 ${syncing ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.253 8H18" />
          </svg>
          {syncing ? 'Synchronizing State Registry...' : 'Force MBON Scraper Run'}
        </button>
        <div className="flex items-center gap-2">
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
          </span>
          <span className="text-xs font-bold text-slate-300 font-mono tracking-wide">RUNNING_100</span>
        </div>
      </div>
    </header>
  );
}
