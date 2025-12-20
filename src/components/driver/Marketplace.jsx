import React, { useState, useEffect } from 'react';
import '../../styles/driver/Marketplace.css';
import { useAuth } from '../../contexts/AuthContext';
import { API_URL } from '../../config';

const MARKETPLACE_THRESHOLD = 60;

export default function Marketplace({ isPostHire, setIsPostHire }) {
  const { currentUser } = useAuth();
  const [isDarkMode, setIsDarkMode] = useState(false);
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

  function PostHireMarketplaceView() {
    return (
      <>
        <header className="fp-header">
          <div className="fp-header-titles">
            <h2>Marketplace</h2>
            <p className="fp-subtitle">Your smart CDL staffing hub - connect with carriers and service providers</p>
            <button onClick={() => setIsPostHire(false)} className="btn small dd-back-btn">Pre-Hire</button>
          </div>
        </header>
        
        <section className="fp-grid">
          {/* Driver Availability Section */}
          <div className="card mp-availability-card">
            <div className="card-header">
              <h3>Driver Availability</h3>
              <span className="int-status-badge active">Currently Available</span>
            </div>
            <div className="mp-availability-content">
              <div className="mp-visibility-status">
                <div className="mp-status-icon active"></div>
                <span>You are visible to carriers in FreightPower's staffing pool</span>
              </div>
              <div className="mp-consent-info">
                <p className="mp-consent-text">By being available, you've agreed to share your CDL & compliance information with carriers through FreightPower.</p>
                <button className='btn small-cd'>
                  <i className="fa-solid fa-info-circle"></i>
                  Auto-Consent Active
                </button>
              </div>
            </div>
          </div>

          {/* Promote Myself Section */}
          <div className="mp-promote-card">
            <div className="mp-promote-content">
              <div className="mp-promote-header">
                <i className="fa-solid fa-star"></i>
                <h4>Promote Myself</h4>
              </div>
              <p className="mp-promote-text">Boost your profile to appear higher in carrier searches</p>
              <button className="btn small-cd">Promote Profile - $9.99</button>
            </div>
          </div>

          {/* AI Staffing Insights */}
          <div className="card mp-ai-insights-card">
            <div className="mp-ai-header">
              <h3>AI Staffing Insights</h3>
            </div>
            <div className="mp-insights-grid">
              <div className="mp-insight-item high-demand">
                <div className="mp-insight-header">
                  <i className="fa-solid fa-trending-up"></i>
                  <span>High Demand Alert</span>
                </div>
                <p>There are 12 carriers in your region actively hiring — make sure your profile is up to date.</p>
              </div>
              <div className="mp-insight-item special-offer">
                <div className="mp-insight-header">
                  <i className="fa-solid fa-gift"></i>
                  <span>Special Offer</span>
                </div>
                <p>20% discount available with CDL protection service this week only.</p>
              </div>
            </div>
          </div>

          {/* Service Providers Hub */}
          <div className="card mp-services-card">
            <div className="card-header">
              <h3>Service Providers Hub</h3>
              <div className="mp-search-bar">
                <i className="fa-solid fa-search"></i>
                <input type="text" placeholder="Search services..." />
              </div>
            </div>
            
            <div className="mp-services-grid">
              <div className="mp-service-category">
                <div>
                  <div className="mp-service-icon cdl-protection">
                  <i className="fa-solid fa-shield"></i>
                </div>
                <h4>CDL Protection (TVC)</h4>
                <p>Protect your CDL with expert legal representation and violation defense services.</p>
                <span className="int-status-badge warning">20% Off This Week</span>
                </div>
                <button className="btn small-cd" style={{marginTop: '20px', width: '100%'}}>Connect</button>
              </div>

              <div className="mp-service-category">
                <div>
                  <div className="mp-service-icon eld-solutions">
                  <i className="fa-solid fa-tablet-screen-button"></i>
                </div>
                <h4>ELD Solutions</h4>
                <p>Advanced ELD integrations with real-time compliance monitoring and reporting.</p>
                <span className="int-status-badge warning">Multiple Options</span>
                </div>
                <button className="btn small-cd" style={{marginTop: '20px', width: '100%'}}>Connect</button>
              </div>

              <div className="mp-service-category">
                <div>
                  <div className="mp-service-icon fuel-programs">
                  <i className="fa-solid fa-gas-pump"></i>
                </div>
                <h4>Fuel Programs</h4>
                <p>Access exclusive fuel discounts and rewards programs nationwide.</p>
                <span className="int-status-badge active">Save up to 15¢/gal</span>
                </div>
                <button className="btn small-cd" style={{marginTop: '20px', width: '100%'}}>Connect</button>
              </div>

              <div className="mp-service-category">
                <div>
                  <div className="mp-service-icon roadside">
                  <i className="fa-solid fa-wrench"></i>
                </div>
                <h4>Roadside Repair</h4>
                <p>24/7 roadside assistance and repair network for emergency breakdowns.</p>
                <span className="int-status-badge warning">24/7 Available</span>
                </div>
                <button className="btn small-cd" style={{marginTop: '20px', width: '100%'}}>Connect</button>
              </div>

              <div className="mp-service-category">
                <div>
                  <div className="mp-service-icon training">
                  <i className="fa-solid fa-graduation-cap"></i>
                </div>
                <h4>Training & Compliance</h4>
                <p>Continuing education and compliance training to advance your career.</p>
                <span className="int-status-badge warning">Earn Certifications</span>
                </div>
                <button className="btn small-cd" style={{marginTop: '20px', width: '100%'}}>Connect</button>
              </div>

              <div className="mp-service-category">
                <div>
                  <div className="mp-service-icon financial">
                  <i className="fa-solid fa-credit-card"></i>
                </div>
                <h4>Financial Services</h4>
                <p>Banking, factoring, and financial planning services for drivers.</p>
                <span className="int-status-badge warning">Multiple Partners</span>
                </div>
                <button className="btn small-cd" style={{marginTop: '20px', width: '100%'}}>Connect</button>
              </div>
            </div>
          </div>
        </section>
      </>
    );
  }

  if (isPostHire) {
    return <PostHireMarketplaceView />;
  }

  return (
    <>
      <header className="fp-header">
        <div className="fp-header-titles">
          <h2>Marketplace</h2>
          <p className="fp-subtitle">Your smart CDL staffing hub - connect with carriers and service providers</p>
          <button onClick={() => setIsPostHire(true)} className="btn small green-btn">Post Hire</button>
        </div>
      </header>
      
      <section className="fp-grid">
        {/* Hidden Status Alert */}
        <div className="card mp-alert-card">
          <div className="mp-alert-content">
            <i className="fa-solid fa-eye-slash mp-alert-icon"></i>
            <div className="mp-alert-text">
              <span className="mp-alert-title">You are currently hidden from carriers</span>
              <p className="mp-alert-subtitle">Toggle 'Available' to enter the hiring pool</p>
            </div>
            <button className="btn small-cd">Become Available</button>
          </div>
        </div>

        {/* GPS-Based Services */}
        <div className="card mp-gps-services-card">
          <div className="card-header">
            <h3>GPS-Based Services</h3>
          </div>
          
          <div className="mp-search-container">
            <div className="mp-search-input">
              <i className="fa-solid fa-search"></i>
              <input type="text" placeholder="Search services near you..." />
            </div>
          </div>

          <div className="mp-service-icons-grid">
            <div className="mp-service-icon-item">
              <div className="mp-service-icon fuel">
                <i className="fa-solid fa-gas-pump"></i>
              </div>
              <span>Fuel Stations</span>
            </div>
            <div className="mp-service-icon-item">
              <div className="mp-service-icon parking">
                <i className="fa-solid fa-parking"></i>
              </div>
              <span>Parking</span>
            </div>
            <div className="mp-service-icon-item">
              <div className="mp-service-icon repair">
                <i className="fa-solid fa-wrench"></i>
              </div>
              <span>Repair Shops</span>
            </div>
            <div className="mp-service-icon-item">
              <div className="mp-service-icon cdl">
                <i className="fa-solid fa-scale-balanced"></i>
              </div>
              <span>CDL Protection</span>
            </div>
            <div className="mp-service-icon-item">
              <div className="mp-service-icon training">
                <i className="fa-solid fa-graduation-cap"></i>
              </div>
              <span>Training</span>
            </div>
            <div className="mp-service-icon-item">
              <div className="mp-service-icon eld">
                <i className="fa-solid fa-mobile-screen"></i>
              </div>
              <span>ELD/Tech</span>
            </div>
          </div>
        </div>

        {/* AI Highlights */}
        <div className="card mp-highlights-card">
          <div className="card-header">
            <h3>AI Highlights</h3>
          </div>
          
          <div className="mp-highlight-item">
            <div className="mp-highlight-icon">
              <i className="fa-solid fa-gas-pump"></i>
            </div>
            <div className="mp-highlight-content">
              <h4>Fuel Discount Alert</h4>
              <p>XYZ Fuel Station - 10¢ off per gallon, 2.3 miles ahead</p>
            </div>
          </div>

          <div className="mp-highlight-item">
            <div className="mp-highlight-icon">
              <i className="fa-solid fa-exclamation-triangle"></i>
            </div>
            <div className="mp-highlight-content">
              <h4>CDL Renewal Reminder</h4>
              <p>Your CDL expires in 45 days - renew to stay eligible</p>
            </div>
          </div>
        </div>

        {/* Nearby Service Providers */}
        <div className="card mp-nearby-providers-card">
          <div className="card-header">
            <h3>Nearby Service Providers</h3>
            <div className="mp-filter-controls">
              <button className="btn small mp-filter-btn">
                <i className="fa-solid fa-filter"></i>
                Filters
              </button>
              <button className="btn small mp-favorites-btn">
                <i className="fa-solid fa-heart"></i>
                Favorites
              </button>
            </div>
          </div>

          <div className="mp-provider-list">
            <div className="mp-provider-item">
              <div className="mp-provider-icon shell">
                <i className="fa-solid fa-gas-pump"></i>
              </div>
              <div className="mp-provider-info">
                <h4>Shell Station</h4>
                <p>1.2 miles • Open 24/7</p>
                <p className="mp-provider-description">Premium fuel station with truck parking and amenities</p>
                <span className="mp-provider-offer">15¢ discount active</span>
              </div>
              <div className="mp-provider-actions">
                <span className="int-status-badge active">
                  Verified
                </span>
                <button className="btn small-cd">View Details</button>
              </div>
            </div>

            <div className="mp-provider-item">
              <div className="mp-provider-icon repair">
                <i className="fa-solid fa-wrench"></i>
              </div>
              <div className="mp-provider-info">
                <h4>Mike's Truck Repair</h4>
                <p>3.8 miles • Open until 8 PM</p>
                <p className="mp-provider-description">Full-service truck repair and maintenance facility</p>
                <span className="mp-provider-offer">Emergency service available</span>
              </div>
              <div className="mp-provider-actions">
                <span className="int-status-badge active">
                  Connected
                </span>
                <button className="btn small-cd">Contact Now</button>
              </div>
            </div>

            <div className="mp-provider-item">
              <div className="mp-provider-icon parking">
                <i className="fa-solid fa-parking"></i>
              </div>
              <div className="mp-provider-info">
                <h4>TruckStop Plaza</h4>
                <p>6.1 miles • Open 24/7</p>
                <p className="mp-provider-description">Secure parking with showers, food court, and WiFi</p>
                <span className="mp-provider-offer">42 spots available</span>
              </div>
              <div className="mp-provider-actions">
                <span className="int-status-badge active">
                  Verified
                </span>
                <button className="btn small-cd">Reserve Spot</button>
              </div>
            </div>

            <div className="mp-provider-item">
              <div className="mp-provider-icon legal">
                <i className="fa-solid fa-scale-balanced"></i>
              </div>
              <div className="mp-provider-info">
                <h4>TVC Legal Protection</h4>
                <p>61 miles • Nationwide</p>
                <p className="mp-provider-description">Comprehensive CDL protection and legal services</p>
                <span className="mp-provider-offer">Special offer this week</span>
              </div>
              <div className="mp-provider-actions">
                <span className="int-status-badge warning">20% Off</span>
                <button className="btn small-cd">Learn More</button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}