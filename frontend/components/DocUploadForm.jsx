import React, { useState } from 'react';

export default function DocUploadForm({ credentialId, onUploadSuccess }) {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [statusMsg, setStatusMsg] = useState({ type: '', text: '' });

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile && selectedFile.type !== 'application/pdf') {
      setStatusMsg({ type: 'error', text: 'Only PDF structures are accepted for OHCQ audits.' });
      setFile(null);
    } else {
      setFile(selectedFile);
      setStatusMsg({ type: '', text: '' });
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) return;

    setUploading(true);
    setStatusMsg({ type: '', text: '' });

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`/api/v1/documents/${credentialId}/upload-pdf`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (response.ok) {
        setStatusMsg({ type: 'success', text: 'Document uploaded and logged successfully!' });
        setFile(null);
        if (onUploadSuccess) onUploadSuccess(data);
      } else {
        setStatusMsg({ type: 'error', text: data.detail || 'Upload failed.' });
      }
    } catch (err) {
      setStatusMsg({ type: 'error', text: 'Network connection failure during file transmission.' });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="bg-slate-800 p-6 rounded-xl border border-slate-700/60 shadow-lg">
      <h3 className="text-md font-bold text-white mb-2">Upload Compliance Certification</h3>
      <p className="text-xs text-slate-400 mb-4">Upload verified credential verification artifacts (PDF format only, Max 5MB).</p>
      
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="border-2 border-dashed border-slate-600 hover:border-emerald-500 rounded-lg p-4 transition text-center bg-slate-900/40">
          <input 
            type="file" 
            accept=".pdf" 
            onChange={handleFileChange} 
            className="hidden" 
            id="pdf-upload-input"
          />
          <label htmlFor="pdf-upload-input" className="cursor-pointer block text-sm text-slate-300">
            {file ? `📄 ${file.name}` : 'Drag & drop compliance document here or click to browse'}
          </label>
        </div>

        {statusMsg.text && (
          <div className={`text-xs px-3 py-2 rounded font-medium ${statusMsg.type === 'success' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>
            {statusMsg.text}
          </div>
        )}

        <button
          type="submit"
          disabled={!file || uploading}
          className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-semibold py-2 px-4 rounded-lg text-sm disabled:opacity-40 disabled:cursor-not-allowed transition shadow-md"
        >
          {uploading ? 'Streaming File Data...' : 'Submit to Compliance Log'}
        </button>
      </form>
    </div>
  );
}
