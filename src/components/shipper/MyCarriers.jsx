import React, { useState, useEffect } from 'react';
import '../../styles/shipper/MyCarriers.css';
import { useAuth } from '../../contexts/AuthContext';
import { API_URL } from '../../config';

export default function MyCarriers() {
  const { currentUser } = useAuth();
  const [activeTab, setActiveTab] = useState('all');
  const [carriers, setCarriers] = useState([]);
  const [loading, setLoading] = useState(true);

  // Fetch carriers from backend (only show carriers that have accepted invitations)
  useEffect(() => {
    const fetchCarriers = async () => {
      if (!currentUser) return;
      
      setLoading(true);
      try {
        const token = await currentUser.getIdToken();
        const response = await fetch(`${API_URL}/carriers/my-carriers`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });
        
        if (response.ok) {
          const data = await response.json();
          // Extract carrier data from relationships
          const carrierList = (data.carriers || []).map(rel => ({
            ...rel,
            id: rel.carrier_id,
            status: rel.status || 'active'
          }));
          setCarriers(carrierList);
        }
      } catch (error) {
        console.error('Error fetching carriers:', error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchCarriers();
  }, [currentUser]);

  const tabs = [
    { id: 'all', label: `All (${carriers.length})` },
    { id: 'active', label: `Active (${carriers.filter(c => c.status === 'active').length})` },
    { id: 'pending', label: 'Pending (0)' },
    { id: 'compliance', label: 'Compliance (0)' },
    { id: 'blocked', label: 'Blocked (0)' }
  ];

  // Filter carriers based on active tab
  const filteredCarriers = carriers.filter(carrier => {
    if (activeTab === 'all') return true;
    if (activeTab === 'active') return carrier.status === 'active';
    // Add more filters as needed
    return false;
  });

  return (
    <div className="fp-dashboard-root shipper-mycarriers">
        <header className="fp-header">
          <div className='sd-carrier-row'>
            <div className="fp-header-titles">
            <h2>Carrier</h2>
            <p className="fp-subtitle">Welcome back! Here's what's happening with your fleet today.</p>
          </div>
          <div className="sd-carrier-row-options">
            <button className="btn small ghost-cd"><i className="fa-solid fa-upload" aria-hidden="true" />Upload Document</button>
            <button className="btn small ghost-cd"><i className="fa-solid fa-download" aria-hidden="true" />Export List</button>
          </div>
          </div>
        </header>

      <section className="cards-row">
        <div className="sd-stat-card">
          <div className="sd-stat-label">Total Carriers</div>
          <div className="sd-stat-value">{loading ? '...' : carriers.length}</div>
          <div className="sd-stat-icon"><i className="fa-solid fa-truck" aria-hidden="true"></i></div>
        </div>
        <div className="sd-stat-card">
          <div className="sd-stat-label">Active Carriers</div>
          <div className="sd-stat-value">{loading ? '...' : carriers.filter(c => c.status === 'active').length}</div>
          <div className="sd-stat-icon"><i className="fa-solid fa-check" aria-hidden="true"></i></div>
        </div>
        <div className="sd-stat-card">
          <div className="sd-stat-label">Pending Invites</div>
          <div className="sd-stat-value">0</div>
          <div className="sd-stat-icon"><i className="fa-solid fa-hourglass" aria-hidden="true"></i></div>
        </div>
        <div className="sd-stat-card">
          <div className="sd-stat-label">Compliance Risk</div>
          <div className="sd-stat-value">0</div>
          <div className="sd-stat-icon"><i className="fa-solid fa-exclamation" aria-hidden="true"></i></div>
        </div>
        <div className="sd-stat-card">
          <div className="sd-stat-label">Avg Rating</div>
          <div className="sd-stat-value">{loading ? '...' : (carriers.length > 0 ? (carriers.reduce((sum, c) => sum + (c.rating || 0), 0) / carriers.length).toFixed(1) : 0)}★</div>
          <div className="sd-stat-icon"><i className="fa-solid fa-star" aria-hidden="true"></i></div>
        </div>
        <div className="sd-stat-card">
          <div className="sd-stat-label">Total Loads</div>
          <div className="sd-stat-value">{loading ? '...' : carriers.reduce((sum, c) => sum + (c.total_loads || 0), 0)}</div>
          <div className="sd-stat-icon"><i className="fa-solid fa-clock" aria-hidden="true"></i></div>
        </div>
      </section>

      <section className="sb-filters-row">
        <div className="tabs" role="tablist" aria-label="Carrier tabs" style={{marginBottom: '20px'}}>
          {tabs.map(t => (
            <button
              key={t.id}
              role="tab"
              aria-selected={activeTab === t.id}
              className={`tab ${activeTab === t.id ? 'active' : ''}`}
              onClick={() => setActiveTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="sb-carrier-controls-row">
          <div className="sb-carrier-filters">
            <select className="sb-carrier-filter-select"><option>All Status</option></select>
            <select className="sb-carrier-filter-select"><option>All Regions</option></select>
            <select className="sb-carrier-filter-select"><option>All Ratings</option></select>
            <select className="sb-carrier-filter-select"><option>Equipment Type</option></select>
            <select className="sb-carrier-filter-select"><option>Compliance</option></select>
          </div>
          <div className="sb-search">
            <input className="sb-search-input" placeholder="Search carriers..." />
          </div>
        </div>
      </section>

      <section className="sb-table-card">
        <div className="sb-table-inner">
        <div className="sb-table-header">
          <div className="th check"><input type="checkbox" /></div>
          <div className="th name">Carrier Name</div>
          <div className="th mc">MC#/DOT</div>
          <div className="th rating">Rating</div>
          <div className="th loads">Loads</div>
          <div className="th status">Status</div>
          <div className="th contact">Contact</div>
          <div className="">Actions</div>
        </div>

        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center', color: '#6b7280' }}>
            <i className="fa-solid fa-spinner fa-spin" style={{ fontSize: '24px', marginBottom: '8px' }}></i>
            <p>Loading carriers...</p>
          </div>
        ) : filteredCarriers.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', color: '#6b7280' }}>
            <i className="fa-solid fa-inbox" style={{ fontSize: '32px', marginBottom: '8px', opacity: 0.3 }}></i>
            <p>No carriers found. Sign up as a carrier to see them appear here.</p>
          </div>
        ) : (
          filteredCarriers.map((carrier, index) => (
            <div className="sb-table-row" key={carrier.id || index}>
              <div className="sb-td check"><input type="checkbox" /></div>
              <div className="sb-td name">
                <div className="avatar">{carrier.name?.slice(0, 2).toUpperCase() || 'NA'}</div>
                <div>
                  <div className="sb-td-name">{carrier.name || 'Unknown Carrier'}</div>
                  <div className="sb-td-sub">{carrier.company_name || 'N/A'}</div>
                </div>
              </div>
              <div className="sb-td mc">
                <div>{carrier.mc_number || 'N/A'}</div>
                <div className="sb-td-sub">{carrier.dot_number || 'N/A'}</div>
              </div>
              <div className="sb-td rating">
                <span className="sb-star">★</span> {carrier.rating || 0}
              </div>
              <div className="sb-td loads">{carrier.total_loads || 0}</div>
              <div className="sb-td status">
                <span className={`int-status-badge ${carrier.status === 'active' ? 'green' : 'gray'}`}>
                  {carrier.status || 'Unknown'}
                </span>
              </div>
              <div className="sb-td contact">
                <div>{carrier.email || 'N/A'}</div>
                <div className="sb-td-sub">{carrier.phone || 'N/A'}</div>
              </div>
              <div className="sb-td">
                <button className="sb-action-btn" title="View Profile">
                  <i className="fa-solid fa-eye"></i>
                </button>
                <button className="sb-action-btn" title="Send Message">
                  <i className="fa-solid fa-envelope"></i>
                </button>
              </div>
            </div>
          ))
        )}

        </div>
      </section>
    </div>
  );
}
