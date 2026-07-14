import React, { useState, useEffect } from 'react';

export default function ComplianceDashboard() {
  const [telemetry, setTelemetry] = useState(null);
  const [loading, setLoading] = useState(true);

  // 🔄 Fetch real-time metrics from the FastAPI endpoint on mount
  useEffect(() => {
    fetch('/api/v1/analytics/scraper-summary')
      .then((res) => res.json())
      .then((data) => {
        setTelemetry(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to stream telemetry data:", err);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-900 text-white">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-emerald-500"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-900 p-6 text-slate-100 font-sans">
      {/* Header Bar */}
      <header className="mb-8 flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">VettedMe Enterprise</h1>
          <p className="text-sm text-slate-400">Maryland OHCQ / DH Compliance Monitor Dashboard</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
          </span>
          <span className="text-xs font-semibold bg-slate-800 px-3 py-1.5 rounded-md border border-slate-700">
            SYSTEM STATUS: RUNNING_100
          </span>
        </div>
      </header>

      {/* Grid Row 1: KPI Telemetry Scorecards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <div className="bg-slate-800 p-5 rounded-xl border border-slate-700/60 shadow-lg">
          <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Compliance Health Score</p>
          <p className="text-3xl font-extrabold text-emerald-400 mt-2">{telemetry?.global_compliance_score}%</p>
        </div>
        <div className="bg-slate-800 p-5 rounded-xl border border-slate-700/60 shadow-lg">
          <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Total Monitored Licenses</p>
          <p className="text-3xl font-extrabold text-white mt-2">{telemetry?.counters?.total_monitored_licenses}</p>
        </div>
        <div className="bg-slate-800 p-5 rounded-xl border border-slate-700/60 shadow-lg">
          <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Cleared Active Workers</p>
          <p className="text-3xl font-extrabold text-white mt-2">{telemetry?.counters?.cleared_active_workers}</p>
        </div>
        <div className="bg-slate-800 p-5 rounded-xl border border-slate-700/60 shadow-lg">
          <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Pending Immediate Sync</p>
          <p className="text-3xl font-extrabold text-amber-400 mt-2">{telemetry?.counters?.pending_immediate_sync}</p>
        </div>
      </div>

      {/* Grid Row 2: Infrastructure Diagnostics & Audit Tables */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Scraper Infrastructure Card */}
        <div className="bg-slate-800 p-6 rounded-xl border border-slate-700/60 shadow-lg lg:col-span-1">
          <h2 className="text-lg font-bold text-white mb-4">Registry Scraper Diagnostics</h2>
          <div className="space-y-4 text-sm">
            <div className="flex justify-between border-b border-slate-700/50 pb-2">
              <span className="text-slate-400">Proxy Pool Health</span>
              <span className="text-emerald-400 font-semibold">{telemetry?.scraper_infrastructure_telemetry?.proxy_pool_health}</span>
            </div>
            <div className="flex justify-between border-b border-slate-700/50 pb-2">
              <span className="text-slate-400">Active Rotators Counted</span>
              <span className="text-white font-mono">{telemetry?.scraper_infrastructure_telemetry?.active_proxies_counted} nodes</span>
            </div>
            <div className="flex justify-between border-b border-slate-700/50 pb-2">
              <span className="text-slate-400">Avg Registry Latency</span>
              <span className="text-white font-mono">{telemetry?.scraper_infrastructure_telemetry?.average_response_latency_ms} ms</span>
            </div>
          </div>
        </div>

        {/* Worker Compliance Queue Mock Rendering */}
        <div className="bg-slate-800 p-6 rounded-xl border border-slate-700/60 shadow-lg lg:col-span-2">
          <h2 className="text-lg font-bold text-white mb-4">Active Placement Clearance Monitor</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-900 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                <tr>
                  <th className="p-3 rounded-l-lg">Professional</th>
                  <th className="p-3">Role / License No.</th>
                  <th className="p-3">Assigned Facility</th>
                  <th className="p-3 rounded-r-lg">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/50">
                <tr className="hover:bg-slate-700/20">
                  <td className="p-3 font-semibold text-white">Sarah Jenkins, RN</td>
                  <td className="p-3 font-mono text-xs">RN - R234951</td>
                  <td className="p-3 text-slate-400">Johns Hopkins Hospital</td>
                  <td className="p-3"><span className="bg-emerald-500/10 text-emerald-400 text-xs px-2.5 py-1 rounded-full font-medium">CLEARED</span></td>
                </tr>
                <tr className="hover:bg-slate-700/20">
                  <td className="p-3 font-semibold text-white">Michael Chang, LPN</td>
                  <td className="p-3 font-mono text-xs">LPN - L098114</td>
                  <td className="p-3 text-slate-400">University of MD Medical Center</td>
                  <td className="p-3"><span className="bg-amber-500/10 text-amber-400 text-xs px-2.5 py-1 rounded-full font-medium">STALE_SYNC</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </div>
  );
}
