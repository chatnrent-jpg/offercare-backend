import React from 'react';
import Head from 'next/head';
import TransferDashboard from '../../components/TransferDashboard';

export default function TransferPage() {
  return (
    <>
      <Head>
        <title>VettedPay - Private Transfer</title>
        <meta name="description" content="Send privacy-preserving international payments with zero-knowledge compliance" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>

      <main className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-indigo-900">
        {/* Header */}
        <header className="border-b border-slate-700/50 bg-slate-900/50 backdrop-blur-sm">
          <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-lg">V</span>
              </div>
              <h1 className="text-xl font-bold text-white">
                Vetted<span className="text-indigo-400">Pay</span>
              </h1>
            </div>
            
            <nav className="hidden md:flex items-center space-x-6">
              <a href="/" className="text-slate-400 hover:text-white text-sm transition-colors">
                Dashboard
              </a>
              <a href="/vettedpay/transfer" className="text-white text-sm font-semibold">
                Transfer
              </a>
              <a href="/vettedpay/transactions" className="text-slate-400 hover:text-white text-sm transition-colors">
                Transactions
              </a>
              <a href="/vettedpay/rails" className="text-slate-400 hover:text-white text-sm transition-colors">
                Rail Health
              </a>
            </nav>

            <div className="flex items-center space-x-3">
              <div className="hidden md:flex items-center space-x-2 px-3 py-1.5 bg-slate-800 rounded-lg border border-slate-700">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                <span className="text-xs text-slate-400">Rails Active</span>
              </div>
              <button className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-sm text-white transition-colors">
                Settings
              </button>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <div className="max-w-7xl mx-auto px-4 py-8">
          <TransferDashboard />
          
          {/* Info Cards */}
          <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4 max-w-xl mx-auto">
            <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4">
              <div className="flex items-center space-x-2 mb-2">
                <div className="w-8 h-8 bg-indigo-500/10 rounded-lg flex items-center justify-center">
                  <span className="text-indigo-400 text-lg">🔒</span>
                </div>
                <h3 className="text-sm font-semibold text-white">Zero-Knowledge</h3>
              </div>
              <p className="text-xs text-slate-400">
                Prove compliance without revealing identity
              </p>
            </div>

            <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4">
              <div className="flex items-center space-x-2 mb-2">
                <div className="w-8 h-8 bg-green-500/10 rounded-lg flex items-center justify-center">
                  <span className="text-green-400 text-lg">⚡</span>
                </div>
                <h3 className="text-sm font-semibold text-white">Multi-Rail</h3>
              </div>
              <p className="text-xs text-slate-400">
                Auto-failover if one provider goes down
              </p>
            </div>

            <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4">
              <div className="flex items-center space-x-2 mb-2">
                <div className="w-8 h-8 bg-amber-500/10 rounded-lg flex items-center justify-center">
                  <span className="text-amber-400 text-lg">🛡️</span>
                </div>
                <h3 className="text-sm font-semibold text-white">Encrypted</h3>
              </div>
              <p className="text-xs text-slate-400">
                Bank data encrypted client-side (E2EE)
              </p>
            </div>
          </div>

          {/* Technical Details */}
          <div className="mt-8 max-w-xl mx-auto">
            <details className="bg-slate-800/30 border border-slate-700/30 rounded-lg p-4">
              <summary className="text-sm font-semibold text-slate-300 cursor-pointer hover:text-white transition-colors">
                How It Works (Technical)
              </summary>
              <div className="mt-4 space-y-3 text-xs text-slate-400">
                <div className="flex items-start space-x-2">
                  <span className="text-indigo-400 font-semibold">1.</span>
                  <p>
                    <strong className="text-slate-300">ZK-Proof Generation:</strong> Your browser generates a zero-knowledge proof 
                    that you&apos;re not on OFAC/EU/UN sanction lists, without revealing your identity.
                  </p>
                </div>
                <div className="flex items-start space-x-2">
                  <span className="text-indigo-400 font-semibold">2.</span>
                  <p>
                    <strong className="text-slate-300">Client-Side Encryption:</strong> Bank account details are encrypted 
                    with the recipient&apos;s public RSA key. The backend never sees plaintext.
                  </p>
                </div>
                <div className="flex items-start space-x-2">
                  <span className="text-indigo-400 font-semibold">3.</span>
                  <p>
                    <strong className="text-slate-300">Rail Routing:</strong> Backend verifies ZK-proof and routes to active 
                    payment rail (Airwallex, Nium, Wise, or Stablecoin).
                  </p>
                </div>
                <div className="flex items-start space-x-2">
                  <span className="text-indigo-400 font-semibold">4.</span>
                  <p>
                    <strong className="text-slate-300">Settlement:</strong> Transaction is processed and audit trail is logged. 
                    Your server only stores DIDs and encrypted references.
                  </p>
                </div>
              </div>
            </details>
          </div>
        </div>

        {/* Footer */}
        <footer className="mt-16 border-t border-slate-700/50 bg-slate-900/50">
          <div className="max-w-7xl mx-auto px-4 py-6">
            <div className="flex flex-col md:flex-row items-center justify-between">
              <p className="text-xs text-slate-500">
                &copy; 2026 VettedPay. Privacy-first payment infrastructure.
              </p>
              <div className="flex items-center space-x-4 mt-4 md:mt-0">
                <a href="/docs" className="text-xs text-slate-500 hover:text-slate-300 transition-colors">
                  Documentation
                </a>
                <a href="/api" className="text-xs text-slate-500 hover:text-slate-300 transition-colors">
                  API Reference
                </a>
                <a href="/status" className="text-xs text-slate-500 hover:text-slate-300 transition-colors">
                  Status Page
                </a>
              </div>
            </div>
          </div>
        </footer>
      </main>
    </>
  );
}
