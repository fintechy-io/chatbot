import { useState, useEffect } from 'react';
import { UploadCloud, File, CheckCircle, XCircle, ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8923';

function AdminPage() {
  const [selectedFiles, setSelectedFiles] = useState([]);
  
  // polling state
  const [jobId, setJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null); // 'queued', 'processing', 'completed', 'error'
  const [progress, setProgress] = useState(0);
  const [currentFileText, setCurrentFileText] = useState('');
  const [uploadResults, setUploadResults] = useState(null);

  const handleFileSelect = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFiles(Array.from(e.target.files));
      setUploadResults(null);
      setJobId(null);
      setJobStatus(null);
      setProgress(0);
    }
  };

  const handleUploadBatch = async () => {
    if (selectedFiles.length === 0) return;

    setJobStatus('queued');
    setProgress(0);
    setUploadResults(null);

    const formData = new FormData();
    selectedFiles.forEach(file => {
      formData.append('files', file);
    });

    try {
      const response = await fetch(`${API_URL}/upload/batch`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Batch upload failed: ${response.statusText}`);
      }

      const data = await response.json();
      setJobId(data.job_id);
    } catch (error) {
      setJobStatus('error');
      setUploadResults({ error: error.message });
    }
  };

  useEffect(() => {
    let intervalId;
    
    const pollStatus = async () => {
      if (!jobId || jobStatus === 'completed' || jobStatus === 'error') {
        return;
      }
      
      try {
        const response = await fetch(`${API_URL}/upload/status/${jobId}`);
        if (!response.ok) throw new Error("Status check failed");
        
        const data = await response.json();
        setJobStatus(data.status);
        setProgress(data.progress);
        setCurrentFileText(data.current_file);
        
        if (data.status === 'completed') {
          setUploadResults(data);
          setJobId(null);
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    };

    if (jobId && jobStatus !== 'completed' && jobStatus !== 'error') {
      intervalId = setInterval(pollStatus, 1000); // Poll every second
    }

    return () => clearInterval(intervalId);
  }, [jobId, jobStatus]);

  const isUploading = jobStatus === 'queued' || jobStatus === 'processing';

  return (
    <div className="admin-container">
      <div className="admin-header">
        <Link to="/" className="back-link"><ArrowLeft size={20} /> Back to Chat</Link>
        <h1>Data Ingestion Admin</h1>
        <p>Upload PDFs, Images, Excel sheets, Word docs, CSVs and more to process and embed them into the vector database.</p>
      </div>

      <div className="admin-content">
        <div className="upload-section">
          <label className={`mass-upload-zone ${isUploading ? 'disabled' : ''}`}>
            <input 
              type="file" 
              multiple
              accept="image/*,.pdf,.txt,.docx,.doc,.xlsx,.xls,.csv,.pptx,.ppt,.md,.html,.rtf,.eml"
              style={{ display: 'none' }} 
              onChange={handleFileSelect}
              disabled={isUploading}
            />
            <UploadCloud className="upload-icon" size={48} />
            <div className="upload-text">
              Click to browse files (Multiple allowed)
            </div>
            <div className="upload-subtext">PDF, Word (DOCX), Excel (XLSX/CSV), PPT, Images (JPG/PNG), TXT, HTML & more</div>
          </label>

          {selectedFiles.length > 0 && (
            <div className="selected-files">
              <h3>Selected Files ({selectedFiles.length})</h3>
              <ul className="file-list">
                {selectedFiles.map((file, idx) => (
                  <li key={idx}>
                    <File size={16} /> {file.name} ({(file.size / 1024 / 1024).toFixed(2)} MB)
                  </li>
                ))}
              </ul>
              
              {!isUploading && !uploadResults && (
                <button 
                  className="mass-upload-button"
                  onClick={handleUploadBatch}
                >
                  Upload & Process All
                </button>
              )}

              {isUploading && (
                <div className="progress-container">
                  <div className="progress-header">
                    <span>Processing {currentFileText}</span>
                    <span>{progress}%</span>
                  </div>
                  <div className="progress-bar-bg">
                    <div 
                      className="progress-bar-fill" 
                      style={{ width: `${progress}%` }}
                    ></div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {uploadResults && (
          <div className="results-section">
            <h3>Ingestion Results</h3>
            {uploadResults.error ? (
              <div className="status-message error">{uploadResults.error}</div>
            ) : (
              <>
                <div className="status-message success">
                  Successfully ingested {uploadResults.total_chunks_ingested} total chunks!
                </div>
                <div className="results-grid">
                  {uploadResults.results.map((res, idx) => (
                    <div key={idx} className={`result-card ${res.status}`}>
                      <div className="result-icon">
                        {res.status === 'success' ? <CheckCircle color="#10b981" /> : <XCircle color="#ef4444" />}
                      </div>
                      <div className="result-details">
                        <h4>{res.filename}</h4>
                        {res.status === 'success' ? (
                          <span>Processed {res.chunks} chunks</span>
                        ) : (
                          <span className="error-text">{res.message}</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default AdminPage;
