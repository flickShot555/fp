import React, { useState, useEffect } from 'react';
import '../../styles/driver/MyCarrier.css';
import { useAuth } from '../../contexts/AuthContext';
import { API_URL } from '../../config';

export default function MyCarrier() {
  const { currentUser } = useAuth();
  const [activeTab, setActiveTab] = useState('Active');
  const [isDarkMode, setIsDarkMode] = useState(false); // Local dark mode state, like Marketplace
  const [carrier, setCarrier] = useState(null);
  const [carrierLoading, setCarrierLoading] = useState(true);

  // Fetch carrier information
  useEffect(() => {
    const fetchCarrier = async () => {
      if (!currentUser) {
        setCarrierLoading(false);
        return;
      }

      setCarrierLoading(true);
      try {
        const token = await currentUser.getIdToken();
        const response = await fetch(`${API_URL}/drivers/my-carrier`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });

        if (response.ok) {
          const data = await response.json();
          setCarrier(data.carrier);
        }
      } catch (error) {
        console.error('Error fetching carrier:', error);
        setCarrier(null);
      } finally {
        setCarrierLoading(false);
      }
    };

    fetchCarrier();
  }, [currentUser]);

  return (
    <>
      {/* Optional: Add a toggle button for demo/testing */}
      {/* <button onClick={() => setIsDarkMode(d => !d)}>Toggle Dark Mode</button> */}
      <section className={`dd-grid${isDarkMode ? ' dark' : ''}`}>
          {/* Carrier Info Card */}
          {carrierLoading ? (
            <div className="card mc-carrier-card">
              <div style={{ padding: '40px', textAlign: 'center' }}>
                <i className="fa-solid fa-spinner fa-spin" style={{ fontSize: '24px', marginRight: '10px' }}></i>
                Loading carrier information...
              </div>
            </div>
          ) : !carrier ? (
            <div className="card mc-carrier-card">
              <div style={{ padding: '40px', textAlign: 'center', color: '#666' }}>
                <i className="fa-solid fa-building" style={{ fontSize: '48px', marginBottom: '20px', opacity: 0.5 }}></i>
                <h3 style={{ marginBottom: '12px' }}>No Carrier Assigned</h3>
                <p>You are not currently hired by any carrier. Once a carrier hires you from the marketplace, their information will appear here.</p>
              </div>
            </div>
          ) : (
          <div className="card mc-carrier-card">
            <div className="mc-carrier-header">
              <div className="mc-carrier-logo">
                {(() => {
                  const name = carrier.name || carrier.company_name || '';
                  if (name) {
                    const initials = name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
                    return initials || 'CA';
                  }
                  return 'CA';
                })()}
              </div>
              <div className="mc-carrier-info">
                <div className="mc-carrier-name">
                  <h3>{carrier.name || carrier.company_name || 'Unknown Carrier'}</h3>
                  <span className="int-status-badge active">
                    {carrier.status === 'active' ? 'Active Carrier' : 'Verified Carrier'}
                  </span>
                </div>
                <div className="mc-carrier-details">
                  {carrier.dot_number && (
                    <span className="mc-detail">DOT: {carrier.dot_number}</span>
                  )}
                  {carrier.mc_number && (
                    <span className="mc-detail">MC: {carrier.mc_number}</span>
                  )}
                  {carrier.service_areas && carrier.service_areas.length > 0 && (
                    <span className="mc-detail">{carrier.service_areas[0]}</span>
                  )}
                  {carrier.email && (
                    <span className="mc-detail">{carrier.email}</span>
                  )}
                </div>
              </div>
              <div className="mc-carrier-status">
                <span className="int-status-badge active">{carrier.status === 'active' ? 'Active' : 'Active'}</span>
                {carrier.rating && (
                  <div className="mc-rating">
                    <i className="fa-solid fa-star"></i>
                    <span>{carrier.rating} Rating</span>
                  </div>
                )}
                {carrier.total_loads && (
                  <div className="mc-rating" style={{ marginTop: '8px' }}>
                    <span>{carrier.total_loads} Loads</span>
                  </div>
                )}
              </div>
            </div>
          </div>
          )}

            {/* AI Assistant Alert */}
          <div className="mc-ai-alert-card" style={{marginTop: '10px', marginBottom: '10px'}}>
            <div className="mc-ai-alert">
              <div className="mc-ai-content" >
                <h4 style={{fontWeight: '700', color: 'white'}}>AI Assistant</h4>
                <p style={{color: "white"}}>Your CDL expires in 45 days. Upload renewal to maintain compliance.</p>
              </div>
              <button className="btn small ghost-cd dd-btn">Upload Now</button>
            </div>
          </div>



          {/* Two Column Layout */}
          <div className="mc-two-column-layout">
            {/* Left Column */}
            <div className="mc-left-column">
              {/* Active Load Card */}
              <div className="card mc-active-load-card">
                <div className="mc-load-header">
                  <div className="mc-load-title">
                    <span className="mc-load-badge">Active Load #TL-4829</span>
                    <span className="int-status-badge active">In Transit</span>
                  </div>
                  <div className="mc-load-actions">
                    <button className="btn small mc-view-route-btn">
                      View Route
                    </button>
                    <button className="btn small mc-message-dispatch-btn">
                      Message Dispatch
                    </button>
                  </div>
                </div>

                <div className="mc-load-details">
                  <div className="mc-load-locations">
                    <div className="mc-location pickup">
                      <h5>Pickup</h5>
                      <p>Amazon Warehouse</p>
                      <p>1234 Industrial Blvd, Atlanta, GA 30309</p>
                      <p className="mc-status-text">
                        <i className="fa-solid fa-check"></i>
                        Completed - 2 hours ago
                      </p>
                    </div>
                    <div className="mc-location delivery">
                      <h5>Delivery</h5>
                      <p>Walmart Distribution</p>
                      <p>5678 Commerce Way, Jacksonville, FL 32218</p>
                      <p>ETA: 4:30 PM (127 miles left)</p>
                    </div>
                  </div>

                  <div className="mc-progress-section">
                    <div className="mc-progress-header">
                      <span style={{fontWeight: '650'}}>Trip Progress</span>
                      <span style={{fontWeight: '650'}}>68% Complete</span>
                    </div>
                    <div className="mc-progress-bar">
                      <div className="mc-progress-fill" style={{width: '68%'}}></div>
                    </div>
                  </div>

                  <div className="mc-load-buttons">
                    <button className="btn small ghost-cd">
                      <i className="fa-solid fa-file-text"></i>
                      View Docs
                    </button>
                    <button className="btn small ghost-cd">
                      <i className="fa-solid fa-upload"></i>
                      Upload POD
                    </button>
                  </div>
                </div>
              </div>

              {/* Assignments Section */}
              <div className="card mc-assignments-card">
                <div className="mc-assignments-header">
                  <h3>Assignments</h3>
                  <div className="mc-assignment-tabs">
                    <button 
                      className={`mc-tab ${activeTab === 'Active' ? 'active' : ''}`}
                      onClick={() => setActiveTab('Active')}
                    >
                      Active
                    </button>
                    <button 
                      className={`mc-tab ${activeTab === 'Completed' ? 'active' : ''}`}
                      onClick={() => setActiveTab('Completed')}
                    >
                      Completed
                    </button>
                    <button 
                      className={`mc-tab ${activeTab === 'Archived' ? 'active' : ''}`}
                      onClick={() => setActiveTab('Archived')}
                    >
                      Archived
                    </button>
                  </div>
                </div>

                <div className="mc-assignment-list">
                  <div className="mc-assignment-item">
                    <div className="mc-assignment-info">
                      <h4>Load #TL-4830</h4>
                      <span className="int-status-badge active">Assigned</span>
                      <div className="mc-assignment-route">
                        <p>From: Miami, FL</p>
                        <p>Home Depot Warehouse</p>
                      </div>
                      <div className="mc-assignment-route">
                        <p>To: Tampa, FL</p>
                        <p>Lowe's Distribution</p>
                      </div>
                      <div className="mc-assignment-details">
                        <span>245 miles • $580</span>
                      </div>
                    </div>
                    <div className="mc-assignment-schedule">
                      <p>Pickup: Tomorrow 8:00 AM</p>
                      <button className="btn small-cd">Start Trip</button>
                    </div>
                  </div>

                  <div className="mc-assignment-item">
                    <div className="mc-assignment-info">
                      <h4>Load #TL-4831</h4>
                      <span className="int-status-badge pending">Pending</span>
                      <div className="mc-assignment-route">
                        <p>From: Orlando, FL</p>
                        <p>Target Distribution</p>
                      </div>
                      <div className="mc-assignment-route">
                        <p>To: Savannah, GA</p>
                        <p>Walmart Supercenter</p>
                      </div>
                      <div className="mc-assignment-details">
                        <span>312 miles • $720</span>
                      </div>
                    </div>
                    <div className="mc-assignment-schedule">
                      <p>Pickup: Dec 28, 10:00 AM</p>
                      <button className="btn small-cd">View Details</button>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Right Column */}
            <div className="mc-right-column">
              {/* Compliance Sync */}
              <div className="card mc-compliance-card">
                <div className="card-header">
                  <h3>Compliance Sync</h3>
                </div>
                <div className="mc-compliance-list">
                  <div className="mc-compliance-item">
                    <span>CDL License</span>
                    <div className="mc-status-icon">
                      <i className="fa-solid fa-check"></i>
                    </div>
                  </div>
                  <div className="mc-compliance-item">
                    <span>Medical Certificate</span>
                    <div className="mc-status-icon">
                      <i className="fa-solid fa-check"></i>
                    </div>
                  </div>
                  <div className="mc-compliance-item">
                    <span>Background Check</span>
                    <div className="mc-status-icon ">
                      <i className="fa-solid fa-check"></i>
                    </div>
                  </div>
                  <div className="mc-compliance-item">
                    <span>Drug Test</span>
                    <div className="mc-status-icon">
                      <i className="fa-solid fa-exclamation-triangle"></i>
                    </div>
                  </div>
                  <div className="mc-compliance-item">
                    <span>Insurance</span>
                    <div className="mc-status-icon">
                      <i className="fa-solid fa-check"></i>
                    </div>
                  </div>
                </div>
                <p className="int-status-badge active">
                  Driver has consented to share information with this carrier.
                </p>
              </div>

              {/* Communication Hub */}
              <div className="card mc-communication-card">
                <div className="card-header">
                  <h3>Communication Hub</h3>
                </div>
                <div className="mc-contact-info">
                  <div className="mc-dispatcher">
                    <img src="https://randomuser.me/api/portraits/women/32.jpg" alt="Sarah Johnson" className="mc-dispatcher-avatar" />
                    <div className="mc-dispatcher-info">
                      <h4>Sarah Johnson</h4>
                      <span>Dispatcher</span>
                    </div>
                  </div>
                  
                  <div className="mc-recent-activity">
                    <h4>Recent Activity</h4>
                    <span className="mc-activity-time">2 min ago</span>
                    <p>"Load #TL-4829 delivery confirmed. Great job!"</p>
                  </div>

                  <div className="mc-communication-actions">
                    <button className="btn small-cd">
                      <i className="fa-solid fa-message"></i>
                      Message
                    </button>
                    <button className="btn small-cd">
                      <i className="fa-solid fa-phone"></i>
                      Call
                    </button>
                  </div>
                </div>
              </div>

              {/* Quick Actions */}
              <div className="card mc-quick-actions-card">
                <div className="card-header">
                  <h3>Quick Actions</h3>
                </div>
                <div className="mc-quick-actions">
                  <button className="btn small-cd">
                    <i className="fa-solid fa-upload"></i>
                    <span>Upload Documents</span>
                  </button>
                  <button className="btn small-cd">
                    <i className="fa-solid fa-calendar"></i>
                    <span>View Schedule</span>
                  </button>
                  <button className="btn small-cd">
                    <i className="fa-solid fa-chart-line"></i>
                    <span>Performance Report</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </section>
      </>
    );
}