import React, { useState } from 'react';

export default function Dashboard() {
  const [loading, setLoading] = useState(false);
  const [verified, setVerified] = useState<string[]>([]);

  const credentials = [
    { id: 'linkedin', name: 'LinkedIn Professional Passport', icon: '🔗' },
    { id: 'state_id', name: 'State ID Verification', icon: '🪪' },
    { id: 'stripe', name: 'Stripe SaaS Billing Account', icon: '💳' }
  ];

  const handleVerify = (id: string) => {
    setLoading(true);
    setTimeout(() => {
      if (!verified.includes(id)) setVerified([...verified, id]);
      setLoading(false);
    }, 1200);
  };

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#030712', color: '#ffffff', fontFamily: 'sans-serif', padding: '40px' }}>
      <div style={{ maxWidth: '800px', margin: '0 auto' }}>
        <header style={{ borderBottom: '1px solid #1f2937', paddingBottom: '20px', marginBottom: '30px', display: 'flex', justifyContent: 'between', alignItems: 'center' }}>
          <div>
            <h1 style={{ fontSize: '28px', fontWeight: 'bold', color: '#3b82f6', margin: 0 }}>VettedMe Trust Passport</h1>
            <p style={{ color: '#9ca3af', marginTop: '5px', margin: 0 }}>Secure zkTLS proofs generated in real-time.</p>
          </div>
        </header>

        <main style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '20px' }}>
          {credentials.map((item) => (
            <div key={item.id} style={{ backgroundColor: '#111827', border: '1px solid #1f2937', padding: '20px', borderRadius: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                <span style={{ fontSize: '24px', backgroundColor: '#1f2937', padding: '10px', borderRadius: '8px' }}>{item.icon}</span>
                <div>
                  <h3 style={{ margin: 0, fontSize: '16px', color: '#f3f4f6' }}>{item.name}</h3>
                  <p style={{ margin: 0, fontSize: '12px', color: '#6b7280' }}>Powered by Reclaim Protocol SDK</p>
                </div>
              </div>
              <button 
                onClick={() => handleVerify(item.id)}
                disabled={loading || verified.includes(item.id)}
                style={{
                  padding: '10px 20px', borderRadius: '8px', border: 'none', fontWeight: 'bold', cursor: 'pointer',
                  backgroundColor: verified.includes(item.id) ? '#065f46' : '#2563eb',
                  color: '#ffffff'
                }}
              >
                {verified.includes(item.id) ? '✓ Verified' : 'Verify Identity'}
              </button>
            </div>
          ))}
        </main>
      </div>
    </div>
  );
}
