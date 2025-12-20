import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { API_URL } from '../../config';
import '../../styles/driver/DocumentVault.css';

// Document type mapping for drivers
const DOCUMENT_TYPES = [
  { value: 'cdl', label: 'CDL License' },
  { value: 'medical_card', label: 'DOT Medical Card' },
  { value: 'mvr', label: 'Motor Vehicle Record (MVR)' },
  { value: 'w9', label: 'W-9 Tax Form' },
  { value: 'drug_test', label: 'Drug Test Results' },
  { value: 'background_check', label: 'Background Check' },
  { value: 'consent', label: 'Consent Form' },
  { value: 'other', label: 'Other' }
];

export default function DocumentVault({ isPostHire, setIsPostHire }) {
  const { currentUser } = useAuth();
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [selectedDocType, setSelectedDocType] = useState('other');
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadError, setUploadError] = useState('');
  const [uploadSuccess, setUploadSuccess] = useState('');
  const [complianceScore, setComplianceScore] = useState(null);

  // Computed stats from documents
  const docStats = {
    total: docs.length,
    valid: docs.filter(d => {
      if (!d.expiry_date) return true;
      return new Date(d.expiry_date) > new Date();
    }).length,
    expiring: docs.filter(d => {
      if (!d.expiry_date) return false;
      const daysUntil = Math.ceil((new Date(d.expiry_date) - new Date()) / (1000 * 60 * 60 * 24));
      return daysUntil > 0 && daysUntil <= 30;
    }).length,
    expired: docs.filter(d => {
      if (!d.expiry_date) return false;
      return new Date(d.expiry_date) < new Date();
    }).length
  };

  // Fetch compliance score
  const fetchComplianceScore = useCallback(async () => {
    if (!currentUser) return;
    try {
      const token = await currentUser.getIdToken();
      const response = await fetch(`${API_URL}/compliance/status`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setComplianceScore(data);
      }
    } catch (error) {
      console.error('Error fetching compliance:', error);
    }
  }, [currentUser]);

  useEffect(() => { fetchComplianceScore(); }, [fetchComplianceScore]);

  // Fetch documents from API
  const fetchDocuments = useCallback(async () => {
    if (!currentUser) return;
    try {
      const token = await currentUser.getIdToken();
      const response = await fetch(`${API_URL}/documents`, {
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }
      });
      if (response.ok) {
        const data = await response.json();
        setDocs(data.documents || data || []);
      }
    } catch (error) {
      console.error('Error fetching documents:', error);
    } finally {
      setLoading(false);
    }
  }, [currentUser]);

  useEffect(() => { fetchDocuments(); }, [fetchDocuments]);

  // Handle file upload
  const handleFileUpload = async (file) => {
    if (!currentUser || !file) return;
    const allowedTypes = ['application/pdf', 'image/jpeg', 'image/png'];
    if (!allowedTypes.includes(file.type)) {
      setUploadError('Only PDF, JPG, and PNG files are allowed');
      return;
    }
    if (file.size > 25 * 1024 * 1024) {
      setUploadError('File size must be less than 25MB');
      return;
    }
    setUploading(true);
    setUploadError('');
    try {
      const token = await currentUser.getIdToken();
      const formData = new FormData();
      formData.append('file', file);
      formData.append('document_type', selectedDocType);
      const response = await fetch(`${API_URL}/documents/upload`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData
      });
      const result = await response.json();
      if (response.ok) {
        const expiryMsg = result.expiry_date ? ` Expiry date detected: ${result.expiry_date}` : '';
        setUploadSuccess(`Document uploaded successfully!${expiryMsg}`);
        setShowUploadModal(false);
        setSelectedFile(null);
        setSelectedDocType('other');
        fetchDocuments();
        setTimeout(() => setUploadSuccess(''), 5000);
      } else {
        setUploadError(result.detail || 'Failed to upload document');
      }
    } catch (error) {
      setUploadError('Failed to upload document. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  const getDocStatus = (doc) => {
    if (!doc.expiry_date) return 'Valid';
    const expiry = new Date(doc.expiry_date);
    const now = new Date();
    const daysUntilExpiry = Math.ceil((expiry - now) / (1000 * 60 * 60 * 24));
    if (daysUntilExpiry < 0) return 'Expired';
    if (daysUntilExpiry <= 30) return 'Expiring Soon';
    return 'Valid';
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const complianceDocuments = [
    {
      id: 1,
      title: "Commercial Driver's License",
      icon: "fa-solid fa-id-card",
      expires: "March 15, 2026",
      lastUpdated: "Jan 10, 2024",
      status: "Active",
      statusColor: "active",
      sharedStatus: "Not Shared Yet"
    },
    {
      id: 2,
      title: "DOT Medical Card",
      icon: "fa-solid fa-stethoscope",
      expires: "June 20, 2025",
      lastUpdated: "Dec 15, 2023",
      status: "Active",
      statusColor: "active",
      sharedStatus: "Not Shared Yet"
    },
    {
      id: 3,
      title: "Background Check",
      icon: "fa-solid fa-user-shield",
      expires: "-",
      lastUpdated: "-",
      status: "Missing",
      statusColor: "disconnected",
      description: "Required for marketplace eligibility"
    },
    {
      id: 4,
      title: "Drug Test Results",
      icon: "fa-solid fa-vial",
      expires: "-",
      lastUpdated: "-",
      status: "Missing",
      statusColor: "revoked",
      description: "Required for marketplace eligibility"
    }
  ];

  const onboardingDocuments = [
    {
      id: 1,
      title: "W-9 Tax Form",
      icon: "fa-solid fa-file-invoice",
      lastUpdated: "Jan 5, 2024",
      status: "Complete",
      statusColor: "active",
      sharedStatus: "Not Shared Yet"
    },
    {
      id: 2,
      title: "Data Sharing Consent",
      icon: "fa-solid fa-handshake",
      lastUpdated: "-",
      status: "Pending",
      statusColor: "warning",
      description: "Required before sharing profile with carriers",
      hasAction: true
    }
  ];

  const postHireComplianceDocuments = [
    {
      id: 1,
      title: "Commercial Driver License",
      status: "Active",
      statusColor: "active",
      date: "Updated: Oct 1, 2024",
      expires: "Expires: Oct 1, 2026"
    },
    {
      id: 2,
      title: "Medical Certificate",
      status: "Pending Soon",
      statusColor: "warning",
      date: "Updated: Nov 15, 2023",
      expires: "Expires: Nov 15, 2025"
    },
    {
      id: 3,
      title: "Background Check",
      status: "Active",
      statusColor: "active",
      date: "Updated: Jan 10, 2024",
      expires: "Expires: Jan 10, 2026"
    },
    {
      id: 4,
      title: "Drug Test Results",
      status: "Active",
      statusColor: "active",
      date: "Updated: Mar 5, 2024",
      expires: "Expires: Mar 5, 2026"
    }
  ];

  const postHireTripDocuments = [
    {
      id: 1,
      title: "Rate Confirmation",
      status: "Active",
      statusColor: "active",
      date: "Load #: FP-2024-519",
      carrier: "Signed with Carrier A"
    },
    {
      id: 2,
      title: "Bill of Lading",
      status: "Active",
      statusColor: "active",
      date: "Load #: FP-2024-520",
      carrier: "Morning Start"
    },
    {
      id: 3,
      title: "Proof of Delivery",
      status: "Missing",
      statusColor: "disconnected",
      date: "Load #: FP-2024-519",
      carrier: "Required by Carrier A"
    },
    {
      id: 4,
      title: "Add Document",
      status: "",
      statusColor: "",
      date: "Upload delivery reports or any",
      carrier: "additional documents"
    }
  ];

  const uploadOptions = [
    {
      icon: "fa-solid fa-id-card",
      title: "State Document",
      subtitle: "DOT card & others"
    },
    {
      icon: "fa-solid fa-upload",
      title: "Bulk Upload",
      subtitle: "Multiple documents"
    },
    {
      icon: "fa-solid fa-file-lines",
      title: "Form Preview",
      subtitle: "Available templates"
    },
    {
      icon: "fa-solid fa-folder",
      title: "File Folder",
      subtitle: "Browse files"
    }
  ];

  function PostHireDocumentView() {
    return (
      <div className={`dd-document-vault ${isDarkMode ? 'dark' : ''}`}>
        {/* Header */}
        <div className="dd-vault-header">
                  <h1>Document Vault</h1>
        <p className="dd-vault-subtitle">Manage and organize all your important documents</p>

          <button onClick={() => setIsPostHire(false)} className="btn small dd-back-btn">Back to Pre-Hire</button>
        </div>

        {/* Compliance Status Card */}
        <div className="dd-compliance-status-card">
          <div className="dd-compliance-card-header">
            <h3 className="dd-compliance-title">Compliance Status</h3>
            <span className="dd-last-updated">Last updated: 2 hours ago</span>
          </div>
          
          <div className="dd-status-summary-section">
            <div className="dd-status-info">
              <span className="dd-status-main">4/5 Documents Active</span>
              <div className="dd-status-badges">
                <span className="int-status-badge revoked">1 Expiring Soon</span>
                <span className="int-status-badge active">
                  4 Active
                </span>
                <span className="int-status-badge warning">
                  1 Expiring
                </span>
              </div>
            </div>
          </div>
          
          <div className="dd-progress-bar-container-new">
            <div className="dd-progress-bar-full">
              <div className="dd-progress-fill-full"></div>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="dd-action-buttons">
          <button className="btn small-cd" onClick={() => setShowUploadModal(true)}>
            <i className="fa-solid fa-upload"></i>
            Upload Documents
          </button>
          <button className="btn small ghost-cd">
            <i className="fa-solid fa-camera"></i>
            Scan with Camera
          </button>
          <button className="btn small ghost-cd">
            <i className="fa-solid fa-download"></i>
            Export Doc Pack
          </button>
          <select className="dd-filter-select">
            <option>All Documents</option>
            <option>Active Only</option>
            <option>Pending Only</option>
          </select>
        </div>

        {/* Upload Success Message */}
        {uploadSuccess && (
          <div style={{ background: '#dcfce7', color: '#166534', padding: '12px 20px', borderRadius: '8px', margin: '20px 0', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <i className="fa-solid fa-check-circle"></i> {uploadSuccess}
          </div>
        )}

        {/* Compliance Documents Section */}
        <div className="dd-post-hire-section">
          <div className="dd-section-header-post">
            <div className="dd-section-title-post">
              <h3>Compliance Documents</h3>
            </div>
            <span className="dd-section-count">4 documents</span>
          </div>
          
          <div className="dd-post-hire-grid">
            {postHireComplianceDocuments.map((doc) => (
              <div key={doc.id} className="dd-post-hire-card">
                <div className="dd-card-icon">
                  <i className="fa-solid fa-file-text"></i>
                </div>
                <div className="dd-card-status">
                  <span className={`int-status-badge ${doc.statusColor}`}>
                    {doc.status}
                  </span>
                </div>
                <h4 className="dd-card-title">{doc.title}</h4>
                <p className="dd-card-date">{doc.date}</p>
                <p className="dd-card-expires">{doc.expires}</p>
                <div className="dd-card-actions">
                  <button className="dd-action-btn">
                    <i className="fa-solid fa-eye"></i>
                    View
                  </button>
                  <button className="dd-action-btn">
                    <i className="fa-solid fa-download"></i>
                    Export
                  </button>
                  <button className="dd-action-btn">
                    <i className="fa-solid fa-share"></i>
                    Share
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Trip Documents Section */}
        <div className="dd-post-hire-section">
          <div className="dd-section-header-post">
            <div className="dd-section-title-post">
              <h3>Trip Documents</h3>
            </div>
            <span className="dd-section-count">3 documents</span>
          </div>
          
          <div className="dd-post-hire-grid">
            {postHireTripDocuments.map((doc) => (
              <div key={doc.id} className={`dd-post-hire-card ${doc.id === 4 ? 'dd-add-card' : ''}`}>
                {doc.id === 4 ? (
                  <>
                    <div className="dd-add-icon">
                      <i className="fa-solid fa-plus"></i>
                    </div>
                    <h4 className="dd-card-title">{doc.title}</h4>
                    <p className="dd-card-date">{doc.date}</p>
                    <p className="dd-card-carrier">{doc.carrier}</p>
                    <button className="btn small-cd">
                      <i className="fa-solid fa-upload"></i>
                      Upload
                    </button>
                  </>
                ) : (
                  <>
                    <div className="dd-card-icon">
                      <i className="fa-solid fa-file-text"></i>
                    </div>
                    <div className="dd-card-status">
                      <span className={`int-status-badge ${doc.statusColor}`}>
                        {doc.status}
                      </span>
                    </div>
                    <h4 className="dd-card-title">{doc.title}</h4>
                    <p className="dd-card-date">{doc.date}</p>
                    <p className="dd-card-carrier">{doc.carrier}</p>
                    <div className="dd-card-actions">
                      <button className="dd-action-btn">
                        <i className="fa-solid fa-eye"></i>
                        View
                      </button>
                      <button className="dd-action-btn">
                        <i className="fa-solid fa-download"></i>
                        Export
                      </button>
                      <button className="dd-action-btn">
                        <i className="fa-solid fa-share"></i>
                        Share
                      </button>
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (isPostHire) {
    return <PostHireDocumentView />;
  }

  return (
    <div className={`dd-document-vault ${isDarkMode ? 'dark' : ''}`}>
      {/* Header */}
      <div className="dd-vault-header">
        <h1>Document Vault</h1>
        <p className="dd-vault-subtitle">Manage and organize all your important documents</p>
        <button onClick={() => setIsPostHire(true)} className="btn dd-post-hire-btn">Post Hire</button>
      </div>

      {/* Compliance Score & Document Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px', marginBottom: '20px' }}>
        <div style={{ background: 'linear-gradient(135deg, #3b82f6, #1d4ed8)', borderRadius: '12px', padding: '20px', color: '#fff' }}>
          <div style={{ fontSize: '14px', opacity: 0.9, marginBottom: '8px' }}>
            <i className="fa-solid fa-shield-halved" style={{ marginRight: '8px' }}></i>
            Compliance Score
          </div>
          <div style={{ fontSize: '36px', fontWeight: '700' }}>
            {complianceScore ? `${complianceScore.compliance_score}%` : '—'}
          </div>
          <div style={{ fontSize: '12px', opacity: 0.8, marginTop: '4px' }}>
            {complianceScore?.is_compliant ? '✓ Compliant' : 'Review needed'}
          </div>
        </div>
        <div style={{ background: '#fff', borderRadius: '12px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          <div style={{ fontSize: '14px', color: '#64748b', marginBottom: '8px' }}>
            <i className="fa-solid fa-file" style={{ marginRight: '8px' }}></i>Total Documents
          </div>
          <div style={{ fontSize: '28px', fontWeight: '700', color: '#1e293b' }}>{docStats.total}</div>
        </div>
        <div style={{ background: '#fff', borderRadius: '12px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          <div style={{ fontSize: '14px', color: '#22c55e', marginBottom: '8px' }}>
            <i className="fa-solid fa-check-circle" style={{ marginRight: '8px' }}></i>Valid
          </div>
          <div style={{ fontSize: '28px', fontWeight: '700', color: '#22c55e' }}>{docStats.valid}</div>
        </div>
        <div style={{ background: '#fff', borderRadius: '12px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          <div style={{ fontSize: '14px', color: '#f59e0b', marginBottom: '8px' }}>
            <i className="fa-solid fa-clock" style={{ marginRight: '8px' }}></i>Expiring Soon
          </div>
          <div style={{ fontSize: '28px', fontWeight: '700', color: '#f59e0b' }}>{docStats.expiring}</div>
        </div>
        <div style={{ background: '#fff', borderRadius: '12px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          <div style={{ fontSize: '14px', color: '#ef4444', marginBottom: '8px' }}>
            <i className="fa-solid fa-exclamation-triangle" style={{ marginRight: '8px' }}></i>Expired
          </div>
          <div style={{ fontSize: '28px', fontWeight: '700', color: '#ef4444' }}>{docStats.expired}</div>
        </div>
      </div>

      {/* AI Marketplace Readiness Check */}
      {complianceScore && !complianceScore.is_compliant && (
        <div className="card" style={{ marginBottom: '20px', borderLeft: '4px solid #f59e0b' }}>
          <div style={{ padding: '16px' }}>
            <h4 style={{ margin: '0 0 12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <i className="fa-solid fa-robot" style={{ color: '#3b82f6' }}></i>
              AI Marketplace Readiness Check
            </h4>
            <p style={{ margin: '0 0 12px', color: '#64748b' }}>
              Documents needed for marketplace eligibility:
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {complianceScore.issues?.map((issue, idx) => (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#dc2626' }}>
                  <i className="fa-solid fa-exclamation-circle"></i>
                  <span>{issue}</span>
                </div>
              ))}
            </div>
            <button className="btn small-cd" style={{ marginTop: '16px' }} onClick={() => setShowUploadModal(true)}>
              Upload Missing Documents
            </button>
          </div>
        </div>
      )}

      {/* Document Grid */}
      <div className="dd-documents-grid">
        {/* Compliance Documents */}
        <div className="dd-document-section-new">
          <div className="dd-section-header-new">
            <h3>Compliance Documents</h3>
          </div>
          
          <div className="dd-document-cards-grid">
            {complianceDocuments.map((doc) => (
              <div key={doc.id} className={`dd-document-card ${doc.status === 'Missing' ? 'dd-missing-doc' : ''}`}>
                <div className="dd-doc-header">
                  <i className={`${doc.icon} dd-doc-icon`}></i>
                  <span className={`int-status-badge ${doc.statusColor}`}>
                    {doc.status}
                  </span>
                </div>
                <h4 className="dd-doc-title-new">{doc.title}</h4>
                
                {doc.status !== 'Missing' ? (
                  <>
                    <p className="dd-doc-expires-new">Expires: {doc.expires}</p>
                    <p className="dd-doc-updated-new">Last Updated: {doc.lastUpdated}</p>
                    <div className="dd-doc-shared">
                      <span className="dd-shared-status">{doc.sharedStatus}</span>
                      <div className="dd-doc-buttons">
                        <button className="btn small ghost-cd">View</button>
                        <button className="btn small ghost-cd">Replace</button>
                      </div>
                    </div>
                  </>
                ) : (
                  <>
                    <p className="dd-doc-description">{doc.description}</p>
                    <button className="btn small-cd"style={{width:"100%"}}>Upload Document</button>
                  </>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Onboarding Documents */}
        <div className="dd-document-section-new">
          <div className="dd-section-header-new">
            <h3>Onboarding Documents</h3>
          </div>
          
          <div className="dd-document-cards-grid">
            {onboardingDocuments.map((doc) => (
              <div key={doc.id} className={`dd-document-card ${doc.status === 'Pending' ? 'dd-pending-doc' : ''}`}>
                <div className="dd-doc-header">
                  <i className={`${doc.icon} dd-doc-icon`}></i>
                  <span className={`int-status-badge ${doc.statusColor}`}>
                    {doc.status}
                  </span>
                </div>
                <h4 className="dd-doc-title-new">{doc.title}</h4>
                
                {doc.status === 'Complete' ? (
                  <>
                    <p className="dd-doc-updated-new">Last Updated: {doc.lastUpdated}</p>
                    <div className="dd-doc-shared">
                      <span className="dd-shared-status">{doc.sharedStatus}</span>
                      <div className="dd-doc-buttons">
                        <button className="btn small ghost-cd">View</button>
                        <button className="btn small ghost-cd">Replace</button>
                      </div>
                    </div>
                  </>
                ) : (
                  <>
                    <p className="dd-doc-description">{doc.description}</p>
                    <button className="btn small-cd"style={{width:"100%"}}>Sign Consent Form</button>
                  </>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Quick Upload Options */}
      <div className="card dd-upload-options-card">
        <div className="card-header">
          <h3>Quick Upload Options</h3>
        </div>
        <div className="dd-upload-grid">
          {uploadOptions.map((option, index) => (
            <div key={index} className="dd-upload-option">
              <i className={`${option.icon} dd-upload-icon`}></i>
              <div className="dd-upload-text">
                <h4>{option.title}</h4>
                <p>{option.subtitle}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Consent Request */}
      <div className="card dd-consent-card">
        <div className="dd-consent-content">
          <i className="fa-solid fa-exclamation-triangle dd-consent-icon"></i>
          <div className="dd-consent-text">
            <h4>Consent Required for Marketplace</h4>
            <p>You must provide consent to share your documents with carriers, you may opt out and skip sharing without fees. This ensures your privacy and gives you control over your information.</p>
          </div>
        </div>
        <button className="btn dd-give-consent-btn">Give Consent</button>
      </div>

      {/* Upload Modal */}
      {showUploadModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#fff', borderRadius: '12px', padding: '30px', maxWidth: '500px', width: '90%', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)' }}>
            <h3 style={{ margin: '0 0 20px', color: '#1e293b' }}>Upload Document</h3>
            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500', color: '#374151' }}>Document Type *</label>
              <select value={selectedDocType} onChange={(e) => setSelectedDocType(e.target.value)} style={{ width: '100%', padding: '10px 12px', borderRadius: '8px', border: '1px solid #d1d5db' }}>
                {DOCUMENT_TYPES.map(dt => (<option key={dt.value} value={dt.value}>{dt.label}</option>))}
              </select>
            </div>
            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500', color: '#374151' }}>Select File *</label>
              <input type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={(e) => { if (e.target.files[0]) setSelectedFile(e.target.files[0]); }} style={{ width: '100%' }} />
              {selectedFile && <p style={{ margin: '8px 0 0', fontSize: '14px', color: '#059669' }}><i className="fa-solid fa-file" style={{ marginRight: '6px' }}></i>{selectedFile.name}</p>}
              <p style={{ margin: '8px 0 0', fontSize: '12px', color: '#6b7280' }}><i className="fa-solid fa-magic" style={{ marginRight: '6px' }}></i>Expiry date will be automatically extracted using AI.</p>
            </div>
            {uploadError && <div style={{ color: '#dc2626', marginBottom: '15px', fontSize: '14px' }}>{uploadError}</div>}
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
              <button onClick={() => { setShowUploadModal(false); setUploadError(''); setSelectedFile(null); }} style={{ padding: '10px 20px', borderRadius: '8px', border: '1px solid #d1d5db', background: '#fff', cursor: 'pointer' }}>Cancel</button>
              <button onClick={() => { if (selectedFile) handleFileUpload(selectedFile); else setUploadError('Please select a file'); }} disabled={uploading || !selectedFile} style={{ padding: '10px 20px', borderRadius: '8px', border: 'none', background: uploading || !selectedFile ? '#9ca3af' : '#3b82f6', color: '#fff', cursor: uploading || !selectedFile ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', gap: '8px' }}>
                {uploading ? <><i className="fa-solid fa-spinner fa-spin"></i>Uploading...</> : <><i className="fa-solid fa-upload"></i>Upload</>}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Uploaded Documents Table */}
      <div className="card" style={{ marginTop: '20px' }}>
        <div className="card-header">
          <h3>Your Uploaded Documents</h3>
          <span className="dd-section-count">{docs.length} documents</span>
        </div>
        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center' }}>
            <i className="fa-solid fa-spinner fa-spin" style={{ fontSize: '2rem', color: '#3b82f6' }}></i>
            <p style={{ marginTop: '10px', color: '#64748b' }}>Loading documents...</p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: '600', color: '#475569' }}>File name</th>
                <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: '600', color: '#475569' }}>Type</th>
                <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: '600', color: '#475569' }}>Expiry date</th>
                <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: '600', color: '#475569' }}>Status</th>
                <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: '600', color: '#475569' }}>Uploaded</th>
              </tr>
            </thead>
            <tbody>
              {docs.length === 0 ? (
                <tr><td colSpan="5" style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>
                  <i className="fa-regular fa-folder-open" style={{ fontSize: '2rem', marginBottom: '10px', display: 'block' }}></i>
                  No documents uploaded yet. Click "Upload Documents" to get started.
                </td></tr>
              ) : docs.map((d) => (
                <tr key={d.id} style={{ borderBottom: '1px solid #e2e8f0' }}>
                  <td style={{ padding: '12px 16px' }}>{d.filename || d.file_name || d.original_filename}</td>
                  <td style={{ padding: '12px 16px' }}>{(d.type || d.document_type || 'other').replace(/_/g, ' ').toUpperCase()}</td>
                  <td style={{ padding: '12px 16px' }}>{formatDate(d.expiry_date)}</td>
                  <td style={{ padding: '12px 16px' }}>
                    <span className={`int-status-badge ${getDocStatus(d) === 'Valid' ? 'active' : getDocStatus(d) === 'Expired' ? 'revoked' : 'warning'}`}>
                      {getDocStatus(d)}
                    </span>
                  </td>
                  <td style={{ padding: '12px 16px' }}>{formatDate(d.created_at || d.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}