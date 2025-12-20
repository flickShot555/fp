import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { API_URL } from '../../config';
import '../../styles/carrier/CarrierDashboard.css';
import peopleIcon from '../../assets/ai_driver.svg';
import MyLoads from './MyLoads';
import DocumentVault from './DocumentVault';
import ShipperPartners from './ShipperPartners';
import Marketplace from './Marketplace';
import DriversAndDispatches from './DriversAndDispatches';
import FactoringInvoicing from './FactoringInvoicing';
import Integrations from './Integrations';
import ComplianceSafety from './ComplianceSafety';
import ConsentESignature from './ConsentESignature';
import Messaging from './Messaging';
import AlertsNotifications from './AlertsNotifications';
import Analytics from './Analytics';
import Calendar from './Calendar';
import Settings from './Settings';
import HelpHub from './HelpHub';
// OnboardingCoach removed - compliance data now shown in Compliance & Safety page
import logo from '/src/assets/logo.png';
import resp_logo from '/src/assets/logo_1.png';
// Note: Font Awesome icons are used instead of custom SVGs for simplicity
// icon images replaced by Font Awesome icons

export default function CarrierDashboard() {
  const { currentUser } = useAuth();
  // Placeholder data to match the design in the attached mock
  const activeLoads = { inProgress: 8, delivered: 24, completed: 156 };
  const driversCompliance = { active: 12, expiring: 4, alerts: 1 };
  const earnings = { week: '$24,580', month: '$98,450', factoring: '$15,200' };
  const [activeNav, setActiveNav] = useState('home');
  const [activeMarketplaceSection, setActiveMarketplaceSection] = useState('loads');
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isSidebarDark, setIsSidebarDark] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(false);

  // Onboarding data state
  const [companyProfile, setCompanyProfile] = useState(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [complianceScore, setComplianceScore] = useState(null);
  const [dotNumber, setDotNumber] = useState('');
  const [mcNumber, setMcNumber] = useState('');

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
          setCompanyProfile(data);
          if (typeof data.onboarding_score !== 'undefined') {
            setComplianceScore(data.onboarding_score);
          }
        }

        // also fetch compliance status to show current compliance score
        const complianceRes = await fetch(`${API_URL}/compliance/status`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (complianceRes.ok) {
          const cData = await complianceRes.json();
          if (typeof cData.compliance_score !== 'undefined') {
            setComplianceScore(cData.compliance_score);
          }
          // Set DOT and MC numbers from the extracted document values
          if (cData.dot_number) {
            setDotNumber(cData.dot_number);
          }
          if (cData.mc_number) {
            setMcNumber(cData.mc_number);
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
        { key: 'home', label: 'Home', icon: 'fa-solid fa-house' },
        { key: 'my-loads', label: 'My Loads', icon: 'fa-solid fa-truck' },
        { key: 'docs', label: 'Document Vault', icon: 'fa-solid fa-folder' },
        { key: 'shippers', label: 'My Shippers/Brokers', icon: 'fa-solid fa-people-group' },
        { key: 'marketplace', label: 'Marketplace', icon: 'fa-solid fa-store' },
        { key: 'drivers', label: 'Drivers & Dispatches', icon: 'fa-solid fa-route' },
      ]
    },
    {
      title: 'FINANCE',
      items: [
        { key: 'factoring', label: 'Factoring & Invoicing', icon: 'fa-solid fa-dollar-sign' },
        { key: 'integrations', label: 'Integrations', icon: 'fa-solid fa-plug' }
      ]
    },
    {
      title: 'MANAGEMENT',
      items: [
        { key: 'compliance', label: 'Compliance & Safety', icon: 'fa-solid fa-shield-halved' },
        { key: 'esign', label: 'Consent & eSignature', icon: 'fa-solid fa-pen-fancy' }
      ]
    },
    {
      title: 'COLLABORATION',
      items: [
        { key: 'messaging', label: 'Messaging', icon: 'fa-solid fa-envelope' },
        { key: 'alerts', label: 'Alerts & Notifications', icon: 'fa-solid fa-bell' }
      ]
    },
    {
      title: 'INSIGHTS',
      items: [
        { key: 'analytics', label: 'Analytics & Reports', icon: 'fa-solid fa-chart-column' },
        { key: 'calendar', label: 'Calendar', icon: 'fa-solid fa-calendar-days' }
      ]
    },
    {
      title: 'SYSTEM',
      items: [
        { key: 'settings', label: 'Settings', icon: 'fa-solid fa-gear' },
        { key: 'help', label: 'Help Hub', icon: 'fa-regular fa-circle-question' }
      ]
    }
  ];

  // Small router for the inner content area so the sidebar & topbar remain mounted
  function HomeView() {
    return (
      <>
        <header className="fp-header">
          <div className="fp-header-titles">
            <h2>Dashboard</h2>
            <p className="fp-subtitle">Welcome back! Here's what's happening with your fleet today.</p>
          </div>
        </header>

        {/* Company Profile Card - Shows onboarding data */}
        {!profileLoading && companyProfile && companyProfile.data && (
          <section style={{ marginBottom: '20px' }}>
            <div className="card" style={{ padding: '20px', background: '#f8fafc' }}>
              <div className="card-header">
                <h3><i className="fa-solid fa-building" style={{ marginRight: '8px' }}></i>Company Profile</h3>
                {complianceScore !== null && (
                  <div className="pill" style={{ background:'#e0f2fe', color:'#075985', padding:'6px 10px', borderRadius:'999px', fontWeight:600 }}>
                    Compliance Score: {Math.round(complianceScore)}%
                  </div>
                )}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginTop: '16px' }}>
                {companyProfile.data.companyName && (
                  <div><strong>Company:</strong> {companyProfile.data.companyName}</div>
                )}
                {companyProfile.data.dotNumber && (
                  <div><strong>DOT Number:</strong> {companyProfile.data.dotNumber}</div>
                )}
                {companyProfile.data.mcNumber && (
                  <div><strong>MC Number:</strong> {companyProfile.data.mcNumber}</div>
                )}
                {companyProfile.data.contactEmail && (
                  <div><strong>Contact:</strong> {companyProfile.data.contactEmail}</div>
                )}
                {companyProfile.data.fleetSize && (
                  <div><strong>Fleet Size:</strong> {companyProfile.data.fleetSize} units</div>
                )}
                {companyProfile.data.homeTerminal && (
                  <div><strong>Home Terminal:</strong> {companyProfile.data.homeTerminal}</div>
                )}
              </div>
              {!companyProfile.onboarding_completed && (
                <div style={{ marginTop: '16px', padding: '12px', background: '#fef3c7', borderRadius: '8px', color: '#92400e' }}>
                  <i className="fa-solid fa-exclamation-triangle" style={{ marginRight: '8px' }}></i>
                  Onboarding not complete. <a href="/carrier-onboarding" style={{ color: '#1d4ed8', textDecoration: 'underline' }}>Complete now</a>
                </div>
              )}
            </div>
          </section>
        )}

        {/* Onboarding Coach removed - compliance data now shown in Compliance & Safety page */}

        <section className="fp-grid">
          <div className="card stats-card">
            <div className="card-header">
              <h3>Active Loads</h3>
              <i className="fa-solid fa-truck cd-card-icon small" aria-hidden="true" />
            </div>
            <div className="stats">
              <div>In Progress <span>{activeLoads.inProgress}</span></div>
              <div>Delivered <span>{activeLoads.delivered}</span></div>
              <div>Completed <span>{activeLoads.completed}</span></div>
            </div>
          </div>

          <div className="card compliance-card">
            <div className="card-header">
              <h3>Drivers Compliance</h3>
              <i className="fa-solid fa-people-group cd-card-icon small" aria-hidden="true" />
            </div>
            <div className="stats">
              <div>Active Drivers <span>{driversCompliance.active}</span></div>
              <div>Expiring Licenses <span>{driversCompliance.expiring}</span></div>
              <div>Safety Alerts <span>{driversCompliance.alerts}</span></div>
            </div>
          </div>

          <div className="card small-card expiring-card">
            <div className="card-header">
              <h3>Expiring Documents</h3>
              <i className="fa-solid fa-triangle-exclamation cd-card-icon small" aria-hidden="true" />
            </div>
            <div className="expiring-list">
              <div className="exp-item pill yellow">
                <span className="exp-title">Insurance</span>
                <span className="exp-days yellow">12 days</span>
              </div>

              <div className="exp-item pill pink">
                <span className="exp-title">Authority</span>
                <span className="exp-days pink">3 days</span>
              </div>
            </div>
          </div>

          <div className="card suggestions-card">
            <div className="card-header">
              <h3>AI Suggestions</h3>
              <i className="fa-solid fa-robot cd-card-icon small" aria-hidden="true" />
            </div>
            <ul>
              <li>Renew insurance in 12 days to avoid compliance issues</li>
              <li>3 high-paying loads available in your area</li>
            </ul>
          </div>

          <div className="card earnings-card">
            <div className="card-header">
              <h3>Earnings Overview</h3>
              <i className="fa-solid fa-dollar-sign cd-card-icon small" aria-hidden="true" />
            </div>
            <div className="stats earnings-stats">
              <div>This Week <span className="green">{earnings.week}</span></div>
              <div>This Month <span className="green">{earnings.month}</span></div>
              <div>Factoring Funded <span className="blue">{earnings.factoring}</span></div>
            </div>
          </div>

          <div className="card small-card integrations-card">
            <div className="card-header">
              <h3>Integrations Health</h3>
              <i className="fa-solid fa-plug cd-card-icon small" aria-hidden="true" />
            </div>
            <ul className="integrations-list">
              <li>QuickBooks <span className="dot green"/></li>
              <li>ELD System <span className="dot green"/></li>
              <li>Bank Connection <span className="dot orange"/></li>
              <li>Factoring <span className="dot green"/></li>
            </ul>
          </div>

          <div className="card recent-messages span-3">
            <div className="card-row">
              <h3>Recent Messages</h3>
              <a className="view-all" onClick={() => setActiveNav('messaging')} style={{ cursor: 'pointer' }}>View All</a>
            </div>
            <ul className="recent-list">
              <li className="msg-item">
                <img className="msg-avatar" src="https://randomuser.me/api/portraits/women/65.jpg" alt="sarah" />
                <div className="msg-body">
                  <div className="msg-head"><strong>Sarah Johnson</strong> <span className="role">- TQL Logistics</span></div>
                  <div className="muted">Load confirmation for Chicago pickup</div>
                </div>
                <div className="msg-time">2m ago</div>
              </li>

              <li className="msg-item">
                <img className="msg-avatar" src="https://randomuser.me/api/portraits/men/32.jpg" alt="mike" />
                <div className="msg-body">
                  <div className="msg-head"><strong>Mike Rodriguez</strong> <span className="role">- Driver</span></div>
                  <div className="muted">Delivered load #1234, BOL attached</div>
                </div>
                <div className="msg-time">1h ago</div>
              </li>

              <li className="msg-item">
                <img className="msg-avatar" src="https://randomuser.me/api/portraits/men/36.jpg" alt="james" />
                <div className="msg-body">
                  <div className="msg-head"><strong>James Wilson</strong> <span className="role">- Dispatcher</span></div>
                  <div className="muted">Route optimization completed for tomorrow</div>
                </div>
                <div className="msg-time">3h ago</div>
              </li>
            </ul>
          </div>

          <div className="card marketplace-snapshot span-3">
            <div className="card-row">
              <h3>Marketplace Snapshot</h3>
              <button 
                className="btn ghost-cd small"
                onClick={() => { setActiveMarketplaceSection('loads'); setActiveNav('marketplace'); }}
                aria-label="View all marketplace listings"
              >
                View All Marketplace
              </button>
            </div>
            <div className="market-grid">
              <div className="market-col loads">
                <h4 className="col-title">Available Loads</h4>
                <div className="load-item">
                  <div className="load-left">
                    <div className="load-route">Chicago, IL 00212 Dallas, TX</div>
                    <div className="load-sub muted">TQL Logistics</div>
                  </div>
                  <div className="load-right">
                    <div className="price green">$2,450</div>
                    <div className="pickup muted">Pickup: Tomorrow</div>
                  </div>
                </div>

                <div className="load-item">
                  <div className="load-left">
                    <div className="load-route">Atlanta, GA 00212 Miami, FL</div>
                    <div className="load-sub muted">Landstar</div>
                  </div>
                  <div className="load-right">
                    <div className="price green">$1,850</div>
                    <div className="pickup muted">Pickup: Today</div>
                  </div>
                </div>
              </div>

              <div className="market-col drivers">
                <h4 className="col-title">Available Drivers</h4>
                <div className="driver-count">5</div>
                <div className="driver-sub muted">Drivers ready for hire</div>
                <button className="btn small green-btn" onClick={() => { setActiveMarketplaceSection('drivers'); setActiveNav('marketplace'); }}>View Candidates</button>
              </div>

              <div className="market-col offers">
                <h4 className="col-title">Service Offers</h4>
                <div className="offer-item">
                  <div className="offer-left">Fuel Discount<div className="muted">Save on fuel at 500+ locations</div></div>
                  <div className="offer-right"><span className="int-status-badge active">15% OFF</span></div>
                </div>
                <div className="offer-item">
                  <div className="offer-left">Factoring Rate<div className="muted">Special rate for new clients</div></div>
                  <div className="offer-right"><span className="int-status-badge active">1.5%</span></div>
                </div>
              </div>
            </div>
          </div>

          <div className="card notifications-card span-3">
            <div className="card-row">
              <h3>Latest Notifications</h3>
              <a className="view-all" onClick={() => setActiveNav('alerts')} style={{ cursor: 'pointer' }}>View All</a>
            </div>
            <ul className="notifications-list">
              <li className="notification-item">
                <div className="note-left"><span className="dot red"/></div>
                <div className="note-body">
                  <div className="note-title">Insurance renewal required</div>
                  <div className="note-sub muted">Your insurance expires in 12 days</div>
                </div>
                <div className="note-time">1h ago</div>
              </li>

              <li className="notification-item">
                <div className="note-left"><span className="dot orange"/></div>
                <div className="note-body">
                  <div className="note-title">Load update</div>
                  <div className="note-sub muted">Load #1234 pickup time changed to 2:00 PM</div>
                </div>
                <div className="note-time">2h ago</div>
              </li>

              <li className="notification-item">
                <div className="note-left"><span className="dot green"/></div>
                <div className="note-body">
                  <div className="note-title">Payment received</div>
                  <div className="note-sub muted">$2,450 payment processed for load #1230</div>
                </div>
                <div className="note-time">3h ago</div>
              </li>
            </ul>
          </div>
        </section>
      </>
    );
  }

  function ContentView({ activeNav }) {
    // For now, only 'home' renders the full dashboard; other routes show placeholders.
    switch (activeNav) {
      case 'home':
        return <HomeView />;
      case 'my-loads':
        return <MyLoads />;
      case 'docs':
        return <DocumentVault />;
      case 'shippers':
        return <ShipperPartners />;
      case 'marketplace':
        return <Marketplace activeSection={activeMarketplaceSection} setActiveSection={setActiveMarketplaceSection} />;
      case 'drivers':
        return <DriversAndDispatches />;
      case 'factoring':
        return <FactoringInvoicing />;
      case 'integrations':
        return <Integrations />;
      case 'compliance':
        return <ComplianceSafety />;
      case 'esign':
        return <ConsentESignature />;
      case 'messaging':
        return <Messaging />;
      case 'alerts':
        return <AlertsNotifications />;
      case 'analytics':
        return <Analytics />;
      case 'calendar':
        return <Calendar />;
      case 'settings':
        return <Settings />;
      case 'help':
        return <HelpHub />;
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
                <div style={{ padding: 20 }}>
                  <p>Content for <strong>{activeNav}</strong> goes here. Replace this with real components as needed.</p>
                </div>
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
                  {/* Desktop / large-screen logo */}
                  <img src={logo} alt="FreightPower" className="landing-logo-image desktop-logo" />
                  {/* Responsive compact logo shown at <=768px */}
                  <img src={resp_logo} alt="FreightPower" className="landing-logo-image mobile-logo" />
                </div>
                {/* verified moved into sidebar header; topbar inline chips removed */}
                <div className="ids">
                  <span className="id-pair"><span className="id-label">DOT:</span> <span className="id-value">{dotNumber || 'N/A'}</span></span>
                  <span className="ids-sep">•</span>
                  <span className="id-pair"><span className="id-label">MC:</span> <span className="id-value">{mcNumber || 'N/A'}</span></span>
                </div>
              </div>
            </div>
          </div>

          <div className="topbar-right actions-right">
            <div className="actions">
              <button className="btn small-cd"><i className="fa-solid fa-link"/> Connect</button>
              <button className="btn ghost-cd small"><i className="fa-solid fa-triangle-exclamation"/> Report Fraud</button>
              <button className="btn ghost-cd small"><i className="fa-solid fa-pen"/> Suggest Edit</button>
            </div>
            {/* mobile-only icons in the first row: visible on small screens */}
            <div className="icons-mobile">
              <div
                className="notif"
                role="button"
                aria-label="Open Alerts & Notifications"
                onClick={() => { setActiveNav('alerts'); setIsSidebarOpen(false); }}
              >
                <i className="fa-regular fa-bell notif-icon" aria-hidden="true" />
                <span className="notif-badge">3</span>
              </div>
              <i
                className="fa-solid fa-robot bot-icon"
                aria-hidden="true"
                role="button"
                aria-label="Open Help Hub"
                onClick={() => { setActiveNav('help'); setIsSidebarOpen(false); }}
              />
              <img
                src="https://randomuser.me/api/portraits/men/75.jpg"
                alt="avatar"
                className="avatar-img"
                role="button"
                aria-label="Open Settings"
                onClick={() => { setActiveNav('settings'); setIsSidebarOpen(false); }}
              />
            </div>
          </div>
        </div>

        <div className="topbar-row topbar-row-2">
          <div className="topbar-left second-left">
            <div className="chips">
              <span className="chip-cd success">DOT Active</span>
              <span className="chip-cd info">Operating</span>
              <span className="chip-cd yellow">Safety: Satisfactory</span>
              <span className="chip-cd blue">ELD: Samsara</span>
            </div>
            <div className="fleet-stats">
              <span className="fleet-item"><i className="fa-solid fa-truck"/> <strong>12</strong> Power Units</span>
              <span className="fleet-item"><i className="fa-solid fa-snowflake"/> <strong>8</strong> Reefers</span>
              <span className="fleet-item"><i className="fa-solid fa-box"/> <strong>15</strong> Dry Vans</span>
            </div>
          </div>

          <div className="topbar-right">
            <div className="icons">
              <span className="lang"><i className="fa-solid fa-globe"/> EN</span>
              <div
                className="notif"
                role="button"
                aria-label="Open Alerts & Notifications"
                onClick={() => { setActiveNav('alerts'); setIsSidebarOpen(false); }}
              >
                <i className="fa-regular fa-bell notif-icon" aria-hidden="true" />
                <span className="notif-badge">3</span>
              </div>
              <i
                className="fa-solid fa-robot bot-icon"
                aria-hidden="true"
                role="button"
                aria-label="Open Help Hub"
                onClick={() => { setActiveNav('help'); setIsSidebarOpen(false); }}
              />
              <img
                src="https://randomuser.me/api/portraits/men/75.jpg"
                alt="avatar"
                className="avatar-img"
                role="button"
                aria-label="Open Settings"
                onClick={() => { setActiveNav('settings'); setIsSidebarOpen(false); }}
              />
            </div>
          </div>
        </div>
      </div>

  <div className={`fp-content-row ${isSidebarOpen ? 'sidebar-open' : ''}`}>
  <aside className={`fp-sidebar ${isSidebarOpen ? 'open' : ''} ${isSidebarDark ? 'dark' : ''}`}>
        <div className="sidebar-header">
          <div className="brand-row">
            <div className="logo"> <img src={logo} alt="FreightPower" className="landing-logo-image" /></div>
          </div>
          {/* DOT / MC line for mobile drawer */}
          <div className="ids mobile-ids">
            <div className="mobile-id-line"><span className="id-pair"><span className="id-label">DOT:</span> <span className="id-value">{dotNumber || 'N/A'}</span></span></div>
            <div className="mobile-id-line"><span className="id-pair"><span className="id-label">MC:</span> <span className="id-value">{mcNumber || 'N/A'}</span></span></div>
          </div>
          <div className="chips sidebar-chips">
            <span className="chip-cd success">DOT Active</span>
            <span className="chip-cd info">Operating</span>
            <span className="chip-cd yellow">Safety: Satisfactory</span>
            <span className="chip-cd blue">ELD: Samsara</span>
          </div>
          <div className="fleet-stats sidebar-fleet">
            <span className="fleet-item"><i className="fa-solid fa-truck"/> <strong>12</strong> Power Units</span>
            <span className="fleet-item"><i className="fa-solid fa-snowflake"/> <strong>8</strong> Reefers</span>
            <span className="fleet-item"><i className="fa-solid fa-box"/> <strong>15</strong> Dry Vans</span>
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
                    onClick={() => { 
                      setActiveNav(it.key);
                      if (it.key === 'marketplace') {
                        setActiveMarketplaceSection('loads');
                      }
                      if (isSidebarOpen) setIsSidebarOpen(false); 
                    }}
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
        {/* Dark mode control - toggles site theme when clicked */}
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
        {/* action buttons in the mobile drawer */}
        <div className="sidebar-actions">
          <button className="btn small-cd"><i className="fa-solid fa-link"/> Connect</button>
          <button className="btn ghost-cd small"><i className="fa-solid fa-triangle-exclamation"/> Report Fraud</button>
          <button className="btn ghost-cd small subtle"><i className="fa-solid fa-pen"/> Suggest Edit</button>
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
