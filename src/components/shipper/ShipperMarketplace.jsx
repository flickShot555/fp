import React, { useState, useEffect } from 'react';
import '../../styles/shipper/ShipperMarketplace.css';
import { useAuth } from '../../contexts/AuthContext';
import { API_URL } from '../../config';

const MARKETPLACE_THRESHOLD = 60;

export default function ShipperMarketplace() {
  const { currentUser } = useAuth();
  const tabs = ['All', 'Public Listings', 'Carriers', 'Service Providers', 'Technology', 'Insurance', 'AI Matches'];

  const regions = ['All Regions', 'North', 'South', 'East', 'West', 'Midwest'];
  const equipment = ['All Equipment', 'Dry Van', 'Reefer', 'Flatbed', 'Container'];
  const ratings = ['All Ratings', '4.5+ Stars', '4.0+ Stars', '3.5+ Stars'];

  const [activeTab, setActiveTab] = useState('All');
  const [openDropdown, setOpenDropdown] = useState(null);
  const [selectedRegion, setSelectedRegion] = useState(regions[0]);
  const [selectedEquipment, setSelectedEquipment] = useState(equipment[0]);
  const [selectedRating, setSelectedRating] = useState(ratings[0]);

  // Marketplace gating state
  const [isMarketplaceReady, setIsMarketplaceReady] = useState(true);
  const [onboardingScore, setOnboardingScore] = useState(100);
  const [nextActions, setNextActions] = useState([]);
  const [checkingAccess, setCheckingAccess] = useState(true);
  const [consentEligible, setConsentEligible] = useState(true);
  const [missingConsents, setMissingConsents] = useState([]);
  const [gatingReason, setGatingReason] = useState('');

  // Check onboarding status AND consent eligibility to gate marketplace
  useEffect(() => {
    const checkMarketplaceAccess = async () => {
      if (!currentUser) {
        setCheckingAccess(false);
        return;
      }

      try {
        const token = await currentUser.getIdToken();

        // Check onboarding score
        const onboardingResponse = await fetch(`${API_URL}/onboarding/coach-status`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });

        let scoreOk = true;
        if (onboardingResponse.ok) {
          const data = await onboardingResponse.json();
          const score = data.total_score || 0;
          setOnboardingScore(score);
          scoreOk = score >= MARKETPLACE_THRESHOLD;
          setNextActions(data.next_best_actions || []);
        }

        // Check consent eligibility
        const consentResponse = await fetch(`${API_URL}/consents/marketplace-eligibility`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });

        let consentsOk = true;
        if (consentResponse.ok) {
          const consentData = await consentResponse.json();
          consentsOk = consentData.eligible;
          setConsentEligible(consentData.eligible);
          setMissingConsents(consentData.missing_consents || []);
        }

        // Determine gating reason
        if (!scoreOk && !consentsOk) {
          setGatingReason('both');
        } else if (!scoreOk) {
          setGatingReason('score');
        } else if (!consentsOk) {
          setGatingReason('consent');
        }

        setIsMarketplaceReady(scoreOk && consentsOk);
      } catch (error) {
        console.error('Error checking marketplace access:', error);
        setIsMarketplaceReady(true);
      } finally {
        setCheckingAccess(false);
      }
    };

    checkMarketplaceAccess();
  }, [currentUser]);

  // Show loading state while checking access
  if (checkingAccess) {
    return (
      <div className="marketplace-loading" style={{ padding: '40px', textAlign: 'center' }}>
        <i className="fa-solid fa-spinner fa-spin" style={{ fontSize: '2rem', color: '#3b82f6' }}></i>
        <p style={{ marginTop: '10px', color: '#64748b' }}>Checking marketplace access...</p>
      </div>
    );
  }

  // Show gating message if onboarding not complete or consents missing
  if (!isMarketplaceReady) {
    return (
      <div className="marketplace-gated" style={{
        padding: '60px 40px',
        textAlign: 'center',
        background: 'linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%)',
        borderRadius: '16px',
        margin: '20px',
        border: '1px solid #e2e8f0'
      }}>
        <div style={{
          width: '80px',
          height: '80px',
          background: '#fef3c7',
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto 20px'
        }}>
          <i className="fa-solid fa-lock" style={{ fontSize: '2rem', color: '#f59e0b' }}></i>
        </div>

        <h2 style={{ fontSize: '1.75rem', color: '#1e293b', marginBottom: '10px' }}>
          Marketplace Access Locked
        </h2>

        <p style={{ color: '#64748b', marginBottom: '20px', maxWidth: '500px', margin: '0 auto 20px' }}>
          {gatingReason === 'consent'
            ? 'You must sign all required consent forms to access the marketplace.'
            : gatingReason === 'both'
            ? 'Complete your onboarding and sign required consent forms to unlock the marketplace.'
            : `Complete your onboarding to unlock the marketplace. Score needed: ${MARKETPLACE_THRESHOLD}%`
          }
        </p>

        {/* Show missing consents if applicable */}
        {!consentEligible && missingConsents.length > 0 && (
          <div style={{
            background: '#fef2f2',
            padding: '15px 20px',
            borderRadius: '12px',
            maxWidth: '400px',
            margin: '0 auto 20px',
            border: '1px solid #fecaca'
          }}>
            <div style={{ fontWeight: '600', color: '#dc2626', marginBottom: '10px' }}>
              <i className="fa-solid fa-file-signature" style={{ marginRight: '8px' }}></i>
              Missing Required Consents
            </div>
            <ul style={{ textAlign: 'left', margin: 0, paddingLeft: '20px', color: '#7f1d1d' }}>
              {missingConsents.map((consent, idx) => (
                <li key={idx} style={{ marginBottom: '5px' }}>
                  {consent.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Show onboarding score if applicable */}
        {(gatingReason === 'score' || gatingReason === 'both') && (
        <div style={{
          background: '#fff',
          padding: '20px',
          borderRadius: '12px',
          maxWidth: '400px',
          margin: '0 auto 30px',
          boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '20px', marginBottom: '15px' }}>
            <div style={{
              width: '60px',
              height: '60px',
              borderRadius: '50%',
              background: onboardingScore >= 50 ? '#fef3c7' : '#fee2e2',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '1.25rem',
              fontWeight: 'bold',
              color: onboardingScore >= 50 ? '#f59e0b' : '#ef4444'
            }}>
              {onboardingScore}%
            </div>
            <div style={{ textAlign: 'left' }}>
              <div style={{ fontWeight: '600', color: '#1e293b' }}>Current Score</div>
              <div style={{ color: '#64748b', fontSize: '0.875rem' }}>
                Need {MARKETPLACE_THRESHOLD - onboardingScore}% more to unlock
              </div>
            </div>
          </div>
        </div>
        )}

        {nextActions.length > 0 && (gatingReason === 'score' || gatingReason === 'both') && (
          <div style={{ textAlign: 'left', maxWidth: '400px', margin: '0 auto' }}>
            <h4 style={{ color: '#1e293b', marginBottom: '10px' }}>Complete These Steps:</h4>
            <ul style={{ listStyle: 'none', padding: 0 }}>
              {nextActions.slice(0, 3).map((action, index) => (
                <li key={index} style={{
                  padding: '10px 15px',
                  background: '#fff',
                  borderRadius: '8px',
                  marginBottom: '8px',
                  border: '1px solid #e2e8f0'
                }}>
                  {action}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    );
  }

  const allListings = [
    {
      id: 'MP-0142',
      lane: 'CHI → DAL',
      equipment: 'Reefer',
      offerCount: '7 offers',
      postedOn: 'Oct 8',
      status: 'Open'
    },
    {
      id: 'MP-0141',
      lane: 'ATL → MIA',
      equipment: 'Dry Van',
      offerCount: '12 offers',
      postedOn: 'Oct 7',
      status: 'Open'
    }
  ];

  const carriers = [
    {
      name: 'Swift Transport',
      dot: '123456',
      mc: '138549',
      location: 'Phoenix, AZ',
      rating: '4.8',
      region: 'Midwest',
      equipment: 'Reefer',
      compliance: 'Verified',
      safety: 'Excellent',
      insuranceStatus: 'Active',
      actionText: 'View'
    },
    {
      name: 'RoadStar Freight',
      dot: '987654',
      mc: '875321',
      location: 'Atlanta, GA',
      rating: '4.6',
      region: 'South',
      equipment: 'Flatbed',
      compliance: 'Valid',
      safety: 'Good',
      insuranceStatus: 'Active',
      actionText: 'Invite'
    },
    {
      name: 'Atlas Hauling',
      dot: '456789',
      mc: '435210',
      location: 'Los Angeles, CA',
      rating: '4.5',
      region: 'West',
      equipment: 'Van',
      compliance: 'Expiring',
      safety: 'Satisfactory',
      insuranceStatus: 'Renewal Due',
      actionText: 'View'
    }
  ];

  const serviceProviders = [
    { name: 'LoadSure', category: 'Insurance', services: 'Freight & cargo coverage', rating: '4.9', status: 'Active', contact: 'email', actionText: 'View' },
    { name: 'EFS', category: 'Fuel', services: 'Fuel cards, payment network', rating: '4.8', status: 'Active', contact: 'website', actionText: 'View' },
    { name: 'OpenFactoring', category: 'Factoring', services: 'Quick pay & cash flow', rating: '4.7', status: 'Active', contact: 'phone', actionText: 'Contact' },
    { name: 'FleetGuard', category: 'Compliance', services: 'Safety, BOC-3, Authority', rating: '4.6', status: 'Renewal Pending', contact: 'email', actionText: 'View' },
    { name: 'TruckerPath', category: 'Technology', services: 'Fleet visibility & routing', rating: '4.9', status: 'Active', contact: 'website', actionText: 'Connect' }
  ];

  // Insurance-specific providers (shown under Insurance tab)
  const insuranceProviders = [
    { name: 'LoadSure', icon: 'fa-solid fa-shield-halved', sub: 'Freight Insurance', category: 'Insurance', services: 'Cargo & liability coverage', rating: '4.9', status: 'Active', contact: 'website', actionText: 'Get Quote' },
    { name: 'CoverWallet', icon: 'fa-solid fa-wallet', sub: 'General Insurance', category: 'Insurance', services: 'COI, cargo, and commercial auto', rating: '4.8', status: 'Active', contact: 'email', actionText: 'Contact' },
    { name: 'FleetGuard Compliance', icon: 'fa-solid fa-clipboard-check', sub: 'Compliance', category: 'Compliance', services: 'BOC-3, IFTA, UCR, safety filings', rating: '4.7', status: 'Active', contact: 'phone', actionText: 'View' },
    { name: 'TruckShield', icon: 'fa-solid fa-truck', sub: 'Safety / Compliance', category: 'Safety', services: 'FMCSA monitoring, document audit', rating: '4.6', status: 'Renewal Pending', contact: 'website', actionText: 'Connect' },
    { name: 'TrueRate', icon: 'fa-solid fa-percent', sub: 'Factoring + Insurance', category: 'Multi Service', services: 'Cargo coverage with load factoring', rating: '4.8', status: 'Active', contact: 'email', actionText: 'View' }
  ];

  const techProviders = [
    { name: 'Motive (KeepTruckin)', icon: 'fa-solid fa-tachometer-alt-fast', iconLabel: 'ELD', tagClass: 'eld', iconClass: 'ic-eld', title: 'HOS tracking, GPS, driver safety monitoring and compliance management', rating: '4.8', status: 'Verified', action: 'Connect' },
    { name: 'Project44', icon: 'fa-solid fa-map-location-dot', iconLabel: 'Visibility', tagClass: 'visibility', iconClass: 'ic-visibility', title: 'Real-time freight tracking and supply chain visibility platform', rating: '4.9', status: 'Verified', action: 'Connect' },
    { name: 'QuickBooks Online', icon: 'fa-solid fa-calculator', iconLabel: 'Accounting', tagClass: 'accounting', iconClass: 'ic-accounting', title: 'Billing, invoicing, and expense tracking for transportation businesses', rating: '4.7', status: 'Active', action: 'Connect' },
    { name: 'OpenTMS', icon: 'fa-solid fa-route', iconLabel: 'TMS', tagClass: 'tms', iconClass: 'ic-tms', title: 'Load management, dispatch optimization and carrier communication', rating: '4.6', status: 'Integration Ready', action: 'View' },
    { name: 'FreightELD', icon: 'fa-solid fa-clipboard-check', iconLabel: 'Compliance', tagClass: 'compliance', iconClass: 'ic-compliance', title: 'Fleet logs, DVIR, fuel tracking and compliance reporting', rating: '4.8', status: 'Verified', action: 'Connect' },
    { name: 'WOFA.ai', icon: 'fa-solid fa-robot', iconLabel: 'AI/Automation', tagClass: 'ai', iconClass: 'ic-ai', title: 'Workflow automation and AI document processing bots', rating: '4.9', status: 'Verified', action: 'Connect' }
  ];

  // AI Matches carrier rows for the AI Matches tab
  const carrierMatches = [
    { name: 'RoadStar Freight', subtitle: 'High compliance, 3 matching lanes', region: 'Midwest', equipment: 'Reefer', match: '97%', compliance: 'Valid', actionText: 'Invite', avatarIcon: 'fa-solid fa-truck', avatarClass: 'match-blue' },
    { name: 'Atlas Hauling', subtitle: 'Strong delivery score', region: 'South', equipment: 'Flatbed', match: '95%', compliance: 'Valid', actionText: 'View', avatarIcon: 'fa-solid fa-box', avatarClass: 'match-purple' },
    { name: 'Skyline Logistics', subtitle: '2 matching lanes', region: 'West', equipment: 'Van', match: '92%', compliance: 'Insurance Expiring', actionText: 'Save', avatarIcon: 'fa-solid fa-shipping-fast', avatarClass: 'match-orange' }
  ];

  React.useEffect(() => {
    function onDocClick() { setOpenDropdown(null); }
    document.addEventListener('click', onDocClick);
    return () => document.removeEventListener('click', onDocClick);
  }, []);

  return (
    <div className="shipper-marketplace">
      {/* Top Dashboard Cards */}
      <div className="dashboard-cards">
        <div className="dashboard-card">
          <div className="card-header">
            <h4>Public Listings</h4>
            <div className="sm-card-icon blue">
              <i className="fa-solid fa-list"/>
            </div>
          </div>
          <div className="card-number">12</div>
          <div className="card-subtitle">3 new today</div>
        </div>

        <div className="dashboard-card">
          <div className="card-header">
            <h4>Verified Carriers</h4>
            <div className="sm-card-icon green">
              <i className="fa-solid fa-question"/>
            </div>
          </div>
          <div className="card-number">2,847</div>
          <div className="card-subtitle">98% compliant</div>
        </div>

        <div className="dashboard-card">
          <div className="card-header">
            <h4>Service Providers</h4>
            <div className="sm-card-icon purple">
              <i className="fa-solid fa-handshake"/>
            </div>
          </div>
          <div className="card-number">156</div>
          <div className="card-subtitle">24 categories</div>
        </div>

        <div className="dashboard-card">
          <div className="card-header">
            <h4>AI Matches</h4>
            <div className="sm-card-icon orange">
              <i className="fa-solid fa-lightbulb"/>
            </div>
          </div>
          <div className="card-number">8</div>
          <div className="card-subtitle">Ready to review</div>
        </div>
      </div>

      {/* Action Bar and Filters */}
      <div className="action-bar">
        <div className="action-left">
          <button className="btn small-cd">
            <i className="fa-solid fa-plus" />
            Post Load to Marketplace
          </button>
          
          <div className="search-wrapper">
            <i className="fa-solid fa-magnifying-glass" />
            <input type="text" placeholder="Search" />
          </div>
        </div>

        <div className="action-right fp-filters">
            <select
              className="sb-carrier-filter-select"
              value={selectedRegion}
              onChange={(e) => setSelectedRegion(e.target.value)}
            >
              {regions.map(r => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>

            <select
              className="sb-carrier-filter-select"
              value={selectedEquipment}
              onChange={(e) => setSelectedEquipment(e.target.value)}
            >
              {equipment.map(eq => (
                <option key={eq} value={eq}>{eq}</option>
              ))}
            </select>

            <select
              className="sb-carrier-filter-select"
              value={selectedRating}
              onChange={(e) => setSelectedRating(e.target.value)}
            >
              {ratings.map(rt => (
                <option key={rt} value={rt}>{rt}</option>
              ))}
            </select>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="mrkt-tabs tabs" style={{marginBottom: '20px'}}>
        {tabs.map(tab => (
          <button
            key={tab}
            className={`tab ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
      </div>

      {activeTab === 'All' && (
        <div className="tab-content">
          {/* Your Public Listings */}
      <div className="all-listings-card">
        <h3>All Listings</h3>
        <div className="listings-table">
          <div className="table-header">
            <div>LISTING ID</div>
            <div>LANE</div>
            <div>EQUIPMENT</div>
            <div>OFFER COUNT</div>
            <div>POSTED ON</div>
            <div>STATUS</div>
            <div>ACTIONS</div>
          </div>
          {allListings.map((listing, index) => (
            <div key={index} className="table-row">
              <div className="listing-id">{listing.id}</div>
              <div className="lane">{listing.lane}</div>
              <div className="equipment">{listing.equipment}</div>
              <div className="offer-count">
                <a href="#" className="int-status-badge blue">{listing.offerCount}</a>
              </div>
              <div className="posted-on">{listing.postedOn}</div>
              <div className="mrkt-status">
                <span className={`int-status-badge ${listing.status.toLowerCase()}`}>
                  {listing.status}
                </span>
              </div>
              <div className="actions">
                <i className="fa-solid fa-ellipsis-h"></i>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Carrier Cards */}
      <div className="carrier-cards">
        {carriers.map((carrier, index) => (
          <div key={index} className="carrier-card">
            <div className='mrkt-sb-carrier-card'>
              <div className='mrkt-sb-name-icon'>
                <div className="carrier-icon">
              <i className="fa-solid fa-truck" aria-hidden="true" />
              </div>
              <div className="mrkt-carrier-details">
              <h4 className="carrier-name">{carrier.name}</h4>
              <p className="mc-number">{carrier.mcNumber}</p>
              </div>
              </div>
              <div className="mrkt-carrier-rating">
                <i className="fa-solid fa-star" /> 
                <span>{carrier.rating}</span>
              </div>
            </div>
            <div className="mrkt-carrier-details">
                <div className="detail-item">
                  <span className="detail-label">Region:</span>
                  <span className="detail-value">{carrier.region}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Equipment:</span>
                  <span className="detail-value">{carrier.equipment}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Compliance:</span>
                  <span className="detail-value">
                    <span className={`int-status-badge ${carrier.compliance}`}>
                  {carrier.compliance}
                    </span>
                  </span>
                </div>
              </div>
              <div className="carrier-actions">
              <button className="btn small-cd" style={{width: '100%'}}>Snapshot</button>
              <button className="btn small ghost-cd" style={{width: '100%'}}>Invite</button>
            </div>
          </div>
        ))}
      </div>

      {/* AI Recommendations */}
      <div className="ai-recommendations">
        <h3>
          AI Recommendations
        </h3>
        
        <div className="recommendation-cards">
          <div className="recommendation-card best-fit">
            <div className="recommendation-content">
              <h4>Best Fit for CHI → DAL Route</h4>
              <p>Based on equipment type, route history, and ratings</p>
              <div className="recommendation-summary">
                <span className="summary-item">3 carriers recommended</span>
                <span className="summary-item">96% match confidence</span>
              </div>
            </div>
            <button className="btn small-cd">View Matches</button>
          </div>

          <div className="recommendation-card rate-intel">
            <div className="recommendation-content">
              <h4>Rate Intelligence Update</h4>
              <p>Market rates for your active lanes have changed</p>
              <div className="rate-changes">
                <span className="rate-change positive">+$120 avg on CHI-DAL</span>
                <span className="rate-change negative">-$80 avg on ATL-MIA</span>
              </div>
            </div>
            <button className="btn small-cd">View Details</button>
          </div>
        </div>
      </div>
        </div>
      )}

      {activeTab === 'Public Listings' && (
        <div className="tab-content">
          {/* Your Public Listings */}
      <div className="all-listings-card">
        <h3>Public Listings</h3>
        <div className="listings-table">
          <div className="table-header">
            <div>LISTING ID</div>
            <div>LANE</div>
            <div>EQUIPMENT</div>
            <div>OFFER COUNT</div>
            <div>POSTED ON</div>
            <div>STATUS</div>
            <div>ACTIONS</div>
          </div>
          {allListings.map((listing, index) => (
            <div key={index} className="table-row">
              <div className="listing-id">{listing.id}</div>
              <div className="lane">{listing.lane}</div>
              <div className="equipment">{listing.equipment}</div>
              <div className="offer-count">
                <a href="#" className="offer-link">{listing.offerCount}</a>
              </div>
              <div className="posted-on">{listing.postedOn}</div>
              <div className="mrkt-status">
                <span className={`int-status-badge ${listing.status.toLowerCase()}`}>
                  {listing.status}
                </span>
              </div>
              <div className="actions">
                <i className="fa-solid fa-ellipsis-h"></i>
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="listings-summary">
          <div className="summary-box">
            <i className="fa-solid fa-circle-info" />
            <span>You have 3 open listings this week · 2 carriers awaiting confirmation · Avg offer rate $2.92/mi</span>
          </div>
        </div>
        </div>
      )}

      {activeTab === 'Carriers' && (
        <div className="tab-content">
          <div className="carrier-listings-card">
            <div className="carriers-table-wrapper">
              <h3>Carrier Listings</h3>
              <table className="carriers-table">
                <thead>
                  <tr>
                    <th>CARRIER NAME</th>
                    <th>DOT / MC</th>
                    <th>REGION</th>
                    <th>EQUIPMENT</th>
                    <th>RATING</th>
                    <th>COMPLIANCE</th>
                    <th>SAFETY</th>
                    <th>INSURANCE</th>
                    <th>ACTIONS</th>
                  </tr>
                </thead>
                <tbody>
                  {carriers.map((c, idx) => (
                    <tr key={idx}>
                      <td className="c-name">
                        <div className="avatar" aria-hidden>{c.name.split(' ').map(n=>n[0]).slice(0,2).join('')}</div>
                        <div className="c-name-details">
                          <div className="c-name-title">{c.name}</div>
                          <div className="c-location">{c.location}</div>
                        </div>
                      </td>
                      <td className="c-dotmc"><div>DOT {c.dot}</div><div>MC {c.mc}</div></td>
                      <td>{c.region}</td>
                      <td>{c.equipment}</td>
                      <td> <span>{c.rating}</span></td>
                      <td><span className={`int-status-badge ${c.compliance}`}>{c.compliance}</span></td>
                      <td>{c.safety}</td>
                      <td>
                        <span className={`int-status-badge ${c.insuranceStatus ? c.insuranceStatus.toLowerCase().replace(/\s+/g,'-') : ''} ${c.insuranceStatus && c.insuranceStatus.toLowerCase().includes('renewal') ? 'revoked' : ''}`.trim()}>
                          {c.insuranceStatus}
                        </span>
                      </td>
                      <td><i className="fa-solid fa-ellipsis-h"></i></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="listings-summary">
          <div className="summary-box">
            <i className="fa-solid fa-circle-info" />
            <span>12 carriers match your active lanes (Midwest -{'>'} South) · 4 with expiring insurance · 3 recommended for refeer lanes.</span>
          </div>
        </div>
        </div>
      )}

      {activeTab === 'Service Providers' && (
        <div className="tab-content">
          <div className="provider-listings-card">
            <h3>Available Service Providers</h3>
            <div className="providers-table-wrapper">
              <table className="providers-table">
                <thead>
                  <tr>
                    <th>PROVIDER</th>
                    <th>CATEGORY</th>
                    <th>SERVICES</th>
                    <th>RATING</th>
                    <th>STATUS</th>
                    <th>CONTACT</th>
                    <th>ACTION</th>
                  </tr>
                </thead>
                <tbody>
                  {serviceProviders.map((p, i) => (
                    <tr key={i}>
                      <td className="p-name"><div className="avatar small">{p.name.split(' ').map(s=>s[0]).slice(0,2).join('')}</div><div className="p-details"><div className="p-title">{p.name}</div><div className="p-sub">{p.category} Provider</div></div></td>
                      <td><span className={`int-status-badge blue ${p.category.toLowerCase()}`}>{p.category}</span></td>
                      <td className="p-services">{p.services}</td>
                      <td className="p-rating"> {p.rating}</td>
                      <td>
                        <span className={`int-status-badge ${p.status.toLowerCase()} ${p.status.toLowerCase().includes('pending') ? 'revoked' : ''}`.trim()}>
                          {p.status}
                        </span>
                      </td>
                      <td className="p-contact">{p.contact === 'email' ? <i className="fa-solid fa-envelope"/> : p.contact === 'phone' ? <i className="fa-solid fa-phone"/> : <i className="fa-solid fa-globe"/>}</td>
                      <td className="p-action"><i className="fa-solid fa-ellipsis-h"></i> </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="listings-summary">
          <div className="summary-box">
            <i className="fa-solid fa-circle-info" />
            <span>3 providers match your company type (factoring & ELD integrations) · 2 offering discounts this month.</span>
          </div>
        </div>
        </div>
      )}

      {activeTab === 'Insurance' && (
        <div className="tab-content">
          <div className="provider-listings-card">
            <h3>Insurance Providers</h3>
            <div className="providers-table-wrapper">
              <table className="providers-table">
                <thead>
                  <tr>
                    <th>PROVIDER</th>
                    <th>CATEGORY</th>
                    <th>SERVICES</th>
                    <th>RATING</th>
                    <th>STATUS</th>
                    <th>CONTACT</th>
                    <th>ACTION</th>
                  </tr>
                </thead>
                <tbody>
                  {insuranceProviders.map((p, i) => (
                    <tr key={i}>
                      <td className="p-name"><div className={`avatar small icon-bg`}><i className={p.icon} aria-hidden="true"/></div><div className="p-details"><div className="p-title">{p.name}</div><div className="p-sub">{p.sub}</div></div></td>
                      <td><span className={`int-status-badge blue ${p.category.toLowerCase().replace(/\s+/g,'-')}`}>{p.category}</span></td>
                      <td className="p-services">{p.services}</td>
                      <td className="p-rating"><i className="fa-solid fa-star"/> <span>{p.rating}</span></td>
                      <td><span className={`int-status-badge ${p.status.toLowerCase().replace(/\s+/g,'-')} ${p.status.toLowerCase().includes('verified') ? 'active' : ''} ${p.status.toLowerCase().includes('pending') ? 'warning' : ''}`.trim()}>{p.status}</span></td>
                      <td className="p-contact">{p.contact === 'email' ? <i className="fa-solid fa-envelope"/> : p.contact === 'phone' ? <i className="fa-solid fa-phone"/> : <i className="fa-solid fa-globe"/>}</td>
                      <td className="p-action"><i className="fa-solid fa-ellipsis-h"></i></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="listings-summary">
          <div className="summary-box">
            <i className="fa-solid fa-circle-info" />
            <span>4 insurance providers offer same-day cargo coverage · 3 compliance partners have auto-renew integration support.</span>
          </div>
        </div>
        </div>
      )}

      {activeTab === 'Technology' && (
        <div className="tab-content">
          <div className="tech-grid">
            {techProviders.map((p, i) => (
              <div key={i} className="tech-card">
                <div className="tech-top">
                    <div className={`tech-icon ${p.iconClass || ''}`}><i className={p.icon} aria-hidden="true" /></div>
                    <div className="tech-top-right"><div className="tech-title">{p.name}</div><div className={`tech-pill ${p.tagClass || ''}`}>{p.iconLabel || ''}</div></div>
                    <div className="tech-rating"><i className="fa-solid fa-star"/> {p.rating}</div>
                  </div>

                <div className="tech-desc">{p.title}</div>

                <div className="tech-bottom">
                  <div className={`int-status-badge active`}>{p.status}</div>
                  <button className="btn small-cd">{p.action}</button>
                </div>
              </div>
            ))}
          </div>
          <div className="listings-summary">
          <div className="summary-box">
            <i className="fa-solid fa-circle-info" />
            <span>6 tools matches your company type · 3 automation ready · 2 integrations pre-approved.</span>
          </div>
        </div>
        </div>
      )}

      {activeTab === 'AI Matches' && (
        <div className="tab-content ai-matches">
          <div className='headings-ai-tab'>Carrier Matches</div>
          <div className="carrier-listings-card">
            <div className="carriers-matches-table">
              {/* reuse carriers-table styles so AI matches keep same theme */}
              <table className="carriers-table">
              <thead>
                <tr>
                  <th>CARRIER</th>
                  <th>REGION</th>
                  <th>EQUIPMENT</th>
                  <th>MATCH %</th>
                  <th>COMPLIANCE</th>
                  <th>ACTION</th>
                </tr>
              </thead>
              <tbody>
                {carrierMatches.map((c, i) => (
                  <tr key={i}>
                    <td className="c-name">
                      <div className={`avatar small ${c.avatarClass}`} aria-hidden><i className={c.avatarIcon} aria-hidden="true"/></div>
                      <div className="c-name-details">
                        <div className="c-name-title">{c.name}</div>
                        {/* reuse c-location styling for the subtitle */}
                        <div className="c-location">{c.subtitle}</div>
                      </div>
                    </td>
                    <td>{c.region}</td>
                    <td>{c.equipment}</td>
                    <td className="c-rating">{c.match}</td>
                    <td><span className={`int-status-badge ${c.compliance}`}>{c.compliance}</span></td>
                    <td className="c-actions"><i className='fa fa-ellipsis-h'></i></td>
                  </tr>
                ))}
              </tbody>
              </table>
            </div>
          </div>
          <div className='headings-ai-tab' style={{ marginTop: '20px' }}>Service Provider Matches</div>
          <div className="service-matches-wrap">
            <div className="matches-grid">
              <div className="match-card">
                <div className="match-top">
                  <div className="match-left">
                    <div className="tech-icon match-avatar"><i className="fa-solid fa-shield-halved"/></div>
                    <div className="match-meta">
                      <div className="match-title">LoadSure</div>
                      <div className="match-sub">Insurance</div>
                      <div className="match-desc">Lower cargo coverage rates</div>
                    </div>
                  </div>
                  <div className="match-percent">96%</div>
                </div>
                <div className="match-cta"><button className="btn small-cd">Contact ›</button></div>
              </div>

              <div className="match-card">
                <div className="match-top">
                  <div className="match-left">
                    <div className="tech-icon match-avatar"><i className="fa-solid fa-clipboard-check"/></div>
                    <div className="match-meta">
                      <div className="match-title">FleetGuard</div>
                      <div className="match-sub">Compliance</div>
                      <div className="match-desc">Auto-renew FMCSA docs</div>
                    </div>
                  </div>
                  <div className="match-percent">92%</div>
                </div>
                <div className="match-cta"><button className="btn small-cd">Connect ›</button></div>
              </div>

              <div className="match-card">
                <div className="match-top">
                  <div className="match-left">
                    <div className="tech-icon match-avatar"><i className="fa-solid fa-sack-dollar"/></div>
                    <div className="match-meta">
                      <div className="match-title">OpenFactoring</div>
                      <div className="match-sub">Factoring</div>
                      <div className="match-desc">Quick pay for carriers</div>
                    </div>
                  </div>
                  <div className="match-percent">90%</div>
                </div>
                <div className="match-cta"><button className="btn small-cd">View ›</button></div>
              </div>
            </div>
          </div>
          <div className='headings-ai-tab' style={{ marginTop: '20px' }}>Technology Matches</div>
          <div className="tech-matches-wrap">
            <div className="matches-grid">
              <div className="match-card">
                <div className="match-top">
                  <div className="match-left">
                    <div className="tech-icon match-avatar"><i className="fa-solid fa-clipboard-check" /></div>
                    <div className="match-meta">
                      <div className="match-title">FreightELD</div>
                      <div className="match-sub">ELD & Compliance</div>
                      <div className="match-desc">API Integration</div>
                    </div>
                  </div>
                  <div className="match-percent">98%</div>
                </div>
                <div className="match-cta"><button className="btn small-cd">Connect ›</button></div>
              </div>

              <div className="match-card">
                <div className="match-top">
                  <div className="match-left">
                    <div className="tech-icon ic-ai match-avatar"><i className="fa-solid fa-robot" /></div>
                    <div className="match-meta">
                      <div className="match-title">WOFA.ai</div>
                      <div className="match-sub">Automation / AI</div>
                      <div className="match-desc">Workflow Assistant</div>
                    </div>
                  </div>
                  <div className="match-percent">95%</div>
                </div>
                <div className="match-cta"><button className="btn small-cd">View ›</button></div>
              </div>

              <div className="match-card">
                <div className="match-top">
                  <div className="match-left">
                    <div className="tech-icon ic-accounting match-avatar"><i className="fa-solid fa-calculator" /></div>
                    <div className="match-meta">
                      <div className="match-title">QuickBooks</div>
                      <div className="match-sub">Accounting</div>
                      <div className="match-desc">API / OAuth</div>
                    </div>
                  </div>
                  <div className="match-percent">91%</div>
                </div>
                <div className="match-cta"><button className="btn small-cd">Connect ›</button></div>
              </div>
            </div>
          </div>
          <div className='headings-ai-tab' style={{ marginTop: '20px' }}>Rate & market Insights</div>
          <div className="aii-insights-row">
              <div className="match-card insight-green">
                <div className="aii-insight-title">Rate Increase</div>
                <div className="aii-insight-desc">MN → TX reefer rates are up 4.2% — consider posting more loads.</div>
                <div className="aii-insight-cta"><button className="btn small-cd">Post Load</button></div>
              </div>
              <div className="match-card insight-blue">
                <div className="aii-insight-title">New Carriers</div>
                <div className="aii-insight-desc">5 new carriers available in your service area.</div>
                <div className="aii-insight-cta"><button className="btn small-cd">View Carriers</button></div>
              </div>
              <div className="match-card insight-purple">
                <div className="aii-insight-title">Top Lane</div>
                <div className="aii-insight-desc">Top performing lane: Midwest → South (avg $2.92/mi).</div>
                <div className="aii-insight-cta"><button className="btn small-cd ">Save Insight</button></div>
              </div>
            </div>
            <div className='headings-ai-tab' style={{ marginTop: '20px' }}>Opportunities</div>
            <div className="opps-list">
              <div className="opp-item">
                <div className="opp-left">
                  <div className="opp-icon opp-icon-warning"><i className="fa-solid fa-shield-halved"/></div>
                  <div>
                    <div className="opp-title">Insurance Provider Missing</div>
                    <div className="opp-desc">You haven't connected an insurance provider — save up to 12% on coverage.</div>
                  </div>
                </div>
                <div className="opp-cta"><button className="btn small-cd">Connect</button></div>
              </div>

              <div className="opp-item">
                <div className="opp-left">
                  <div className="opp-icon opp-icon-alert"><i className="fa-solid fa-triangle-exclamation"/></div>
                  <div>
                    <div className="opp-title">Compliance Documents Expiring</div>
                    <div className="opp-desc">2 compliance documents expiring soon — connect with FleetGuard.</div>
                  </div>
                </div>
                <div className="opp-cta"><button className="btn small-cd">Fix Compliance</button></div>
              </div>

              <div className="opp-item">
                <div className="opp-left">
                  <div className="opp-icon opp-icon-integration"><i className="fa-solid fa-plug"/></div>
                  <div>
                    <div className="opp-title">Integration Opportunities</div>
                    <div className="opp-desc">3 tech tools integrate directly with your current setup — Connect now.</div>
                  </div>
                </div>
                <div className="opp-cta"><button className="btn small-cd">Connect Now</button></div>
              </div>
            </div>

            <div className="ai-analysis-box">
              <div className="ai-analysis-left"><div className="aai-icon"><i className="fa-solid fa-robot"/></div></div>
              <div className="ai-analysis-body">
                <div className="ai-analysis-title">AI Analysis Complete</div>
                <div className="ai-analysis-desc">AI scanned 1,243 regional carriers • Found 18 matches above 90% fit • 4 service providers recommended based on your last 5 loads.</div>
              </div>
            </div>

        </div>
      )}
    </div>
  );
}
