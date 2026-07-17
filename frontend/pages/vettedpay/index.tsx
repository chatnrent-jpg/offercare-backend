import React, { useState, useEffect } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

export default function VettedPayLanding() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);
  const [priorityData, setPriorityData] = useState<{ position: number; score: number } | null>(null);
  const [showForm, setShowForm] = useState(true);

  useEffect(() => {
    // Track referral source
    const ref = router.query.ref as string;
    if (ref) {
      localStorage.setItem('vettedpay_ref', ref);
    }
  }, [router.query.ref]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setStatusMessage(null);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const refSource = localStorage.getItem('vettedpay_ref') || router.query.ref || 'organic';

      const response = await fetch(`${apiUrl}/api/v1/vettedpay/waitlist`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email,
          referral_source: refSource,
        }),
      });

      const data = await response.json();

      if (response.ok && data.success) {
        setStatusMessage({ text: data.message, type: 'success' });
        setPriorityData({ position: data.position, score: data.priority_score });
        setEmail('');
        
        setTimeout(() => {
          setShowForm(false);
        }, 2000);
      } else {
        setStatusMessage({ 
          text: data.message || 'Failed to join waitlist. Please try again.', 
          type: 'error' 
        });
      }
    } catch (error) {
      console.error('Waitlist error:', error);
      setStatusMessage({ 
        text: 'Network error. Please check your connection and try again.', 
        type: 'error' 
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Head>
        <title>VettedPay | Private Cross-Border Financial Rails</title>
        <meta name="description" content="Send money globally with zero-knowledge compliance. Multi-rail payment infrastructure with end-to-end encryption." />
        <meta name="keywords" content="VettedPay, cross-border payments, zero-knowledge, privacy, encryption, financial rails" />
        
        <meta property="og:title" content="VettedPay - Private Cross-Border Financial Rails" />
        <meta property="og:description" content="Send money anywhere globally. Zero identity tracking." />
        <meta property="og:type" content="website" />
        <meta property="og:url" content="https://vettedpay.com" />
        
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>

      <div className="bg-slate-950 text-slate-100 min-h-screen flex flex-col justify-between selection:bg-indigo-500 selection:text-white">
        {/* Background glow effect */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-[500px] bg-gradient-to-b from-indigo-900/20 via-transparent to-transparent blur-3xl pointer-events-none -z-10"></div>

        {/* Header */}
        <header className="max-w-6xl w-full mx-auto px-6 py-6 flex justify-between items-center">
          <div className="text-xl font-extrabold tracking-tight">
            Vetted<span className="text-indigo-500">Pay</span>
            <span className="text-xs font-medium text-slate-500 ml-1">.com</span>
          </div>
          <div className="text-xs font-mono uppercase bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-full text-slate-400 tracking-wider">
            Network State: Stealth Alpha
          </div>
        </header>

        {/* Main Content */}
        <main className="max-w-4xl w-full mx-auto px-6 text-center py-12 md:py-20 my-auto">
          <span className="text-xs font-bold text-indigo-400 uppercase tracking-widest bg-indigo-500/10 border border-indigo-500/30 px-3 py-1 rounded-full">
            The Multi-Rail Financial Adapter Protocol
          </span>
          
          <h1 className="text-4xl md:text-6xl font-black tracking-tight text-white mt-6 leading-tight">
            Send Money Anywhere Globally.<br />
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 via-purple-400 to-indigo-400">
              Zero Identity Tracking.
            </span>
          </h1>
          
          <p className="mt-6 text-base md:text-xl text-slate-400 max-w-2xl mx-auto leading-relaxed">
            Move traditional capital through bank clearing rails using zero-knowledge compliance packets. 
            Complete corporate AML screening locally while remaining totally anonymous to our network servers.
          </p>

          {/* Waitlist Form */}
          {showForm && (
            <div className="mt-10 max-w-md mx-auto bg-slate-900/80 border border-slate-800 p-2 rounded-xl shadow-2xl backdrop-blur-md">
              <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-2">
                <input 
                  type="email" 
                  required 
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Enter corporate email address" 
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all" 
                />
                <button 
                  type="submit" 
                  disabled={loading}
                  className="whitespace-nowrap bg-indigo-600 hover:bg-indigo-700 active:scale-98 text-white text-sm font-semibold px-6 py-3 rounded-lg shadow-lg shadow-indigo-600/20 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed">
                  {loading ? 'Joining...' : 'Request Integration Access'}
                </button>
              </form>
              
              {/* Status Message */}
              {statusMessage && (
                <div className={`mt-3 p-3 rounded-lg text-xs ${
                  statusMessage.type === 'success' 
                    ? 'bg-green-500/10 border border-green-500/30 text-green-400' 
                    : 'bg-red-500/10 border border-red-500/30 text-red-400'
                }`}>
                  {statusMessage.text}
                </div>
              )}
            </div>
          )}

          {/* Priority Display */}
          {priorityData && (
            <div className="mt-6 max-w-md mx-auto">
              <div className="bg-indigo-500/10 border border-indigo-500/30 rounded-lg p-4">
                <div className="text-sm font-semibold text-indigo-400">Welcome to VettedPay!</div>
                <div className="text-xs text-slate-400 mt-2">
                  You&apos;re <span className="text-white font-bold">#{priorityData.position}</span> on the waitlist
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  Priority Score: <span className="text-indigo-400 font-mono">{priorityData.score}</span>
                </div>
              </div>
            </div>
          )}

          {/* Features Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-16 max-w-5xl mx-auto text-left">
            <div className="p-5 bg-slate-900/40 border border-slate-900 rounded-xl hover:border-slate-800 transition-colors">
              <div className="text-sm font-bold text-white mb-2">⚡ No-Knowledge Routing</div>
              <div className="text-xs text-slate-400 leading-relaxed">
                Financial data is end-to-end asymmetric encrypted locally. Our operational databases never capture bank routing payloads.
              </div>
            </div>
            <div className="p-5 bg-slate-900/40 border border-slate-900 rounded-xl hover:border-slate-800 transition-colors">
              <div className="text-sm font-bold text-white mb-2">🛡️ zkTLS Sanction Engine</div>
              <div className="text-xs text-slate-400 leading-relaxed">
                Cryptographically matches global compliance check credentials via Reclaim Protocol without tracking corporate entities.
              </div>
            </div>
            <div className="p-5 bg-slate-900/40 border border-slate-900 rounded-xl hover:border-slate-800 transition-colors">
              <div className="text-sm font-bold text-white mb-2">🔄 Multi-Rail Dynamic Adapter</div>
              <div className="text-xs text-slate-400 leading-relaxed">
                Decoupled abstraction allows our stack to switch pipelines instantly from Airwallex to Nium, Wise, or stablecoin networks.
              </div>
            </div>
          </div>

          {/* Social Proof */}
          <div className="mt-16 flex flex-col md:flex-row items-center justify-center gap-8 text-center">
            <div>
              <div className="text-3xl font-bold text-white">$12M+</div>
              <div className="text-xs text-slate-500 mt-1">Volume Processed</div>
            </div>
            <div className="hidden md:block w-px h-12 bg-slate-800"></div>
            <div>
              <div className="text-3xl font-bold text-white">5</div>
              <div className="text-xs text-slate-500 mt-1">Payment Rails</div>
            </div>
            <div className="hidden md:block w-px h-12 bg-slate-800"></div>
            <div>
              <div className="text-3xl font-bold text-white">99.9%</div>
              <div className="text-xs text-slate-500 mt-1">Uptime SLA</div>
            </div>
          </div>

          {/* Tech Stack */}
          <div className="mt-20 max-w-3xl mx-auto">
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-4">
              Trusted Infrastructure
            </div>
            <div className="flex flex-wrap items-center justify-center gap-6 opacity-50">
              <span className="text-sm font-mono text-slate-600">Airwallex</span>
              <span className="text-sm font-mono text-slate-600">Nium</span>
              <span className="text-sm font-mono text-slate-600">Wise</span>
              <span className="text-sm font-mono text-slate-600">PostgreSQL</span>
              <span className="text-sm font-mono text-slate-600">FastAPI</span>
              <span className="text-sm font-mono text-slate-600">Next.js</span>
              <span className="text-sm font-mono text-slate-600">Reclaim</span>
            </div>
          </div>
        </main>

        {/* Footer */}
        <footer className="max-w-6xl w-full mx-auto px-6 py-6 border-t border-slate-900 text-center text-xs text-slate-600 font-mono">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div>
              &copy; 2026 VettedPay Systems Inc. Powered seamlessly by VettedMe Identity Proof Circuits.
            </div>
            <div className="flex items-center gap-4">
              <a href="/docs" className="hover:text-slate-400 transition-colors">Documentation</a>
              <a href="/api" className="hover:text-slate-400 transition-colors">API</a>
              <a href="/status" className="hover:text-slate-400 transition-colors">Status</a>
              <a href="https://github.com/vettedpay" className="hover:text-slate-400 transition-colors" target="_blank" rel="noopener noreferrer">
                GitHub
              </a>
            </div>
          </div>
        </footer>
      </div>
    </>
  );
}
