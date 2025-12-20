import React, { useState, useEffect } from 'react'
import '../../styles/carrier/Marketplace.css'
import '../../styles/carrier/ServicesPage.css'
import { useAuth } from '../../contexts/AuthContext'
import { API_URL } from '../../config'

// Minimum onboarding score required to access marketplace
const MARKETPLACE_THRESHOLD = 60

export default function Marketplace({ activeSection, setActiveSection }) {
  const { currentUser } = useAuth()
  const [activeTab, setActiveTab] = useState(activeSection || 'loads') // loads | drivers | services
  const [searchQuery, setSearchQuery] = useState('')
  const [equipmentType, setEquipmentType] = useState('')
  const [origin, setOrigin] = useState('')
  const [destination, setDestination] = useState('')
  const [dateRange, setDateRange] = useState('')
  const [distance, setDistance] = useState('')
  const [serviceTab, setServiceTab] = useState('all')
  const [showSidebar, setShowSidebar] = useState(true)
  const [isMobile, setIsMobile] = useState(false)

  // Marketplace gating state
  const [isMarketplaceReady, setIsMarketplaceReady] = useState(true)
  const [onboardingScore, setOnboardingScore] = useState(100)
  const [nextActions, setNextActions] = useState([])
  const [checkingAccess, setCheckingAccess] = useState(true)
  const [consentEligible, setConsentEligible] = useState(true)
  const [missingConsents, setMissingConsents] = useState([])
  const [gatingReason, setGatingReason] = useState('')

  // Check onboarding status AND consent eligibility to gate marketplace
  useEffect(() => {
    const checkMarketplaceAccess = async () => {
      if (!currentUser) {
        setCheckingAccess(false)
        return
      }

      try {
        const token = await currentUser.getIdToken()

        // Check onboarding score
        const onboardingResponse = await fetch(`${API_URL}/onboarding/coach-status`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        })

        let scoreOk = true
        if (onboardingResponse.ok) {
          const data = await onboardingResponse.json()
          const score = data.total_score || 0
          setOnboardingScore(score)
          scoreOk = score >= MARKETPLACE_THRESHOLD
          setNextActions(data.next_best_actions || [])
        }

        // Check consent eligibility
        const consentResponse = await fetch(`${API_URL}/consents/marketplace-eligibility`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        })

        let consentsOk = true
        if (consentResponse.ok) {
          const consentData = await consentResponse.json()
          consentsOk = consentData.eligible
          setConsentEligible(consentData.eligible)
          setMissingConsents(consentData.missing_consents || [])
        }

        // Determine gating reason
        if (!scoreOk && !consentsOk) {
          setGatingReason('both')
        } else if (!scoreOk) {
          setGatingReason('score')
        } else if (!consentsOk) {
          setGatingReason('consent')
        }

        setIsMarketplaceReady(scoreOk && consentsOk)
      } catch (error) {
        console.error('Error checking marketplace access:', error)
        // Allow access if check fails (graceful degradation)
        setIsMarketplaceReady(true)
      } finally {
        setCheckingAccess(false)
      }
    }

    checkMarketplaceAccess()
  }, [currentUser])

  // Sync activeTab when activeSection prop changes
  useEffect(() => {
    if (activeSection) {
      setActiveTab(activeSection)
    }
  }, [activeSection])

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth <= 1024) {
        setIsMobile(true)
        setShowSidebar(false)
      } else {
        setIsMobile(false)
        setShowSidebar(true)
      }
    }
    handleResize()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  // Show loading state while checking access
  if (checkingAccess) {
    return (
      <div className="marketplace-loading" style={{ padding: '40px', textAlign: 'center' }}>
        <i className="fa-solid fa-spinner fa-spin" style={{ fontSize: '2rem', color: '#3b82f6' }}></i>
        <p style={{ marginTop: '10px', color: '#64748b' }}>Checking marketplace access...</p>
      </div>
    )
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
            : `Complete your onboarding to unlock the marketplace. You need a score of at least ${MARKETPLACE_THRESHOLD}% to access loads, drivers, and services.`
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
            <button
              onClick={() => window.location.href = '/carrier/consent'}
              style={{
                marginTop: '15px',
                padding: '10px 20px',
                background: '#dc2626',
                color: '#fff',
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer',
                fontWeight: '600'
              }}
            >
              Sign Consent Forms
            </button>
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

          <div style={{
            background: '#f1f5f9',
            height: '8px',
            borderRadius: '4px',
            overflow: 'hidden'
          }}>
            <div style={{
              width: `${onboardingScore}%`,
              height: '100%',
              background: onboardingScore >= 50 ? '#f59e0b' : '#ef4444',
              borderRadius: '4px',
              transition: 'width 0.5s ease'
            }}></div>
          </div>
        </div>
        )}

        {nextActions.length > 0 && (
          <div style={{ textAlign: 'left', maxWidth: '400px', margin: '0 auto' }}>
            <h4 style={{ color: '#1e293b', marginBottom: '10px' }}>
              <i className="fa-solid fa-list-check" style={{ marginRight: '8px', color: '#3b82f6' }}></i>
              Complete These Steps:
            </h4>
            <ul style={{ listStyle: 'none', padding: 0 }}>
              {nextActions.slice(0, 3).map((action, index) => (
                <li key={index} style={{
                  padding: '10px 15px',
                  background: '#fff',
                  borderRadius: '8px',
                  marginBottom: '8px',
                  border: '1px solid #e2e8f0',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px'
                }}>
                  <span style={{
                    width: '24px',
                    height: '24px',
                    background: '#3b82f6',
                    color: '#fff',
                    borderRadius: '50%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '0.75rem',
                    fontWeight: 'bold'
                  }}>
                    {index + 1}
                  </span>
                  <span style={{ color: '#475569' }}>{action}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <button
          onClick={() => window.location.href = '/carrier-dashboard'}
          style={{
            marginTop: '30px',
            padding: '12px 24px',
            background: '#3b82f6',
            color: '#fff',
            border: 'none',
            borderRadius: '8px',
            fontWeight: '600',
            cursor: 'pointer',
            fontSize: '1rem'
          }}
        >
          <i className="fa-solid fa-arrow-left" style={{ marginRight: '8px' }}></i>
          Go to Dashboard
        </button>
      </div>
    )
  }

  // Mock drivers data
  const drivers = [
    {
      id: 1,
      name: 'Marcus Johnson',
      rating: 4.8,
      trips: 127,
      class: 'A - TX',
      location: 'Dallas, TX',
      experience: '5 years',
      endorsements: ['Hazmat', 'Tanker', 'Double/Triple'],
      safetyScore: 95,
      onTime: true,
      available: true,
      photo: 'https://randomuser.me/api/portraits/men/32.jpg',
      lastActivity: '2 days ago',
      equipmentTypes: ['CDL Valid', 'Med Card Active', 'MVR Clean']
    },
    {
      id: 2,
      name: 'Sarah Williams',
      rating: 4.4,
      trips: 89,
      class: 'A - CA',
      location: 'Los Angeles, CA',
      experience: '3 years',
      endorsements: ['Hazmat', 'Passenger'],
      safetyScore: 92,
      onTime: true,
      available: true,
      photo: 'https://randomuser.me/api/portraits/women/44.jpg',
      lastActivity: '1 day ago',
      equipmentTypes: ['CDL Valid', 'Med Card Active', 'MVR Clean']
    },
    {
      id: 3,
      name: 'Robert Martinez',
      rating: 4.7,
      trips: 203,
      class: 'A - FL',
      location: 'Miami, FL',
      experience: '7 years',
      endorsements: ['Tanker', 'Double/Triple'],
      safetyScore: 98,
      onTime: false,
      available: true,
      photo: 'https://randomuser.me/api/portraits/men/67.jpg',
      lastActivity: '5 hours ago',
      equipmentTypes: ['CDL Valid', 'Med Card Active', 'MVR Clean']
    },
    {
      id: 4,
      name: 'Jennifer Davis',
      rating: 5.0,
      trips: 45,
      class: 'A - NY',
      location: 'Buffalo, NY',
      experience: '2 years',
      endorsements: ['Hazmat', 'Tanker', 'Double/Triple', 'Passenger'],
      safetyScore: 100,
      onTime: true,
      available: true,
      photo: 'https://randomuser.me/api/portraits/women/68.jpg',
      lastActivity: '3 hours ago',
      equipmentTypes: ['CDL Valid', 'Med Card Active', 'MVR Clean']
    },
    {
      id: 5,
      name: 'David Thompson',
      rating: 4.6,
      trips: 156,
      class: 'B - IL',
      location: 'Chicago, IL',
      experience: '4 years',
      endorsements: ['None'],
      safetyScore: 88,
      onTime: false,
      available: false,
      photo: 'https://randomuser.me/api/portraits/men/71.jpg',
      lastActivity: '2 hours ago',
      equipmentTypes: ['CDL Expiring', 'Med Card Active', 'MVR Clear']
    }
  ]

  // Mock loads data
  const loads = [
    {
      id: 1,
      origin: 'Chicago, IL',
      destination: 'Dallas, TX',
      pickupDate: 'Dec 10, 2024',
      deliveryDate: 'Delivery: Dec 12, 2024',
      rate: '$2,850',
      perMile: '$1.75/mile',
      status: 'Active',
      postedTime: 'Posted 1h ago',
      carrier: 'Sky Jet',
      distance: '925 miles',
      urgency: 'normal'
    },
    {
      id: 2,
      origin: 'Atlanta, GA',
      destination: 'Miami, FL',
      pickupDate: 'Dec 16, 2024',
      deliveryDate: 'Delivery: Dec 18, 2024',
      rate: '$1,950',
      perMile: '$3.12/mile',
      status: 'Pending',
      postedTime: 'Posted 4h ago',
      carrier: 'Reefer',
      distance: '662 miles',
      urgency: 'normal'
    },
    {
      id: 3,
      origin: 'Los Angeles, CA',
      destination: 'Phoenix, AZ',
      pickupDate: 'Dec 4, 2024',
      deliveryDate: 'Delivery: Dec 12, 2024',
      rate: '$1,200',
      perMile: '$3.18/mile',
      status: 'Urgent',
      postedTime: 'Posted 8h ago',
      carrier: 'Flatbed',
      distance: '372 miles',
      urgency: 'urgent'
    }
  ]

  return (
    <div className="marketplace">
      <header className="marketplace-header">
        <div className="marketplace-header-content">
          <h1>Marketplace</h1>
          <p className="marketplace-subtitle">Find loads, hire drivers, and connect with service providers</p>
        </div>
      </header>

      {/* Tabs Navigation */}
      <div className="marketplace-nav">
        <div className="marketplace-tabs">
          <button
            className={`marketplace-tab ${activeTab === 'loads' ? 'active' : ''}`}
            onClick={() => setActiveTab('loads')}
          >
            Loads
          </button>
          <button
            className={`marketplace-tab ${activeTab === 'drivers' ? 'active' : ''}`}
            onClick={() => setActiveTab('drivers')}
          >
            Drivers
          </button>
          <button
            className={`marketplace-tab ${activeTab === 'services' ? 'active' : ''}`}
            onClick={() => setActiveTab('services')}
          >
            Services
          </button>
        </div>
      </div>

      {/* Search and Filters - Only show on Loads tab */}
      {activeTab === 'loads' && (
        <div className="marketplace-controls">
          <div className="marketplace-inner">
            <div className="search-section">
          <div className="search-input-container">
            <i className="fa-solid fa-search search-icon" />
            <input
              type="text"
              className="marketplace-search"
              placeholder="Search loads, drivers, or services..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <button className="btn small-cd">
              <i className="fa-solid fa-search" />
              Search
            </button>
          </div>
        </div>

        <div className="filters-section">
          <select
            className="marketplace-filter-select"
            value={equipmentType}
            onChange={(e) => setEquipmentType(e.target.value)}
          >
            <option value="">Equipment Type</option>
            <option value="dry-van">Dry Van</option>
            <option value="reefer">Reefer</option>
            <option value="flatbed">Flatbed</option>
          </select>

          <input
            type="text"
            className="marketplace-filter-input"
            placeholder="Origin"
            value={origin}
            onChange={(e) => setOrigin(e.target.value)}
          />

          <input
            type="text"
            className="marketplace-filter-input"
            placeholder="Destination"
            value={destination}
            onChange={(e) => setDestination(e.target.value)}
          />

          <input
            type="text"
            className="marketplace-filter-input"
            placeholder="mm/dd/yyyy"
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value)}
          />

          <select
            className="marketplace-filter-select"
            value={distance}
            onChange={(e) => setDistance(e.target.value)}
          >
            <option value="">Distance</option>
            <option value="0-100">0-100 miles</option>
            <option value="100-500">100-500 miles</option>
            <option value="500+">500+ miles</option>
          </select>
            </div>
          </div>
        </div>
      )}

      {/* Loads Content */}
      {activeTab === 'loads' && (
        <div className="loads-grid">
          {loads.map(load => (
            <div key={load.id} className={`load-card ${load.urgency === 'urgent' ? 'urgent' : ''}`}>
              <div className="load-card-header">
                <div className="route-info">
                  <div className="route-cities">
                    <span className="origin">{load.origin}</span>
                    <i className="fa-solid fa-arrow-right route-arrow" />
                    <span className="destination">{load.destination}</span>
                  </div>
                  <div className="route-meta">
                    <span className="pickup-date">{load.pickupDate}</span>
                    <span className="delivery-date">{load.deliveryDate}</span>
                  </div>
                </div>
                <div className={`status-badge status-${load.status.toLowerCase()}`}>
                  {load.status}
                </div>
              </div>

              <div className="load-details">
                <div className="load-rate">
                  <div className="rate-amount">{load.rate}</div>
                  <div className="rate-per-mile">{load.perMile}</div>
                </div>
                <div className="load-meta">
                  <div className="carrier-info">
                    <i className="fa-solid fa-truck" />
                    {load.carrier}
                  </div>
                  <div className="distance-info">
                    <i className="fa-solid fa-route" />
                    {load.distance}
                  </div>
                </div>
              </div>

              <div className="load-actions">
                <button className="btn small-cd" style={{width: '100%'}}>Bid/Counter</button>
                <button className="btn small ghost-cd"style={{width: '100%'}}>Accept</button>
              </div>

              <div className="posted-time">{load.postedTime}</div>
            </div>
          ))}
        </div>
      )}

      {/* Drivers Content */}
      {activeTab === 'drivers' && (
        <div className="drivers-content">

          <div className="marketplace-drivers-filters">
            <div className="marketplace-filters-top-row">
              <div className="marketplace-filter-group">
                <label className="marketplace-filter-label">Location & Radius</label>
                <div className="marketplace-location-inputs">
                  <input 
                    className="marketplace-filter-input marketplace-location-input" 
                    placeholder="City, State or ZIP"
                    value=""
                    onChange={() => {}}
                  />
                  <select className="marketplace-filter-select marketplace-radius-select">
                    <option>25 miles</option>
                    <option>50 miles</option>
                    <option>100 miles</option>
                  </select>
                </div>
              </div>
              
              <div className="marketplace-filter-group">
                <label className="marketplace-filter-label">CDL Class</label>
                <select className="marketplace-filter-select">
                  <option>All Classes</option>
                  <option>CDL Class A</option>
                  <option>CDL Class B</option>
                  <option>CDL Class C</option>
                </select>
              </div>
              
              <div className="marketplace-filter-group">
                <label className="marketplace-filter-label">Status</label>
                <select className="marketplace-filter-select">
                  <option>All Status</option>
                  <option>Available</option>
                  <option>Assigned</option>
                  <option>Off Duty</option>
                </select>
              </div>
              
              <div className="marketplace-filter-group">
                <label className="marketplace-filter-label">Compliance</label>
                <select className="marketplace-filter-select">
                  <option>All</option>
                  <option>Compliant</option>
                  <option>Non-Compliant</option>
                </select>
              </div>
            </div>
            
            <div className="marketplace-endorsements-row">
              <span className="marketplace-filter-label">Endorsements</span>
              <div className="marketplace-endorsement-chips">
                <button className="marketplace-endorsement-chip">Hazmat</button>
                <button className="marketplace-endorsement-chip">Tanker</button>
                <button className="marketplace-endorsement-chip marketplace-selected">Double/Triple</button>
                <button className="marketplace-endorsement-chip">Passenger</button>
                <button className="marketplace-endorsement-chip">School Bus</button>
              </div>
            </div>
          </div>
          
          <div className="marketplace-drivers-results-bar">
            <div className="marketplace-results-count">1,247 drivers found</div>
            <div className="marketplace-results-controls">
              <div className="marketplace-sort-group">
                <label>Sort by:</label>
                <select className="marketplace-sort-select">
                  <option>Relevance</option>
                  <option>Rating</option>
                  <option>Experience</option>
                  <option>Location</option>
                </select>
              </div>
            </div>
          </div>

          <div className="drivers-actions">
          <button className="btn small ghost-cd">
            <i className="fa-solid fa-download"></i> Export
          </button>
          <button className="btn small-cd">
            <i className="fa-solid fa-plus"></i> Post Driver Request
          </button>
            </div>

          <div className="marketplace-drivers-list">
            {drivers.map(driver => (
              <div key={driver.id} className="marketplace-driver-card">
                <div className="marketplace-driver-header">
                  <div className="marketplace-driver-left">
                    <div className="marketplace-driver-avatar">
                      <img src={driver.photo} alt={driver.name} />
                    </div>
                    <div className="marketplace-driver-info">
                      <div className="marketplace-driver-name-row">
                        <h3 className="marketplace-driver-name">{driver.name}</h3>
                        <div className="marketplace-driver-rating">
                          <i className="fa-solid fa-star" />
                          <span>{driver.rating}</span>
                          <span className="marketplace-trips-count">• {driver.trips} trips</span>
                        </div>
                      </div>
                      
                      <div className="marketplace-driver-details">
                        <div className="marketplace-detail-item">
                          <span className="marketplace-detail-label">CDL INFO</span>
                          <span className="marketplace-detail-value">Class {driver.class}</span>
                          <span className="marketplace-detail-sub">Exp: 03/2025</span>
                        </div>
                        
                        <div className="marketplace-detail-item">
                          <span className="marketplace-detail-label">LOCATION</span>
                          <span className="marketplace-detail-value">{driver.location}</span>
                          <span className="marketplace-detail-sub">{driver.lastActivity}</span>
                        </div>
                        
                        <div className="marketplace-detail-item">
                          <span className="marketplace-detail-label">STATUS</span>
                          <span className={`marketplace-detail-value marketplace-status-${driver.available ? 'available' : 'unavailable'}`}>
                            <i className="fa-solid fa-circle" />
                            {driver.available ? 'Available' : 'Not Available'}
                          </span>
                        </div>
                        
                        <div className="marketplace-detail-item">
                          <span className="marketplace-detail-label">AI SAFETY SCORE</span>
                          <span className="marketplace-detail-value marketplace-safety-score">
                            {driver.safetyScore}/100
                          </span>
                        </div>
                      </div>

                      <div className="marketplace-driver-tags">
                        <div className="marketplace-endorsements">
                          <span className="marketplace-tags-label">Endorsements:</span>
                          {driver.endorsements.map((endorsement, index) => (
                            <span key={index} className="marketplace-endorsement-tag">{endorsement}</span>
                          ))}
                        </div>
                        
                        <div className="marketplace-equipment-status">
                          {driver.equipmentTypes.map((equipment, index) => (
                            <span key={index} className={`marketplace-equipment-tag ${equipment.includes('Valid') || equipment.includes('Active') || equipment.includes('Clean') ? 'valid' : equipment.includes('Expiring') ? 'warning' : 'invalid'}`}>
                              <i className={`fa-solid ${equipment.includes('Valid') || equipment.includes('Active') || equipment.includes('Clean') ? 'fa-check-circle' : equipment.includes('Expiring') ? 'fa-exclamation-triangle' : 'fa-times-circle'}`} />
                              {equipment}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  <div className="marketplace-driver-actions">
                    <button className={`marketplace-btn-hire ${driver.available ? 'available' : 'unavailable'}`}>
                      <i className="fa-solid fa-plus" />
                      Hire Driver
                    </button>
                    <div className="marketplace-driver-menu">
                      <button className="marketplace-menu-btn" title="View Details">
                        <i className="fa-solid fa-file-text" />
                      </button>
                      <button className="marketplace-menu-btn" title="Message">
                        <i className="fa-solid fa-message" />
                      </button>
                      <button className="marketplace-menu-btn" title="Favorite">
                        <i className="fa-regular fa-heart" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="drivers-pagination">
            <span>Showing 1-5 of 1,247 drivers</span>
            <div className="pagination">
              <button aria-label="Previous page">&lt;</button>
              <button className="active" aria-current="page">1</button>
              <button>2</button>
              <button>3</button>
              <span>...</span>
              <button>25</button>
              <button aria-label="Next page">&gt;</button>
            </div>
          </div>
        </div>
      )}

      {/* Services Content */}
      {activeTab === 'services' && (
        <div className="services-page">
          {/* Service Tabs */}
          <div className="services-header">
            <div className="services-tabs">
              <button className={`service-tab ${serviceTab === 'all' ? 'active' : ''}`} onClick={() => setServiceTab('all')}>
                <i className="fa-solid fa-th"></i> All Services
              </button>
              <button className={`service-tab ${serviceTab === 'fuel' ? 'active' : ''}`} onClick={() => setServiceTab('fuel')}>
                <i className="fa-solid fa-gas-pump"></i> Fuel
              </button>
              <button className={`service-tab ${serviceTab === 'parking' ? 'active' : ''}`} onClick={() => setServiceTab('parking')}>
                <i className="fa-solid fa-square-parking"></i> Parking
              </button>
              <button className={`service-tab ${serviceTab === 'parts' ? 'active' : ''}`} onClick={() => setServiceTab('parts')}>
                <i className="fa-solid fa-cog"></i> Parts
              </button>
              <button className={`service-tab ${serviceTab === 'maintenance' ? 'active' : ''}`} onClick={() => setServiceTab('maintenance')}>
                <i className="fa-solid fa-wrench"></i> Maintenance
              </button>
              <button className={`service-tab ${serviceTab === 'factoring' ? 'active' : ''}`} onClick={() => setServiceTab('factoring')}>
                <i className="fa-solid fa-dollar-sign"></i> Factoring
              </button>
              <button className={`service-tab ${serviceTab === 'insurance' ? 'active' : ''}`} onClick={() => setServiceTab('insurance')}>
                <i className="fa-solid fa-shield-alt"></i> Insurance
              </button>
              <button className={`service-tab ${serviceTab === 'food' ? 'active' : ''}`} onClick={() => setServiceTab('food')}>
                <i className="fa-solid fa-utensils"></i> Food
              </button>
              <button className={`service-tab ${serviceTab === 'favourites' ? 'active' : ''}`} onClick={() => setServiceTab('food')}>
                <i className="fa-solid fa-heart"></i> Favourites
              </button>
              <button className={`service-tab ${serviceTab === 'history' ? 'active' : ''}`} onClick={() => setServiceTab('food')}>
                <i className="fa-solid fa-history"></i> History
              </button>
            </div>
          </div>
          <div className="services-main">
            {/* Services Grid and Info */}
            <div className="services-left">
              <div className="services-info">
                <span>Showing 247 service providers</span>
                <div className="sort-controls">
                  <label htmlFor="services-sort-select">Sort by:</label>
                  <select id="services-sort-select" className="marketplace-filter-select" style={{ minWidth: 120 }}>
                    <option value="relevance">Relevance</option>
                    <option value="rating">Rating</option>
                    <option value="reviews">Reviews</option>
                    <option value="distance">Distance</option>
                  </select>
                  {isMobile && (
                    <button
                      className="btn-filter-toggle"
                      aria-label="Show Filters"
                      onClick={() => setShowSidebar((v) => !v)}
                      style={{ marginLeft: 8 }}
                    >
                      <i className="fa-solid fa-filter"></i>
                    </button>
                  )}
                </div>
              </div>

              {/* Service Cards Grid */}
              <div className="services-grid">
                {/* Pilot Flying J Card */}
                <div className="service-card">
                  <div className="card-header">
                    <div className="provider-info">
                      <div className="provider-logo red">PJ</div>
                      <div>
                        <h3>Pilot Flying J</h3>
                        <p>Fuel Network</p>
                      </div>
                    </div>
                    <i className="fa-regular fa-heart"></i>
                  </div>
                  <div className="service-features">
                    <span className="feature nationwide"><i class="fa-solid fa-location-dot"></i> Nationwide Coverage</span>
                    <div className="rating">
                      <span><i className="fa-solid fa-star" style={{color:'#fbbf24'}}></i> 4.8</span>
                      <span>(1,247 reviews)</span>
                    </div>
                    <span className="discount"><i class="fa-solid fa-tag"></i> 12¢ off per gallon</span>
                    <span className="cashback">Plus 2% cash back on purchases</span>
                  </div>
                  <button className="btn small-cd" style={{width:'100%'}}>Request Quote</button>
                </div>

                {/* TruckPro Service Card */}
                <div className="service-card">
                  <div className="card-header">
                    <div className="provider-info">
                      <div className="provider-logo blue">TP</div>
                      <div>
                        <h3>TruckPro Service</h3>
                        <p>Maintenance & Repair</p>
                      </div>
                    </div>
                    <i className="fa-regular fa-heart"></i>
                  </div>
                  <div className="service-features">
                    <span className="location"><i class="fa-solid fa-location-dot"></i> Dallas, TX - 50 mile radius</span>
                    <div className="rating">
                      <span><i className="fa-solid fa-star" style={{color:'#fbbf24'}}></i> 4.9</span>
                      <span>(456 reviews)</span>
                    </div>
                    <span className="cd-emergency"><i class="fa-solid fa-clock"></i> 24/7 Emergency Service</span>
                    <span className="mobile">Mobile repair units available</span>
                  </div>
                  <button className="btn small-cd" style={{width:'100%'}}>Request Quote</button>
                </div>

                {/* Progressive Commercial Card */}
                <div className="service-card">
                  <div className="card-header">
                    <div className="provider-info">
                      <div className="provider-logo">PC</div>
                      <div>
                        <h3>Progressive Commercial</h3>
                        <p>Commercial Insurance</p>
                      </div>
                    </div>
                    <i className="fa-solid fa-heart red"></i>
                  </div>
                  <div className="service-features">
                    <span className="coverage"><i class="fa-solid fa-location-dot"></i> All 50 States</span>
                    <div className="rating">
                      <span> 4.6</span>
                      <span>(2,134 reviews)</span>
                    </div>
                    <span className="savings"><i class="fa-solid fa-percent"></i> Save up to 25%</span>
                    <span className="discount">Multi-policy discount available</span>
                  </div>
                  <button className="btn small-cd" style={{width:'100%'}}>Get Quote</button>
                </div>

                {/* RTS Financial Card */}
                <div className="service-card">
                  <div className="card-header">
                    <div className="provider-info">
                      <div className="provider-logo dollar">$</div>
                      <div>
                        <h3>RTS Financial</h3>
                        <p>Invoice Factoring</p>
                      </div>
                    </div>
                    <i className="fa-regular fa-heart"></i>
                  </div>
                  <div className="service-features">
                    <span className="service-type"><i class="fa-solid fa-location-dot"></i> Nationwide Service</span>
                    <div className="rating">
                      <span><i className="fa-solid fa-star" style={{color:'#fbbf24'}}></i> 4.7</span>
                      <span>(892 reviews)</span>
                    </div>
                    <span className="funding"><i class="fa-solid fa-bolt"></i> Same-day funding</span>
                    <span className="rate">Rates starting at 1.5%</span>
                  </div>
                  <button className="btn small-cd" style={{width:'100%'}}>Apply Now</button>
                </div>

                {/* SecurePark Network Card */}
                <div className="service-card">
                  <div className="card-header">
                    <div className="provider-info">
                      <div className="provider-logo purple">SP</div>
                      <div>
                        <h3>SecurePark Network</h3>
                        <p>Truck Parking</p>
                      </div>
                    </div>
                    <i className="fa-regular fa-heart"></i>
                  </div>
                  <div className="service-features">
                    <span className="locations"><i class="fa-solid fa-location-dot"></i> 150+ Locations</span>
                    <div className="rating">
                      <span><i className="fa-solid fa-star" style={{color:'#fbbf24'}}></i> 4.5</span>
                      <span>(678 reviews)</span>
                    </div>
                    <span className="security"><i class="fa-solid fa-shield-alt"></i> Secure & Monitored</span>
                    <span className="available">24/7 security & reservations</span>
                  </div>
                  <button className="btn small-cd" style={{width:'100%'}}>Reserve Spot</button>
                </div>

                {/* FleetParts Direct Card */}
                <div className="service-card">
                  <div className="card-header">
                    <div className="provider-info">
                      <div className="provider-logo orange">FP</div>
                      <div>
                        <h3>FleetParts Direct</h3>
                        <p>Truck Parts & Components</p>
                      </div>
                    </div>
                    <i className="fa-regular fa-heart"></i>
                  </div>
                  <div className="service-features">
                    <span className="shipping"><i class="fa-solid fa-location-dot"></i> Same-day shipping</span>
                    <div className="rating">
                      <span><i className="fa-solid fa-star" style={{color:'#fbbf24'}}></i> 4.8</span>
                      <span>(1,523 reviews)</span>
                    </div>
                    <span className="free-shipping"><i class="fa-solid fa-truck"></i> Free shipping $200+</span>
                    <span className="oem">OEM & aftermarket parts</span>
                  </div>
                  <button className="btn small-cd" style={{width:'100%'}}>Browse Parts</button>
                </div>
              </div>

              <div className="load-more">
                <button className="btn small ghost-cd">Load More Providers</button>
              </div>
            </div>

            {/* Filters Sidebar */}
            {(showSidebar || !isMobile) && (
              <div className={`services-sidebar${showSidebar && isMobile ? ' active' : ''}`}>
                {isMobile && (
                  <button
                    className="btn-filter-close"
                    aria-label="Close Filters"
                    onClick={() => setShowSidebar(false)}
                    style={{ float: 'right', marginBottom: 12 }}
                  >
                    <i className="fa-solid fa-times"></i>
                  </button>
                )}
                <h3>Filters</h3>
                
                <div className="filter-section">
                  <h4>Location</h4>
                  <input type="text" placeholder="Enter city or ZIP code" className="location-input" />
                  <div className="radius-selector">
                    <label>Radius</label>
                    <select>
                      <option>25 miles</option>
                      <option>50 miles</option>
                      <option>100 miles</option>
                    </select>
                  </div>
                </div>

                <div className="filter-section">
                  <h4>Minimum Rating</h4>
                  <div className="rating-filters">
                    <label><input type="radio" name="rating" />
                      <i className="fa-solid fa-star" style={{color:'#fbbf24'}}></i>
                      <i className="fa-solid fa-star" style={{color:'#fbbf24'}}></i>
                      <i className="fa-solid fa-star" style={{color:'#fbbf24'}}></i>
                      <i className="fa-solid fa-star" style={{color:'#fbbf24'}}></i>
                      <i className="fa-solid fa-star" style={{color:'#fbbf24'}}></i>
                      5 stars
                    </label>
                    <label><input type="radio" name="rating" />
                      <i className="fa-solid fa-star" style={{color:'#fbbf24'}}></i>
                      <i className="fa-solid fa-star" style={{color:'#fbbf24'}}></i>
                      <i className="fa-solid fa-star" style={{color:'#fbbf24'}}></i>
                      <i className="fa-solid fa-star" style={{color:'#fbbf24'}}></i>
                      4+ stars
                    </label>
                    <label><input type="radio" name="rating" />
                      <i className="fa-solid fa-star" style={{color:'#fbbf24'}}></i>
                      <i className="fa-solid fa-star" style={{color:'#fbbf24'}}></i>
                      <i className="fa-solid fa-star" style={{color:'#fbbf24'}}></i>
                      3+ stars
                    </label>
                  </div>
                </div>

                <div className="filter-section">
                  <h4>Service Features</h4>
                  <div className="feature-checkboxes">
                    <label><input type="checkbox" /> 24/7 Service</label>
                    <label><input type="checkbox" checked /> Mobile Service</label>
                    <label><input type="checkbox" checked /> Same-day Service</label>
                    <label><input type="checkbox" /> Warranty Included</label>
                  </div>
                </div>

                <div className="filter-section">
                  <h4>Price Range</h4>
                  <div className="price-filters">
                    <label><input type="radio" name="price" /> $ - Budget</label>
                    <label><input type="radio" name="price" checked /> $$ - Moderate</label>
                    <label><input type="radio" name="price" /> $$$ - Premium</label>
                  </div>
                </div>

                <div className="filter-actions">
                  <button className="btn small-cd">Apply Filters</button>
                  <button className="btn small ghost-cd">Clear All Filters</button>
                </div>

                <div className="quick-actions">
                  <h4>Quick Actions</h4>
                  <button className="btn small ghost-cd" style={{ width: '100%' }}>
                    <i className="fa-solid fa-add"></i>
                    Request Service
                  </button>
                  <button className="btn small ghost-cd" style={{ width: '100%' }}>
                    <i className="fa-solid fa-exclamation-circle"></i>
                    Request Emergency Service
                  </button>
                  <button className="btn small ghost-cd" style={{ width: '100%' }}>
                    <i className="fa-solid fa-calendar"></i>
                    Schedule Maintenance
                  </button>
                  <button className="btn small ghost-cd" style={{ width: '100%' }}>
                    <i className="fa-solid fa-shield"></i>
                    Get Insurance Quote
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}