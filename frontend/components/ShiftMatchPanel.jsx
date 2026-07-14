import React, { useState, useEffect } from 'react';

export default function ShiftMatchPanel({ shiftId, requiredRole, facilityId }) {
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/v1/shifts/${shiftId}/matches?required_role=${requiredRole}&facility_id=${facilityId}`)
      .then((res) => res.json())
      .then((data) => {
        setCandidates(data.candidates || []);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Matchmaking calculation failed:", err);
        setLoading(false);
      });
  }, [shiftId, requiredRole, facilityId]);

  return (
    <div className="bg-slate-800 p-6 rounded-xl border border-slate-700/60 shadow-lg">
      <div className="flex justify-between items-center mb-4">
        <div>
          <h3 className="text-md font-bold text-white">Automated OHCQ Scheduling Matches</h3>
          <p className="text-xs text-slate-400">Rank-order match scores for required position: <span className="font-mono text-emerald-400 font-semibold">{requiredRole}</span></p>
        </div>
        <span className="text-xs bg-slate-900 border border-slate-700 text-slate-300 font-mono px-2 py-1 rounded">
          Shift ID: {shiftId}
        </span>
      </div>

      {loading ? (
        <div className="text-center py-6 text-slate-400 text-sm animate-pulse">Calculating score vectors...</div>
      ) : candidates.length === 0 ? (
        <div className="text-center py-6 text-rose-400 text-sm">No cleared, active candidates found for this role profile.</div>
      ) : (
        <div className="space-y-3">
          {candidates.map((candidate) => (
            <div key={candidate.professional_id} className="flex items-center justify-between bg-slate-900/60 border border-slate-700/40 p-3 rounded-lg hover:border-slate-600 transition">
              <div className="flex flex-col">
                <span className="text-sm font-semibold text-white">{candidate.name}</span>
                <span className="text-xs text-slate-400 font-mono">{candidate.license}</span>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-right">
                  <div className="text-xs text-slate-400 font-medium">Match Match Score</div>
                  <div className="text-sm font-extrabold text-emerald-400">{candidate.match_score}%</div>
                </div>
                <button className="bg-slate-800 hover:bg-emerald-600 hover:text-white border border-slate-700 text-slate-200 text-xs font-semibold py-1.5 px-3 rounded transitions">
                  Assign Shift
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
