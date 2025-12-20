import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { API_URL } from '../../config';

import DocumentVault from './DocumentVault';
import Marketplace from './Marketplace';
import MyCarrier from './MyCarrier';
import HiringOnboarding from './HiringOnboarding';
import AccountSettings from './AccountSettings';
import AiHub from './AiHub';
import ConsentESignature from './ConsentESignature';
// OnboardingCoach removed - compliance data now shown in Compliance & Safety page
import '../../styles/driver/DriverDashboard.css';
import logo from '/src/assets/logo.png';
import resp_logo from '/src/assets/logo_1.png';

export default function DriverDashboard() {
  const { currentUser } = useAuth();
  const [activeNav, setActiveNav] = useState('home');
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [isPostHire, setIsPostHire] = useState(false);

  // Onboarding data state
  const [driverProfile, setDriverProfile] = useState(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [onboardingScore, setOnboardingScore] = useState(null);

  // Fetch onboarding data on mount
  useEffect(() => {
    const fetchProfile = async () => {
      if (!currentUser) {
        setProfileLoading(false);
        return;
      }
      try {
        const token = await currentUser.getIdToken();
        const response = await fetch(`${API_URL}/onboarding/data`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });
        if (response.ok) {
          const data = await response.json();
          setDriverProfile(data);
          if (typeof data.onboarding_score !== 'undefined') {
            setOnboardingScore(data.onboarding_score);
          }
        }

        // Fetch onboarding coach for progress/score if available
        const coachRes = await fetch(`${API_URL}/onboarding/coach-status`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (coachRes.ok) {
          const coach = await coachRes.json();
          if (typeof coach.total_score !== 'undefined') {
            setOnboardingScore(coach.total_score);
          }
        }
      } catch (error) {
        console.error('Error fetching profile:', error);
      } finally {
        setProfileLoading(false);
      }
    };
    fetchProfile();
  }, [currentUser]);

  const navGroups = [
    {
      title: 'OPERATIONS',
      items: [
        { key: 'home', label: 'My Loads', icon: 'fa-solid fa-house' },
        { key: 'docs', label: 'Document Vault', icon: 'fa-solid fa-folder' },
        { key: 'marketplace', label: 'Marketplace', icon: 'fa-solid fa-store' },
      ]
    },
    {
      title: 'MANAGEMENT',
      items: [
        { key: 'carrier', label: 'My Carrier', icon: 'fa-solid fa-building' },
        { key: 'compliance', label: 'Compliance & Safety', icon: 'fa-solid fa-shield-halved' },
        { key: 'hiring', label: 'Hiring & Onboarding', icon: 'fa-solid fa-user-plus' },
        { key: 'esign', label: 'Consent & E-Signature', icon: 'fa-solid fa-pen-fancy' }
      ]
    },
    {
      title: 'SUPPORT',
      items: [
        { key: 'settings', label: 'Account & Settings', icon: 'fa-solid fa-gear' },
        { key: 'help', label: 'AI Hub', icon: 'fa-solid fa-robot' }
      ]
    }
  ];

  function HomeView() {
    return (
      <>
        <header className="fp-header">
          <div className="fp-header-titles">
            <h2>
              <span role="img" aria-label="wave">👋</span>
              Welcome to FreightPower, Marcus!
            </h2>
            <p className="fp-subtitle">Complete your onboarding to start connecting with carriers and finding loads.</p>
            <button onClick={() => setIsPostHire(true)} className="btn small green-btn">Post Hire</button>
          </div>
        </header>

        {/* Driver Profile Card - Shows onboarding data */}
        {!profileLoading && driverProfile && driverProfile.data && (
          <section style={{ marginBottom: '20px' }}>
            <div className="card" style={{ padding: '20px', background: '#f8fafc' }}>
              <div className="card-header">
                <h3><i className="fa-solid fa-user" style={{ marginRight: '8px' }}></i>Driver Profile</h3>
                {onboardingScore !== null && (
                  <div className="pill" style={{ background:'#e0f2fe', color:'#075985', padding:'6px 10px', borderRadius:'999px', fontWeight:600 }}>
                    Onboarding Score: {Math.round(onboardingScore)}%
                  </div>
                )}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginTop: '16px' }}>
                {driverProfile.data.fullName && (
                  <div><strong>Name:</strong> {driverProfile.data.fullName}</div>
                )}
                {driverProfile.data.cdlNumber && (
                  <div><strong>CDL Number:</strong> {driverProfile.data.cdlNumber}</div>
                )}
                {driverProfile.data.cdlClass && (
                  <div><strong>CDL Class:</strong> {driverProfile.data.cdlClass}</div>
                )}
                {driverProfile.data.issuingState && (
                  <div><strong>Issuing State:</strong> {driverProfile.data.issuingState}</div>
                )}
                {driverProfile.data.preferredRegions && (
                  <div><strong>Preferred Regions:</strong> {driverProfile.data.preferredRegions}</div>
                )}
                {driverProfile.data.equipmentExperience && (
                  <div><strong>Equipment Experience:</strong> {driverProfile.data.equipmentExperience}</div>
                )}
              </div>
              {!driverProfile.onboarding_completed && (
                <div style={{ marginTop: '16px', padding: '12px', background: '#fef3c7', borderRadius: '8px', color: '#92400e' }}>
                  <i className="fa-solid fa-exclamation-triangle" style={{ marginRight: '8px' }}></i>
                  Onboarding not complete. <a href="/driver-onboarding" style={{ color: '#1d4ed8', textDecoration: 'underline' }}>Complete now</a>
                </div>
              )}
            </div>
          </section>
        )}

        {/* Onboarding Coach removed - compliance data now shown in Compliance & Safety page */}

        <section className="fp-grid">
          {/* Onboarding Progress Card */}
          <div className="card dd-onboarding-card span-3">
            <div className="dd-onboarding-progress">
              <span className="dd-progress-title">Onboarding Progress</span>
              <span className="dd-progress-percent">70% Complete</span>
            </div>
            <div className="dd-progress-bar">
              <div className="dd-progress-bar-inner" />
            </div>
            <div className="dd-onboarding-steps">
              <div className="dd-step dd-step-complete">
                  <i className="fa-solid fa-check-circle dd-step-complete-icon-fa"></i>
                <div className="dd-step-title">Docs Uploaded</div>
                <div className="dd-step-status">Complete</div>
              </div>
              <div className="dd-step dd-step-inprogress">
                  <i className="fa-solid fa-hourglass-half dd-step-inprogress-icon-fa"></i>
                <div className="dd-step-title">Consent Given</div>
                <div className="dd-step-status">In Progress</div>
              </div>
              <div className="dd-step dd-step-pending">
                  <i className="fa-regular fa-circle dd-step-pending-icon-fa"></i>
                <div className="dd-step-title">Availability On</div>
                <div className="dd-step-status">Pending</div>
              </div>
            </div>
            <button className="btn small-cd">Continue Onboarding</button>
          </div>

          {/* Marketplace Activity */}
          <div className="card dd-marketplace-card">
            <div className="card-header">
              <h3>Marketplace Activity</h3>
              <span className="dd-marketplace-new dd-marketplace-green">3 New</span>
            </div>
            <div className="dd-marketplace-content dd-center dd-marketplace-padding">
              <div className="dd-marketplace-eye">
                <i className="fa-solid fa-eye dd-marketplace-eye-icon"></i>
              </div>
              <div className="dd-marketplace-viewed">3 Carriers Viewed You</div>
              <div className="dd-marketplace-desc">
                This week carriers have shown interest in your profile
              </div>
              <button className="btn small-cd">View Marketplace</button>
            </div>
          </div>

          {/* AI Suggestions */}
          <div className="card dd-ai-suggestions-card">
            <div className="card-header">
              <h3>AI Suggestions</h3>
            </div>
            <div className="dd-ai-suggestion">
              <div className="dd-suggestion-title">Medical Card Expiring</div>
              <div className="dd-suggestion-text">Expires in 15 days</div>
            </div>
            <div className="dd-ai-suggestion">
              <div className="dd-suggestion-title">Profile Tip</div>
              <div className="dd-suggestion-text">Add experience details to attract carriers</div>
            </div>
            <div className="dd-ai-suggestion">
              <div className="dd-suggestion-title">Marketplace Ready</div>
              <div className="dd-suggestion-text">Turn on availability to be discovered</div>
            </div>
          </div>

          {/* Service Providers */}
          <div className="card dd-service-providers-card">
            <div className="card-header">
              <h3>Service Providers</h3>
              <span className="view-all">View All</span>
            </div>
            <div className="dd-service-grid">
              <div className="dd-service-item dd-center">
                <i className="fa-solid fa-gavel" />
                <div>Legal Help</div>
              </div>
              <div className="dd-service-item dd-center">
                <i className="fa-solid fa-wrench" />
                <div>Roadside</div>
              </div>
              <div className="dd-service-item dd-center">
                <i className="fa-solid fa-parking" />
                <div>Parking</div>
              </div>
              <div className="dd-service-item dd-center">
                <i className="fa-solid fa-gas-pump" />
                <div>Fuel</div>
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="card dd-quick-actions-card span-3">
            <div className="card-header">
              <h3>Quick Actions</h3>
            </div>
            <div className="dd-quick-actions">
              <button className="btn small-cd">
                <i className="fa-solid fa-upload"></i>
                Upload Document
              </button>
              <button className="btn small-cd">
                <i className="fa-solid fa-store"></i>
                Browse Marketplace
              </button>
              <button className="btn small-cd">
                <i className="fa-solid fa-pen"></i>
                Complete Consent
              </button>
              <button className="btn small ghost-cd">
                <i className="fa-solid fa-headset"></i>
                Get Support
              </button>
            </div>
          </div>
        </section>
      </>
    );
  }

  function PostHireView() {
    return (
      <>
        <header className="fp-header">
          <div className="fp-header-titles">
            <button onClick={() => setIsPostHire(false)} className="btn small">Back to Pre-Hire</button>
          </div>
        </header>

        {/* Active Load Card - Full Width */}
        <div className="card dd-active-load-card">
          <div className="dd-active-load-header">
            <h3>Active Load - Chicago to Denver</h3>
            <span className="dd-load-status">In Transit</span>
          </div>
          <div className="dd-active-load-content">
            <div className="dd-load-info-grid">
              <div className="dd-load-info-item">
                <span className="dd-info-label">Pickup</span>
                <span className="dd-info-value">Chicago, IL</span>
                <span className="dd-info-status">Completed ✓</span>
              </div>
              <div className="dd-load-info-item">
                <span className="dd-info-label">Delivery</span>
                <span className="dd-info-value">Denver, CO</span>
                <span className="dd-info-status">ETA: 6:30 PM</span>
              </div>
              <div className="dd-load-info-item">
                <span className="dd-info-label">Distance</span>
                <span className="dd-info-value">287 miles left</span>
                <span className="dd-info-status">920 total miles</span>
              </div>
              <div className="dd-load-info-item">
                <span className="dd-info-label">Rate</span>
                <span className="dd-info-value">$2,300</span>
                <span className="dd-info-status">$2.50/mile</span>
              </div>
            </div>
            <div className="dd-load-actions">
              <button className="btn small ghost-cd dd-btn">
                <i className="fa-solid fa-location-arrow"></i>
                Navigate
              </button>
              <button className="btn small ghost-cd dd-btn">
                <i className="fa-solid fa-upload"></i>
                Upload POD
              </button>
              <button className="btn small ghost-cd dd-btn">
                <i className="fa-solid fa-comment"></i>
                Message Dispatch
              </button>
            </div>
          </div>
        </div>

        {/* Two Column Layout */}
        <div className="dd-two-column-layout">
          {/* Left Column */}
          <div className="dd-left-column">
            {/* Load Summary */}
            <div className="dd-load-summary-section">
              <h3 className="dd-section-title">Load Summary</h3>
              <div className="card dd-load-summary-card dd-no-header">
                <div className="dd-summary-stats-horizontal">
                  <div className="dd-stat-item-horizontal">
                    <div className="dd-stat-number-large">2</div>
                    <div className="dd-stat-label-horizontal">Assigned</div>
                  </div>
                  <div className="dd-stat-item-horizontal">
                    <div className="dd-stat-number-large">1</div>
                    <div className="dd-stat-label-horizontal">In Transit</div>
                  </div>
                  <div className="dd-stat-item-horizontal">
                    <div className="dd-stat-number-large">12</div>
                    <div className="dd-stat-label-horizontal">Completed</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Route Cards */}
            <div className="card dd-route-card">
              <div className="dd-route-header">
                <h4>Denver to Phoenix</h4>
                <span className="int-status-badge active">Assigned</span>
              </div>
              <div className="dd-route-info">
                <div className="dd-route-details">
                  <div>Pickup: Nov 15, 8:00 AM</div>
                  <div>Delivery: Nov 16, 2:00 PM</div>
                  <div>Rate: $1,850</div>
                </div>
                <div className="dd-route-actions">
                  <button className="btn small-cd">Start Trip</button>
                  <button className="btn small ghost-cd">View Details</button>
                </div>
              </div>
            </div>

            <div className="card dd-route-card">
              <div className="dd-route-header">
                <h4>Phoenix to Los Angeles</h4>
                <span className="int-status-badge warning">Pending</span>
              </div>
              <div className="dd-route-info">
                <div className="dd-route-details">
                  <div>Pickup: Nov 17, 10:00 AM</div>
                  <div>Delivery: Nov 17, 6:00 PM</div>
                  <div>Rate: $950</div>
                </div>
                <div className="dd-route-actions">
                  <button className="btn small ghost-cd">View Details</button>
                </div>
              </div>
            </div>

            {/* Live Route Tracking */}
            <div className="card dd-live-route-card">
              <div className="dd-section-title">
                <h3>Live Route Tracking</h3>
              </div>
              <div className="dd-live-route-content">
                <div className="dd-map-placeholder">
                  <i className="fa-solid fa-map-location-dot dd-map-icon"></i>
                  <div className="dd-map-text">
                    <div className="dd-map-title">Interactive map with real-time GPS tracking</div>
                    <div className="dd-map-location">Current location: I-76 W, Mile 287</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column */}
          <div className="dd-right-column">
            {/* Compliance Status */}
            <div className="card dd-compliance-card">
              <div className="dd-section-title">
                <h3>Compliance Status</h3>
              </div>
              <div className="dd-compliance-items">
                <div className="dd-compliance-item ">
                  <i className="fa-solid fa-id-card"></i>
                  <span>CDL License</span>
                  <i className="fa-solid fa-check"></i>
                </div>
                <div className="dd-compliance-item ">
                  <i className="fa-solid fa-file-medical"></i>
                  <span>Medical Card</span>
                  <i className="fa-solid fa-exclamation-triangle"></i>
                </div>
                <div className="dd-compliance-item">
                  <i className="fa-solid fa-search"></i>
                  <span>Drug Test</span>
                  <i className="fa-solid fa-check"></i>
                </div>
                <div className="dd-compliance-item">
                  <i className="fa-solid fa-clipboard-check"></i>
                  <span>Background Check</span>
                  <i className="fa-solid fa-check"></i>
                </div>
              </div>
              <button className="btn small-cd" style={{width: '100%'}}>View All Documents</button>
            </div>

            {/* Messages & Alerts Section */}
            <div className="dd-messages-alerts-section">
              <h3 className="dd-section-title">Messages & Alerts</h3>
              
              {/* Route Update Card */}
              <div className="card dd-message-card dd-route-update-card">
                <div className="dd-message-icon ">
                  <i className="fa-solid fa-route"></i>
                </div>
                <div className="dd-message-content">
                  <div className="dd-message-title">Route Update</div>
                  <div className="dd-message-text">Traffic ahead on I-76. Alternative route suggested.</div>
                </div>
              </div>

              {/* Medical Card Expiring Card */}
              <div className="card dd-message-card dd-medical-warning-card">
                <div className="dd-message-icon ">
                  <i className="fa-solid fa-exclamation-triangle"></i>
                </div>
                <div className="dd-message-content">
                  <div className="dd-message-title">Medical Card Expiring</div>
                  <div className="dd-message-text">Expires in 15 days. Schedule renewal now.</div>
                </div>
              </div>

              {/* Carrier Message Card */}
              <div className="card dd-message-card dd-carrier-message-card">
                <div className="dd-message-icon ">
                  <i className="fa-solid fa-comment"></i>
                </div>
                <div className="dd-message-content">
                  <div className="dd-message-title">Carrier Message</div>
                  <div className="dd-message-text">Great job on the Chicago delivery!</div>
                </div>
              </div>
            </div>

            {/* AI Suggestions Card */}
              <div className="card dd-ai-suggestions-separate-card">
                <div className="dd-section-title">
                  <span>AI Suggestions</span>
                </div>
                <div className="dd-suggestion-item">
                  <div className="dd-suggestion-title">Fuel Stop Recommended</div>
                  <div className="dd-suggestion-text">Pilot at Exit 142 - Best price in 50 miles ahead</div>
                  <button className="dd-suggestion-link">Navigate</button>
                </div>
                <div className="dd-suggestion-item">
                  <div className="dd-suggestion-title">Break Required Soon</div>
                  <div className="dd-suggestion-text">30-min break needed in 45 minutes</div>
                  <button className="dd-suggestion-link">Find Rest Areas</button>
                </div>
              </div>
          </div>
        </div>
      </>
    );
  }

  // Driver Compliance View Component
  function DriverComplianceView() {
    const [loading, setLoading] = useState(true);
    const [complianceStatus, setComplianceStatus] = useState({
      score: 0, breakdown: {}, status_color: 'Red', documents: [], issues: [], warnings: [], recommendations: []
    });
    const [complianceData, setComplianceData] = useState({
      cdlNumber: '', cdlState: '', cdlClass: '', cdlExpiry: '', medicalCardExpiry: '',
      drugTestStatus: 'pending', mvrStatus: 'pending', clearinghouseStatus: 'pending'
    });
    const [complianceTasks, setComplianceTasks] = useState([]);
    const [aiAnalysis, setAiAnalysis] = useState(null);
    const [analyzingAI, setAnalyzingAI] = useState(false);

    useEffect(() => {
      if (!currentUser) return;
      const fetchData = async () => {
        setLoading(true);
        try {
          const token = await currentUser.getIdToken();
          const statusRes = await fetch(`${API_URL}/compliance/status`, {
            headers: { 'Authorization': `Bearer ${token}` }
          });
          if (statusRes.ok) {
            const data = await statusRes.json();
            setComplianceStatus({
              score: data.compliance_score || 0, breakdown: data.score_breakdown || {},
              status_color: data.status_color || 'Red', documents: data.documents || [],
              issues: data.issues || [], warnings: data.warnings || [],
              recommendations: data.recommendations || []
            });
            if (data.role_data) {
              setComplianceData(prev => ({
                ...prev, cdlNumber: data.role_data.cdl_number || '', cdlState: data.role_data.cdl_state || '',
                cdlClass: data.role_data.cdl_class || '', cdlExpiry: data.role_data.cdl_expiry || '',
                medicalCardExpiry: data.role_data.medical_card_expiry || '',
                drugTestStatus: data.role_data.drug_test_status || 'pending',
                mvrStatus: data.role_data.mvr_status || 'pending',
                clearinghouseStatus: data.role_data.clearinghouse_status || 'pending'
              }));
            }
          }
          const tasksRes = await fetch(`${API_URL}/compliance/tasks`, {
            headers: { 'Authorization': `Bearer ${token}` }
          });
          if (tasksRes.ok) setComplianceTasks(await tasksRes.json());
        } catch (e) { console.error('Error:', e); }
        finally { setLoading(false); }
      };
      fetchData();
    }, [currentUser]);

    const runAIAnalysis = async () => {
      if (!currentUser) return;
      setAnalyzingAI(true);
      try {
        const token = await currentUser.getIdToken();
        const res = await fetch(`${API_URL}/compliance/ai-analyze`, {
          method: 'POST', headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) setAiAnalysis(await res.json());
      } catch (e) { console.error('AI error:', e); }
      finally { setAnalyzingAI(false); }
    };

    const getScoreColor = (score) => score >= 80 ? '#10b981' : score >= 50 ? '#f59e0b' : '#ef4444';

    if (loading) return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '300px' }}>
        <i className="fas fa-spinner fa-spin" style={{ fontSize: '2rem', color: '#3b82f6' }}></i>
        <span style={{ marginLeft: '10px' }}>Loading compliance data...</span>
      </div>
    );

    return (
      <div style={{ padding: '20px' }}>
        <header style={{ marginBottom: '20px' }}>
          <h2 style={{ margin: 0 }}>Compliance & Safety</h2>
          <p style={{ color: '#6b7280', margin: '8px 0' }}>Monitor your compliance status and required documents</p>
        </header>

        {/* Score Card */}
        <div className="card" style={{ padding: '20px', marginBottom: '20px', background: 'linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%)', color: 'white' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h3 style={{ margin: 0, color: 'white' }}>AI Compliance Score</h3>
              <p style={{ margin: '8px 0 0', opacity: 0.8 }}>Based on documents, verification, and completeness</p>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '48px', fontWeight: 'bold', color: getScoreColor(complianceStatus.score) }}>
                {complianceStatus.score}%
              </div>
              <div style={{ fontSize: '14px', opacity: 0.8 }}>{complianceStatus.status_color} Status</div>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', marginTop: '20px' }}>
            {Object.entries(complianceStatus.breakdown).map(([key, val]) => (
              <div key={key} style={{ background: 'rgba(255,255,255,0.1)', padding: '12px', borderRadius: '8px', textAlign: 'center' }}>
                <div style={{ fontSize: '12px', opacity: 0.8, textTransform: 'capitalize' }}>{key.replace('_', ' ')}</div>
                <div style={{ fontSize: '20px', fontWeight: '600' }}>{val}%</div>
              </div>
            ))}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '20px' }}>
          {/* Left Column */}
          <div>
            {/* CDL & Credentials */}
            <div className="card" style={{ padding: '20px', marginBottom: '20px' }}>
              <h4 style={{ margin: '0 0 16px' }}><i className="fas fa-id-card" style={{ marginRight: '8px' }}></i>CDL & Credentials</h4>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px' }}>
                <div><strong>CDL Number:</strong> {complianceData.cdlNumber || 'Not provided'}</div>
                <div><strong>CDL State:</strong> {complianceData.cdlState || 'Not provided'}</div>
                <div><strong>CDL Class:</strong> {complianceData.cdlClass || 'Not provided'}</div>
                <div><strong>CDL Expiry:</strong> {complianceData.cdlExpiry || 'Not provided'}</div>
                <div><strong>Medical Card Expiry:</strong> {complianceData.medicalCardExpiry || 'Not provided'}</div>
              </div>
            </div>

            {/* Compliance Checks */}
            <div className="card" style={{ padding: '20px', marginBottom: '20px' }}>
              <h4 style={{ margin: '0 0 16px' }}><i className="fas fa-clipboard-check" style={{ marginRight: '8px' }}></i>Compliance Checks</h4>
              <div style={{ display: 'grid', gap: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '12px', background: '#f8fafc', borderRadius: '8px' }}>
                  <span>Drug Test</span>
                  <span className={`int-status-badge ${complianceData.drugTestStatus === 'passed' ? 'active' : 'pending'}`}>
                    {complianceData.drugTestStatus}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '12px', background: '#f8fafc', borderRadius: '8px' }}>
                  <span>MVR Check</span>
                  <span className={`int-status-badge ${complianceData.mvrStatus === 'passed' ? 'active' : 'pending'}`}>
                    {complianceData.mvrStatus}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '12px', background: '#f8fafc', borderRadius: '8px' }}>
                  <span>FMCSA Clearinghouse</span>
                  <span className={`int-status-badge ${complianceData.clearinghouseStatus === 'passed' ? 'active' : 'pending'}`}>
                    {complianceData.clearinghouseStatus}
                  </span>
                </div>
              </div>
            </div>

            {/* Documents */}
            <div className="card" style={{ padding: '20px' }}>
              <h4 style={{ margin: '0 0 16px' }}><i className="fas fa-file-alt" style={{ marginRight: '8px' }}></i>Uploaded Documents</h4>
              {complianceStatus.documents && complianceStatus.documents.length > 0 ? (
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead><tr style={{ borderBottom: '1px solid #e5e7eb' }}>
                    <th style={{ textAlign: 'left', padding: '8px' }}>Document</th>
                    <th style={{ textAlign: 'left', padding: '8px' }}>Type</th>
                    <th style={{ textAlign: 'left', padding: '8px' }}>Expiry</th>
                    <th style={{ textAlign: 'left', padding: '8px' }}>Status</th>
                    <th style={{ textAlign: 'left', padding: '8px' }}>Uploaded</th>
                  </tr></thead>
                  <tbody>
                    {complianceStatus.documents.map((doc, idx) => (
                      <tr key={idx} style={{ borderBottom: '1px solid #f3f4f6' }}>
                        <td style={{ padding: '8px' }}>{doc.file_name || doc.filename || 'Document'}</td>
                        <td style={{ padding: '8px', fontSize: '12px' }}>{(doc.document_type || doc.type || 'OTHER').replace(/_/g, ' ').toUpperCase()}</td>
                        <td style={{ padding: '8px', fontSize: '12px', color: '#6b7280' }}>
                          {doc.expiry_date ? new Date(doc.expiry_date).toLocaleDateString() : 'N/A'}
                        </td>
                        <td style={{ padding: '8px' }}>
                          <span className={`int-status-badge ${doc.status === 'Valid' ? 'active' : doc.status === 'Expired' ? 'inactive' : 'pending'}`}>
                            {doc.status || 'Unknown'}
                          </span>
                        </td>
                        <td style={{ padding: '8px', color: '#6b7280', fontSize: '12px' }}>
                          {doc.uploaded_at ? new Date(doc.uploaded_at * 1000).toLocaleDateString('en-US', { 
                            month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit'
                          }) : 'N/A'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : <p style={{ color: '#6b7280' }}>No documents uploaded yet</p>}
            </div>
          </div>

          {/* Right Column - AI Assistant */}
          <div>
            <div className="card" style={{ padding: '20px' }}>
              <h4 style={{ margin: '0 0 16px' }}><i className="fas fa-robot" style={{ marginRight: '8px' }}></i>AI Compliance Assistant</h4>
              <button onClick={runAIAnalysis} disabled={analyzingAI} className="btn small-cd" style={{ width: '100%', marginBottom: '16px' }}>
                {analyzingAI ? 'Analyzing...' : 'Run AI Analysis'}
              </button>
              {aiAnalysis && (
                <div style={{ padding: '12px', background: '#f0fdf4', borderRadius: '8px', marginBottom: '16px' }}>
                  <strong>Risk Level:</strong> {aiAnalysis.analysis?.risk_level || 'Unknown'}
                  <p style={{ margin: '8px 0 0', fontSize: '14px' }}>{aiAnalysis.analysis?.summary || ''}</p>
                </div>
              )}
              <h5 style={{ margin: '16px 0 8px' }}>Tasks</h5>
              {complianceTasks.length > 0 ? complianceTasks.slice(0, 5).map((task, idx) => (
                <div key={idx} style={{ padding: '8px', background: '#f8fafc', borderRadius: '6px', marginBottom: '8px', fontSize: '14px' }}>
                  <strong>{task.title}</strong>
                  <div style={{ color: '#6b7280', fontSize: '12px' }}>{task.description}</div>
                </div>
              )) : <p style={{ color: '#6b7280', fontSize: '14px' }}>No pending tasks</p>}
            </div>
          </div>
        </div>
      </div>
    );
  }

  function ContentView({ activeNav }) {
    switch (activeNav) {
      case 'home':
        return isPostHire ? <PostHireView /> : <HomeView />;
      case 'docs':
        return <DocumentVault isPostHire={isPostHire} setIsPostHire={setIsPostHire} />;
      case 'marketplace':
        return <Marketplace isPostHire={isPostHire} setIsPostHire={setIsPostHire} />;
      case 'carrier':
        return <MyCarrier />;
      case 'compliance':
        return <DriverComplianceView />;
      case 'hiring':
        return <HiringOnboarding />;
      case 'esign':
        return <ConsentESignature />;
      case 'settings':
        return <AccountSettings />;
      case 'help':
        return <AiHub />;
      default:
        return (
          <div>
            <header className="fp-header">
              <div className="fp-header-titles">
                <h2>{navGroups.flatMap(g => g.items).find(i => i.key === activeNav)?.label || 'View'}</h2>
                <p className="fp-subtitle">This is the {activeNav} view. Only the inner area changes.</p>
              </div>
            </header>
            <section className="fp-grid">
              <div className="card">
                <div className="card-header"><h3>Placeholder</h3></div>
              </div>
            </section>
          </div>
        );
    }
  }

  return (
    <div className={`fp-dashboard-root ${isDarkMode ? 'dark-root' : ''}`}>
      <div className="fp-topbar">
        <div className="topbar-row topbar-row-1">
          <div className="topbar-left">
            <button className="hamburger" aria-label="Open sidebar" onClick={() => setIsSidebarOpen(true)}>
              <i className="fa-solid fa-bars" />
            </button>
            <div className="brand-block">
              <div className="brand-row">
                <div className="logo">
                  <div className="logo">
                                    {/* Desktop / large-screen logo */}
                                    <img src={logo} alt="FreightPower" className="landing-logo-image desktop-logo" />
                                    {/* Responsive compact logo shown at <=768px */}
                                    <img src={resp_logo} alt="FreightPower" className="landing-logo-image mobile-logo" />
                                  </div>
                </div>
                      <div className="user-profile dd-user-profile">
                        <img src="https://randomuser.me/api/portraits/men/75.jpg" alt="Marcus Johnson" className="avatar-img user-avatar-desktop dd-avatar-img"/>
                        <div className="user-info user-info-desktop dd-user-info">
                          <div className="user-name">Marcus Johnson</div>
                          <div className="user-role dd-user-role">Pre-Hire Driver</div>
                        </div>
                      </div>

              </div>
            </div>
          </div>

          <div className="topbar-right actions-right dd-actions-right">
            {isPostHire ? (
              /* Post-hire topbar content */
              <>
                <span className="dd-posthire-status">
                  <span className="dd-status-dot dd-all-docs-active" />
                  <span className="dd-status-text">All Docs Active</span>
                </span>
                <span className="dd-posthire-status">
                  <span className="dd-status-text">Available</span>
                  <label className="dd-toggle-switch">
                    <input type="checkbox" defaultChecked />
                    <span className="dd-toggle-slider"></span>
                  </label>
                </span>
                <span className="dd-posthire-status">
                  <i className="fa-regular fa-clock dd-timer-icon" />
                  <span className="dd-status-text">8h 45m left</span>
                </span>
                <div className="dd-notif-bell">
                  <i className="fa-regular fa-bell notif-icon dd-notif-icon" aria-hidden="true" />
                  <span className="dd-notif-badge">3</span>
                </div>
              </>
            ) : (
              /* Pre-hire topbar content */
              <>
                <span className="dd-missing-doc-chip">
                  <span className="missing-doc-dot dd-missing-doc-dot" />
                  <span className="missing-doc-text dd-missing-doc-text">Missing Docs</span>
                </span>
                <div className="dd-notif-bell">
                  <i className="fa-regular fa-bell notif-icon dd-notif-icon" aria-hidden="true" />
                  <span className="dd-notif-badge">3</span>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      <div className={`fp-content-row ${isSidebarOpen ? 'sidebar-open' : ''}`}>
        <aside className={`fp-sidebar ${isSidebarOpen ? 'open' : ''}`}>
          <div className="sidebar-header">
            <div className="brand-row">
              <div className="logo"><img src={logo} alt="FreightPower" className="landing-logo-image" /></div>
            </div>
            <div className="ids mobile-ids">
              <div className="mobile-id-line"><span className="id-pair"><span className="id-label">Marcus Johnson</span></span></div>
              <div className="mobile-id-line"><span className="id-pair"><span className="id-label">{isPostHire ? 'Active Driver' : 'Pre-Hire Driver'}</span></span></div>
            </div>
            <div className="chips sidebar-chips">
              {isPostHire ? (
                <>
                  <span className="chip green">All Docs Active</span>
                  <span className="chip blue">Available</span>
                  <span className="chip orange">8h 45m left</span>
                </>
              ) : (
                <span className="chip yellow">Missing Docs</span>
              )}
            </div>
          </div>
          <nav className="fp-nav">
            {navGroups.map((group) => (
              <div className="nav-group" key={group.title}>
                <div className="nav-group-title">{group.title}</div>
                <ul>
                  {group.items.map((item) => (
                    <li
                      className={`nav-item ${activeNav === item.key ? 'active' : ''}`}
                      key={item.key}
                      onClick={() => { setActiveNav(item.key); if (isSidebarOpen) setIsSidebarOpen(false); }}
                      role="button"
                      tabIndex={0}
                    >
                      <i className={`${item.icon} icon`} aria-hidden="true"></i>
                      <span className="label">{item.label}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </nav>
          <div className="sidebar-dark-control" aria-hidden="false">
            <span className="dark-label">Dark Mode</span>
            <button
              className="dark-toggle"
              aria-pressed={isDarkMode}
              aria-label="Toggle dark mode"
              onClick={() => setIsDarkMode((s) => !s)}
            >
              <span className="dark-toggle-knob" />
            </button>
          </div>
          <button className="sidebar-close" aria-label="Close sidebar" onClick={() => setIsSidebarOpen(false)}>
            <i className="fa-solid fa-xmark" />
          </button>
        </aside>

        {isSidebarOpen && <div className="overlay" onClick={() => setIsSidebarOpen(false)} />}

        <main className="fp-main">
          <ContentView activeNav={activeNav} />
        </main>
      </div>
    </div>
  );
}
