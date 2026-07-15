import React, { useState } from 'react';
import ScraperControlHeader from '../components/ScraperControlHeader';
import ComplianceDashboard from '../components/ComplianceDashboard';
import DocUploadForm from '../components/DocUploadForm';
import ShiftMatchPanel from '../components/ShiftMatchPanel';

export default function MasterDashboardShell() {
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const triggerGlobalDataPull = () => {
    setRefreshTrigger(prev => prev + 1);
  };

  return (
    <div className="min-h-screen bg-slate-900 p-6 text-slate-100 font-sans">
      <ScraperControlHeader onRefreshComplete={triggerGlobalDataPull} />
      
      {/* Primary Telemetry Analytics Grid Cards */}
      <ComplianceDashboard key={refreshTrigger} />

      {/* Interactive Operational Feature Forms */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-8">
        <DocUploadForm credentialId="cred-seed-md-01" onUploadSuccess={triggerGlobalDataPull} />
        <ShiftMatchPanel shiftId="shift-2026-004" requiredRole="RN" facilityId="fac-jhh-baltimore" />
      </div>
    </div>
  );
}
