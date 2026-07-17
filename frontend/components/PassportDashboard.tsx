import React, { useState, useEffect } from 'react';

export default function PassportDashboard() {
  const [loading, setLoading] = useState(false);
  const [verifiedBadges, setVerifiedBadges] = useState<string[]>([]);

  const badges = [
    { id: 'linkedin', name: 'LinkedIn Professional Profile', icon: '🔗' },
    { id: 'state_id', name: 'State Credential Verification', icon: '🪪' },
    { id: 'stripe_billing', name: 'Verified B2B SaaS Business', icon: '💳' }
  ];

  const handleVerify = (id: string) => {
    setLoading(true);
    // Simulating Reclaim Protocol zkTLS verification step
    setTimeout(() => {
      if (!verifiedBadges.includes(id)) {
        setVerifiedBadges([...verifiedBadges, id]);
      }
      setLoading(false);
    }, 1500);
  };

  return (
    <div className="min-h-screen bg-gray-950 text-white font-sans p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <header className="border-b border-gray-800 pb-6 mb-8 flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-blue-400 to-indigo-500 bg-clip-text text-transparent">
              VettedMe Trust Passport
            </h1>
            <p className="text-gray-400 mt-1">Generate and display secure zkTLS proofs instantly.</p>
          </div>
          <div className="bg-gray-900 border border-gray-800 px-4 py-2 rounded-lg text-sm text-gray-300">
            Status: <span className="text-emerald-400 font-semibold">Active Engine</span>
          </div>
        </header>

        {/* Dashboard Grid */}
        <main className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="md:col-span-2 space-y-6">
            <h2 className="text-xl font-bold text-gray-200">Available Trust Credentials</h2>
            <div className="space-y-4">
              {badges.map((badge) => (
                <div key={badge.id} className="bg-gray-900 border border-gray-800 p-5 rounded-xl flex items-center justify-between hover:border-gray-700 transition-all">
                  <div className="flex items-center space-x-4">
                    <span className="text-2xl p-2 bg-gray-800 rounded-lg">{badge.icon}</span>
                    <div>
                      <h3 className="font-semibold text-gray-100">{badge.name}</h3>
                      <p className="text-xs text-gray-500">Secured via Reclaim Protocol SDK</p>
                    </div>
                  </div>
                  <button 
                    onClick={() => handleVerify(badge.id)}
                    disabled={loading || verifiedBadges.includes(badge.id)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      verifiedBadges.includes(badge.id)
                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 cursor-default'
                        : 'bg-blue-600 hover:bg-blue-500 text-white'
                    }`}
                  >
                    {verifiedBadges.includes(badge.id) ? '✓ Verified' : 'Verify Identity'}
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Right Sidebar - Passport Summary */}
          <div className="bg-gray-900 border border-gray-800 p-6 rounded-xl h-fit space-y-6">
            <h2 className="text-lg font-bold text-gray-200">Your Trust Score</h2>
            <div className="relative pt-1">
              <div className="flex mb-2 items-center justify-between">
                <div>
                  <span className="text-xs font-semibold inline-block py-1 px-2 uppercase rounded-full text-blue-400 bg-blue-900/30">
                    Verification Progress
                  </span>
                </div>
                <div className="text-right">
                  <span className="text-sm font-bold text-blue-400">
                    {Math.round((verifiedBadges.length / badges.length) * 100)}%
                  </span>
                </div>
              </div>
              <div className="overflow-hidden h-2 text-xs flex rounded bg-gray-800">
                <div 
                  style={{ width: `${(verifiedBadges.length / badges.length) * 100}%` }}
                  className="shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center bg-blue-500 transition-all duration-500"
                ></div>
              </div>
            </div>
            <div className="border-t border-gray-800 pt-4 space-y-3">
              <p className="text-xs text-gray-400">Verified Credentials Layer:</p>
              {verifiedBadges.length === 0 ? (
                <p className="text-sm text-gray-500 italic">No credentials loaded yet.</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {verifiedBadges.map(id => (
                    <span key={id} className="text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-1 rounded">
                      {id.toUpperCase()} PROVED
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
