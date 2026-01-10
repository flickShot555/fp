import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { API_URL } from '../../config';
import TrackingVisibility from './TrackingVisibility';
import DocumentVault from './DocumentVault';
import Finance from './Finance';
import '../../styles/carrier/CarrierDashboard.css';
import '../../styles/shipper/ShipperDashboard.css';
import MyCarriers from './MyCarriers';
import ShipperMarketplace from './ShipperMarketplace';
import ComplianceOverview from './ComplianceOverview';
import AiHub from './AiHub';
import ShipperAnalytics from './Analytics';
import Settings from './Settings';
import AddLoads from '../carrier/AddLoads';
import DraftLoadsModal from './DraftLoadsModal';
import InviteCarrierModal from './InviteCarrierModal';
import CarrierBids from './CarrierBids';
import ShipperMyLoads from './MyLoads';
import '../../styles/shipper/InviteCarrierModal.css';
// OnboardingCoach removed - compliance data now shown in Compliance & Safety page
import logo from '/src/assets/logo.png';
import resp_logo from '/src/assets/logo_1.png';

export default function ShipperDashboard() {
  const { currentUser, logout } = useAuth();
  const navigate = useNavigate();
  const [activeNav, setActiveNav] = useState('home');
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isSidebarDark, setIsSidebarDark] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(false);

  // Onboarding data state
  const [shipperProfile, setShipperProfile] = useState(null);
  const [profileLoading, setProfileLoading] = useState(true);

  // Dashboard stats state
  const [dashboardStats, setDashboardStats] = useState(null);
  const [statsLoading, setStatsLoading] = useState(true);

  // AddLoads modal state
  const [showAddLoads, setShowAddLoads] = useState(false);
  const [editingDraftLoad, setEditingDraftLoad] = useState(null);

  // Draft loads modal state
  const [showDraftLoadsModal, setShowDraftLoadsModal] = useState(false);

  // Invite Carrier modal state
  const [isInviteCarrierOpen, setIsInviteCarrierOpen] = useState(false);

  // File upload ref
  const fileInputRef = React.useRef(null);

  // Handle file upload
  const handleFileUpload = async (e) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setStatsLoading(true);
    
    try {
      const token = await currentUser.getIdToken();
      
      for (const file of files) {
        // Create FormData for file upload
        const formData = new FormData();
        formData.append('file', file);
        
        console.log(`Uploading: ${file.name}...`);
        
        const response = await fetch(`${API_URL}/documents`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`
          },
          body: formData
        });
        
        if (response.ok) {
          const data = await response.json();
          console.log('✅ Upload successful:', data);
          alert(`Document "${file.name}" uploaded successfully!\nType: ${data.doc_type}\nValidation: ${data.validation.status}`);
        } else {
          const error = await response.json();
          console.error('Upload failed:', error);
          alert(`Failed to upload "${file.name}": ${error.detail || 'Unknown error'}`);
        }
      }
      
      // Refresh dashboard stats after all uploads
      await fetchStats();
      
    } catch (err) {
      console.error('Error uploading documents:', err);
      alert('Error uploading documents. Please try again.');
    } finally {
      setStatsLoading(false);
      // Clear the file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  // Fetch dashboard stats
  const fetchStats = async () => {
    if (!currentUser) {
      setStatsLoading(false);
      return;
    }
    try {
      const token = await currentUser.getIdToken();
      const response = await fetch(`${API_URL}/dashboard/stats`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      if (response.ok) {
        const data = await response.json();
        setDashboardStats(data);
      }
    } catch (error) {
      console.error('Error fetching dashboard stats:', error);
    } finally {
      setStatsLoading(false);
    }
  };

  // Handle editing draft loads
  const handleEditDraft = (draftLoad) => {
    setEditingDraftLoad(draftLoad);
    setShowAddLoads(true);
  };

  // Fetch dashboard stats
  useEffect(() => {
    fetchStats();
  }, [currentUser]);

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
          setShipperProfile(data);
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
      title: 'OPERATE',
      items: [
        { key: 'home', label: 'Dashboard', icon: 'fa-solid fa-house' },
        { key: 'my-loads', label: 'My Loads', icon: 'fa-solid fa-truck' },
        { key: 'my-carriers', label: 'My Carriers', icon: 'fa-solid fa-people-group' },
        { key: 'marketplace', label: 'Marketplace', icon: 'fa-solid fa-store' },
        { key: 'carrier-bids', label: 'Carrier Bids', icon: 'fa-solid fa-hand-holding-dollar' },
        { key: 'tracking', label: 'Tracking & Visibility', icon: 'fa-solid fa-location-crosshairs' },
        { key: 'doc-vault', label: 'Document Vault', icon: 'fa-solid fa-folder' },
      ]
    },
    {
      title: 'MANAGE',
      items: [
        { key: 'finance', label: 'Finance', icon: 'fa-solid fa-wallet' },
        { key: 'compliance', label: 'Compliance', icon: 'fa-solid fa-shield-halved' },
        { key: 'analytics', label: 'Analytics', icon: 'fa-solid fa-chart-column' }
      ]
    },
    {
      title: 'SYSTEM',
      items: [
        { key: 'profile', label: 'Profile', icon: 'fa-solid fa-user' },
        { key: 'settings', label: 'Settings', icon: 'fa-solid fa-gear' },
        { key: 'help', label: 'AI Hub', icon: 'fa-regular fa-circle-question' },
        { key: 'logout', label: 'Logout', icon: 'fa-solid fa-right-from-bracket' }
      ]
    }
  ];

  // Handle logout
  const handleLogout = async () => {
    try {
      await logout();
      navigate('/login');
    } catch (error) {
      console.error('Error logging out:', error);
    }
  };

  // Handle navigation click
  const handleNavClick = (key) => {
    if (key === 'logout') {
      handleLogout();
    } else {
      setActiveNav(key);
      if (isSidebarOpen) setIsSidebarOpen(false);
    }
  };

  // --- FILTER DROPDOWNS STATE ---
  const [openDropdown, setOpenDropdown] = useState(null);
  const [selectedRange, setSelectedRange] = useState('Last 30 Days');
  const [selectedRegion, setSelectedRegion] = useState('All Regions');
  const [selectedCarrier, setSelectedCarrier] = useState('All Carriers');
  const [selectedLane, setSelectedLane] = useState('All Lanes');

  const ranges = ['Last 7 Days', 'Last 30 Days', 'Last 90 Days', 'Year to Date'];
  const regions = ['All Regions', 'North', 'South', 'East', 'West', 'Midwest'];
  const carriers = ['All Carriers', 'Swift Transport', 'Reliable Freight', 'Express Logistics'];
  const lanes = ['All Lanes', 'MN → IL', 'TX → AZ', 'FL → GA'];

  // close dropdowns on outside click
  React.useEffect(() => {
    function onDocClick() { setOpenDropdown(null); }
    document.addEventListener('click', onDocClick);
    return () => document.removeEventListener('click', onDocClick);
  }, []);

  function HomeView() {
    return (
      <>
        <header className="fp-header">
          <div className="fp-header-controls">
            <button className="btn small-cd" onClick={() => setShowAddLoads(true)}>+ Create Load</button>
            <button className="btn small ghost-cd" onClick={() => setIsInviteCarrierOpen(true)}>Invite Carrier</button>
            <button className="btn small ghost-cd" onClick={() => fileInputRef.current?.click()}>Upload Document</button>
            <input 
              type="file" 
              ref={fileInputRef} 
              style={{ display: 'none' }} 
              multiple 
              onChange={handleFileUpload}
              accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
            />
            <button className="btn small ghost-cd">Track Shipments</button>
          </div>
        </header>

        {/* Shipper Profile Card - Shows onboarding data */}
        {!profileLoading && shipperProfile && shipperProfile.data && (
          <section style={{ marginBottom: '20px' }}>
            <div className="card" style={{ padding: '20px', background: '#f8fafc' }}>
              <div className="card-header">
                <h3><i className="fa-solid fa-building" style={{ marginRight: '8px' }}></i>Business Profile</h3>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginTop: '16px' }}>
                {shipperProfile.data.businessName && (
                  <div><strong>Business:</strong> {shipperProfile.data.businessName}</div>
                )}
                {shipperProfile.data.businessType && (
                  <div><strong>Type:</strong> {shipperProfile.data.businessType}</div>
                )}
                {shipperProfile.data.contactFullName && (
                  <div><strong>Contact:</strong> {shipperProfile.data.contactFullName}</div>
                )}
                {shipperProfile.data.contactEmail && (
                  <div><strong>Email:</strong> {shipperProfile.data.contactEmail}</div>
                )}
                {shipperProfile.data.freightType && (
                  <div><strong>Freight Type:</strong> {shipperProfile.data.freightType}</div>
                )}
                {shipperProfile.data.regionsOfOperation && (
                  <div><strong>Regions:</strong> {shipperProfile.data.regionsOfOperation}</div>
                )}
              </div>
              {!shipperProfile.onboarding_completed && (
                <div style={{ marginTop: '16px', padding: '12px', background: '#fef3c7', borderRadius: '8px', color: '#92400e' }}>
                  <i className="fa-solid fa-exclamation-triangle" style={{ marginRight: '8px' }}></i>
                  Onboarding not complete. <button onClick={() => setActiveNav('profile')} style={{ background: 'none', border: 'none', color: '#1d4ed8', textDecoration: 'underline', cursor: 'pointer', padding: 0 }}>Complete your profile</button>
                </div>
              )}
            </div>
          </section>
        )}

        {/* Onboarding Coach removed - compliance data now shown in Compliance & Safety page */}

        <section className="top-stats">
          <div className="card sd-small-card">
            <div className="sd-small-card-row">
              <h4>Active Loads</h4>
              <i className="fa-solid fa-truck" aria-hidden="true" />
            </div>
            <div className="big">{statsLoading ? '...' : (dashboardStats?.active_loads || 0)}</div>
            <div className="small-sub-active">+{dashboardStats?.active_loads_today || 0} today</div>
          </div>
          <div className="card sd-small-card">
            <div className="sd-small-card-row">
              <h4>On-Time %</h4>
              <i className="fa-solid fa-clock" aria-hidden="true" />
            </div>
            <div className="big green">{statsLoading ? '...' : `${dashboardStats?.on_time_percentage || 0}%`}</div>
            <div className="small-sub-time">{dashboardStats?.on_time_change || '+0%'}</div>
          </div>
          <div className="card sd-small-card">
            <div className="sd-small-card-row">
              <h4>Carrier Rating</h4>
              <i className="fa-solid fa-star" aria-hidden="true" />
            </div>
            <div className="big">{statsLoading ? '...' : (dashboardStats?.rating || 0)}</div>
            <div className="small-sub-rating">{dashboardStats?.rating_label || 'N/A'}</div>
          </div>

          <div className="card sd-small-card">
            <div className="sd-small-card-row">
              <h4>Total Revenue</h4>
              <i className="fa-solid fa-dollar-sign" aria-hidden="true" />
            </div>
            <div className="big">${statsLoading ? '...' : ((dashboardStats?.total_revenue || 0) / 1000).toFixed(0)}K</div>
            <div className="small-sub-revenue">{dashboardStats?.revenue_change || '+0%'} MTD</div>
          </div>
          <div className="card sd-small-card">
            <div className="sd-small-card-row">
              <h4>Compliance</h4>
              <i className="fa-solid fa-shield-halved" aria-hidden="true" />
            </div>
            <div className="big">{statsLoading ? '...' : `${dashboardStats?.compliance_score || 0}%`}</div>
            <div className="small-sub-compliance">{dashboardStats?.compliance_expiring || 0} expiring</div>
          </div>
          <div className="card sd-small-card" style={{ cursor: 'pointer' }} onClick={() => setShowDraftLoadsModal(true)}>
            <div className="sd-small-card-row">
              <h4>Draft Loads</h4>
              <i className="fa-solid fa-file-lines" aria-hidden="true" />
            </div>
            <div className="big">{statsLoading ? '...' : (dashboardStats?.draft_loads || 0)}</div>
            <div className="small-sub-task">Click to manage</div>
          </div>

          <div className="card sd-small-card shd-ai-summary">
            <h4>AI Summary</h4>
            <div className="big">{statsLoading ? '...' : (dashboardStats?.total_loads || 0)} loads</div>
          </div>
        </section>

        <section className="fp-filters" style={{display:'flex',gap:12,alignItems:'center',marginBottom:18,flexWrap:'wrap'}}>
            <select className="sb-carrier-filter-select" value={selectedRange} onChange={(e) => setSelectedRange(e.target.value)}>
              {ranges.map(r => <option key={r} value={r}>{r}</option>)}
            </select>

            <select className="sb-carrier-filter-select" value={selectedRegion} onChange={(e) => setSelectedRegion(e.target.value)}>
              {regions.map(r => <option key={r} value={r}>{r}</option>)}
            </select>

            <select className="sb-carrier-filter-select" value={selectedCarrier} onChange={(e) => setSelectedCarrier(e.target.value)}>
              {carriers.map(c => <option key={c} value={c}>{c}</option>)}
            </select>

            <select className="sb-carrier-filter-select" value={selectedLane} onChange={(e) => setSelectedLane(e.target.value)}>
              {lanes.map(l => <option key={l} value={l}>{l}</option>)}
            </select>

          <div style={{marginLeft:'auto'}} className="search-wrapper">
            <div className="ssd-search-box">
              <i className="fa-solid fa-magnifying-glass" aria-hidden="true" />
              <input placeholder="Search..." />
            </div>
          </div>
        </section>

        <section className="fp-grid" style={{gridTemplateColumns:'repeat(3,1fr)',gap:18}}>
          <div className="card ai-insights">
            <h3>AI Insights</h3>
            <div className="insight">Top Lane Alert<br/>MN → IL averaging $2.95/mi (+8%)</div>
            <ul className="muted">
              <li>Demand spike in Midwest corridors</li>
              <li>Fuel costs stabilizing</li>
            </ul>
          </div>

          <div className="card active-loads">
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
              <h3>Active Loads</h3>
              <div className="muted">5 of 24</div>
            </div>
            <ul className="active-load-list">
              <li>
                <div className="load-left"><strong>#L2401</strong><div className="muted">Chicago → Atlanta</div></div>
                <div className="load-right"><div className="int-status-badge active">On Time</div><div className="muted small">ETA: 2h 15m</div></div>
              </li>
              <li>
                <div className="load-left"><strong>#L2402</strong><div className="muted">Dallas → Phoenix</div></div>
                <div className="load-right"><div className="int-status-badge warning">Delayed</div><div className="muted small">ETA: +45m</div></div>
              </li>
              <li>
                <div className="load-left"><strong>#L2403</strong><div className="muted">Miami → Jacksonville</div></div>
                <div className="load-right"><div className="int-status-badge active">Delivered</div><div className="muted small">30m ago</div></div>
              </li>
            </ul>
          </div>

          <div className="card top-carriers">
            <h3>Top Carriers</h3>
            <ol className="top-carriers">
              <li>
                <div className="carrier-left">
                  <div className="name">Swift Transport</div>
                  <div className="sub muted small">98.5% On-Time</div>
                </div>
                <div className="carrier-right">
                  <span className="rating">4.9★</span>
                  <div className="muted small">42 loads</div>
                </div>
              </li>
              <li>
                <div className="carrier-left">
                  <div className="name">Reliable Freight</div>
                  <div className="sub muted small">96.8% On-Time</div>
                </div>
                <div className="carrier-right">
                  <span className="rating blue">4.8★</span>
                  <div className="muted small">38 loads</div>
                </div>
              </li>
              <li>
                <div className="carrier-left">
                  <div className="name">Express Logistics</div>
                  <div className="sub muted small">95.2% On-Time</div>
                </div>
                <div className="carrier-right">
                  <span className="rating orange">4.7★</span>
                  <div className="muted small">29 loads</div>
                </div>
              </li>
            </ol>
          </div>

          <div className="card performance-card">
            <h3>Performance Health</h3>
            <div className="performance-metrics">
              <div className="metric">
                <strong className="green">Financial</strong>
                <div className="muted">92%</div>
              </div>
              <div className="metric">
                <strong className="blue">Operational</strong>
                <div className="muted">96%</div>
              </div>
            </div>
          </div>

          <div className="card compliance-card">
            <h3>Compliance Status</h3>
            <div className="sd-exp-item pill">
              <div className="exp-title">Insurance Expiring</div>
              <div className="exp-sub muted">Swift Transport - 3 days</div>
            </div>
            <div className="sd-exp-item pill">
              <div className="exp-title">DOT Audit Due</div>
              <div className="exp-sub muted">Reliable Freight - 7 days</div>
            </div>
          </div>
        </section>
      </>
    );
  }

  function ContentView({ activeNav }) {
    if (activeNav === 'home') return <HomeView />;
    if (activeNav === 'my-loads') return <ShipperMyLoads />;
    if (activeNav === 'my-carriers') return <MyCarriers />;
    if (activeNav === 'marketplace') return <ShipperMarketplace />;
    if (activeNav === 'carrier-bids') return <CarrierBids />;
    if (activeNav === 'tracking') return <TrackingVisibility />;
    if (activeNav === 'doc-vault') return <DocumentVault />;
    if (activeNav === 'finance') return <Finance />;
    if (activeNav === 'compliance') return <ComplianceOverview />;
    if (activeNav === 'settings') return <Settings />;
    if (activeNav === 'help') return <AiHub />;
    if (activeNav === 'analytics') return <ShipperAnalytics />;
    if (activeNav === 'profile') return (
      <div>
        <header className="fp-header">
          <div className="fp-header-titles">
            <h2>Profile</h2>
            <p className="fp-subtitle">Complete your business profile and onboarding information.</p>
          </div>
        </header>
        <section className="fp-grid">
          <div className="card">
            <div className="card-header"><h3>Profile Component</h3></div>
            <div style={{ padding: 20 }}>
              <p>Profile component will be added here. This is where users can complete their onboarding details.</p>
            </div>
          </div>
        </section>
      </div>
    );
    return (
      <div>
        <header className="fp-header">
          <div className="fp-header-titles">
            <h2>{navGroups.flatMap(g => g.items).find(i => i.key === activeNav)?.label || 'View'}</h2>
            <p className="fp-subtitle">This is the {activeNav} view.</p>
          </div>
        </header>
        <section className="fp-grid">
          <div className="card">
            <div className="card-header"><h3>Placeholder</h3></div>
            <div style={{ padding: 20 }}>Content for <strong>{activeNav}</strong> goes here.</div>
          </div>
        </section>
      </div>
    );
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
                  {/* Desktop / large-screen logo */}
                  <img src={logo} alt="FreightPower" className="landing-logo-image desktop-logo" />
                  {/* Responsive compact logo shown at <=768px */}
                  <img src={resp_logo} alt="FreightPower" className="landing-logo-image mobile-logo" />
                  </div>
                  {/* Company name placed to the right of the logo (shipper-only) */}
                  <div className="brand-info">
                    <div className="company-name">Atlas Logistics LLC</div>
                    {/* Shipper-only status chips placed below the company name (column) */}
                    <div className="shipper-status">
                      <span className="int-status-badge active"><i className="fa-solid fa-check"/> Active & Operating</span>
                      <span className="int-status-badge blue"><i className="fa-solid fa-network-wired"/> TMS Connected</span>
                    </div>
                  </div>
                </div>
            </div>
          </div>

          <div className="topbar-right actions-right">
            <div className="icons">
              <div className="notif">
                <i className="fa-regular fa-bell notif-icon" aria-hidden="true" />
                <span className="notif-badge">3</span>
              </div>
              <i className="fa-solid fa-robot bot-icon" aria-hidden="true" />
              <img src="https://randomuser.me/api/portraits/women/65.jpg" alt="avatar" className="avatar-img"/>
            </div>
          </div>
        </div>
      </div>

      <div className={`fp-content-row ${isSidebarOpen ? 'sidebar-open' : ''}`}>
        <aside className={`fp-sidebar ${isSidebarOpen ? 'open' : ''} ${isSidebarDark ? 'dark' : ''}`}>
          <div className="sidebar-header">
            <div className="brand-row">
              <div className="logo"><img src={logo} alt="FreightPower" className="landing-logo-image" /></div>
            </div>
            <div className="chips sidebar-chips">
              <div className="company-name">Atlas Logistics LLC</div>
              <span className="int-status-badge active">Active & Operating</span>
              <span className="int-status-badge blue">TMS Connected</span>
            </div>
          </div>

          <nav className="fp-nav">
            {navGroups.map((group) => (
              <div className="nav-group" key={group.title}>
                <div className="nav-group-title">{group.title}</div>
                <ul>
                  {group.items.map((it) => (
                    <li
                      className={`nav-item ${activeNav === it.key ? 'active' : ''}`}
                      key={it.key}
                      onClick={() => handleNavClick(it.key)}
                      role="button"
                      tabIndex={0}
                    >
                      <i className={`${it.icon} icon`} aria-hidden="true"></i>
                      <span className="label">{it.label}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </nav>

          <div className="sidebar-dark-control">
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

      {/* AddLoads Modal */}
      {showAddLoads && (
        <AddLoads 
          onClose={() => {
            setShowAddLoads(false);
            setEditingDraftLoad(null);
          }} 
          isShipper={true}
          draftLoad={editingDraftLoad}
        />
      )}

      {/* Draft Loads Modal */}
      {showDraftLoadsModal && (
        <DraftLoadsModal
          onClose={() => setShowDraftLoadsModal(false)}
          onEditDraft={handleEditDraft}
        />
      )}

      {/* Invite Carrier Modal */}
      <InviteCarrierModal 
        isOpen={isInviteCarrierOpen} 
        onClose={() => setIsInviteCarrierOpen(false)} 
      />

      {/* Hidden File Input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
        style={{ display: 'none' }}
        onChange={handleFileUpload}
      />
    </div>
  );
}
