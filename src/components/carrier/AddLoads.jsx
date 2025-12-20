import React, { useState } from 'react';
import '../../styles/carrier/AddLoads.css';

export default function AddLoads({ onClose }) {
  const [step, setStep] = useState(1);
  const [chargeName, setChargeName] = useState('');
  const [chargeAmount, setChargeAmount] = useState('');
  const [formData, setFormData] = useState({
    // Step 1: Route & Equipment
    origin: '',
    destination: '',
    pickupDate: '',
    deliveryDate: '',
    equipmentType: 'Dry Van',
    loadType: 'FTL',
    weight: '',
    palletCount: '',
    
    // Step 2: Price & Details
    pricingModel: 'flatRate',
    linehaul: '',
    fuelSurcharge: '',
    advancedCharges: [],
    carrierRequirements: [],
    driverInstructions: '',
    
    // Step 3: Visibility & Preferences
    visibility: 'public',
    autoMatch: true,
    instantBooking: false,
    postToLoadBoards: true,
    bestTimeToPost: '',
    rateAdjustment: '',
    highMatchCarriers: true,
  });

  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleLoadTypeSelect = (type) => {
    setFormData(prev => ({ ...prev, loadType: type }));
  };

  const handleVisibilitySelect = (option) => {
    setFormData(prev => ({ ...prev, visibility: option }));
  };

  const toggleRequirement = (req) => {
    setFormData(prev => ({
      ...prev,
      carrierRequirements: prev.carrierRequirements.includes(req)
        ? prev.carrierRequirements.filter(r => r !== req)
        : [...prev.carrierRequirements, req]
    }));
  };

  const handleAddCharge = () => {
    if (chargeName && chargeAmount) {
      setFormData(prev => ({
        ...prev,
        advancedCharges: [...prev.advancedCharges, { name: chargeName, amount: chargeAmount }]
      }));
      setChargeName('');
      setChargeAmount('');
    }
  };

  const handleRemoveCharge = (index) => {
    setFormData(prev => ({
      ...prev,
      advancedCharges: prev.advancedCharges.filter((_, i) => i !== index)
    }));
  };

  const handleNext = () => {
    if (step < 3) setStep(step + 1);
  };

  const handleBack = () => {
    if (step > 1) setStep(step - 1);
  };

  const handlePostLoad = () => {
    console.log('Load posted with data:', formData);
    onClose();
  };

  return (
    <div className="add-loads-overlay" onClick={onClose}>
      <div className="add-loads-modal" onClick={(e) => e.stopPropagation()}>
        <button className="add-loads-close" aria-label="Close" onClick={onClose}>×</button>
        
        <div className="add-loads-page">
          <div className="add-loads-container">
            {/* STEP 1: Route & Equipment */}
            {step === 1 && (
              <div className="add-loads-step">
                <div className="step-header">
                  <h2>Create New Load</h2>
                  <p className="step-subtitle">Step 1 of 3 – Route & Equipment</p>
                  <p className="step-description">Load ID generated after Step 1</p>
                </div>

                <div className="form-section">
                  <h4 className="section-title">Route Information</h4>
                  <p className="section-desc">Where the shipment is picked up and delivered</p>
                  
                  <div className="grid-2">
                    <div className="form-group">
                      <label>Origin *</label>
                      <input
                        type="text"
                        name="origin"
                        placeholder="City, State, Zip or Facility"
                        value={formData.origin}
                        onChange={handleInputChange}
                      />
                    </div>
                    <div className="form-group">
                      <label>Destination *</label>
                      <input
                        type="text"
                        name="destination"
                        placeholder="City, State, Zip or Facility"
                        value={formData.destination}
                        onChange={handleInputChange}
                      />
                    </div>
                  </div>

                  <div className="grid-2" style={{ marginTop: '10px' }}>
                    <div className="form-group">
                      <label>Pickup Date *</label>
                      <input
                        type="date"
                        name="pickupDate"
                        value={formData.pickupDate}
                        onChange={handleInputChange}
                      />
                    </div>
                    <div className="form-group">
                      <label>Delivery Date</label>
                      <input
                        type="date"
                        name="deliveryDate"
                        value={formData.deliveryDate}
                        onChange={handleInputChange}
                      />
                    </div>
                  </div>
                </div>

                <div className="form-section">
                  <h4 className="section-title">Equipment & Load Type</h4>
                  <p className="section-desc">Define how this load should be handled</p>
                  
                  <div className="grid-2">
                    <div className="form-group">
                      <label>Equipment Type *</label>
                      <select
                        name="equipmentType"
                        value={formData.equipmentType}
                        onChange={handleInputChange}
                      >
                        <option>Dry Van</option>
                        <option>Reefer</option>
                        <option>Flatbed</option>
                        <option>Stepdeck</option>
                        <option>Power Only</option>
                      </select>
                    </div>
                    <div className="form-group">
                      <label>Weight (lbs) *</label>
                      <input
                        type="text"
                        name="weight"
                        placeholder="e.g. 42,000"
                        value={formData.weight}
                        onChange={handleInputChange}
                      />
                    </div>
                  </div>

                  <div className="form-group" style={{ marginTop: '10px' }}>
                    <label>Load Type </label>
                    <div className="load-type-selector">
                      <button
                        className={`load-type-btn ${formData.loadType === 'FTL' ? 'active' : ''}`}
                        onClick={() => handleLoadTypeSelect('FTL')}
                      >
                        <div className="btn-icon">📦</div>
                        <div className="btn-label">FTL</div>
                        <div className="btn-desc">Dedicated trailer, no sharing</div>
                      </button>
                      <button
                        className={`load-type-btn ${formData.loadType === 'LTL' ? 'active' : ''}`}
                        onClick={() => handleLoadTypeSelect('LTL')}
                      >
                        <div className="btn-icon">📫</div>
                        <div className="btn-label">LTL</div>
                        <div className="btn-desc">Shared space, multiple shippers</div>
                      </button>
                      <button
                        className={`load-type-btn ${formData.loadType === 'Multi-Stop' ? 'active' : ''}`}
                        onClick={() => handleLoadTypeSelect('Multi-Stop')}
                      >
                        <div className="btn-icon">🏢</div>
                        <div className="btn-label">Multi-Stop</div>
                        <div className="btn-desc">Multiple pickups or deliveries</div>
                      </button>
                    </div>
                  </div>

                  <div className="form-group" style={{ marginTop: '10px' }}>
                    <label>Pallet Count</label>
                    <input
                      type="text"
                      name="palletCount"
                      placeholder="Optional"
                      value={formData.palletCount}
                      onChange={handleInputChange}
                    />
                  </div>

                  <div className="info-box">
                    <p><strong>Estimated Distance: —</strong> miles</p>
                    <p><strong>Estimated Transit Time: —</strong> hours / days</p>
                  </div>
                </div>

                <div className="add-route-box">
                  <button className="add-route-btn">+ Add Additional Route & Equipment</button>
                  <p className="add-route-desc">For multi-stop or complex shipments</p>
                </div>

                <div className="step-actions">
                  <button className="btn small ghost-cd" onClick={onClose}>Cancel</button>
                  <button className="btn small-cd" onClick={handleNext}>Next → Price & Details</button>
                </div>
              </div>
            )}

            {/* STEP 2: Price & Details */}
            {step === 2 && (
              <div className="add-loads-step">
                <div className="step-header">
                  <h2>Create New Load</h2>
                  <p className="step-subtitle">Step 2 of 3 – Price & Details</p>
                  <p className="step-description">Load ID: FP-2504-611-00123</p>
                </div>

                <div className="form-section">
                  <h4 className="section-title">Pricing</h4>
                  <p className="section-desc">Define how carriers are paid. Clear pricing improves booking speed and quality.</p>
                  
                  <div className="pricing-selector">
                    <button
                      className={`pricing-btn ${formData.pricingModel === 'flatRate' ? 'active' : ''}`}
                      onClick={() => setFormData(prev => ({ ...prev, pricingModel: 'flatRate' }))}
                    >
                      <div className="pricing-icon">💚</div>
                      <div className="pricing-label">Flat Rate</div>
                      <div className="pricing-desc">One total price for the load</div>
                    </button>
                    <button
                      className={`pricing-btn ${formData.pricingModel === 'perMile' ? 'active' : ''}`}
                      onClick={() => setFormData(prev => ({ ...prev, pricingModel: 'perMile' }))}
                    >
                      <div className="pricing-icon">📍</div>
                      <div className="pricing-label">Per Mile</div>
                      <div className="pricing-desc">Calculated from total distance</div>
                    </button>
                    <button
                      className={`pricing-btn ${formData.pricingModel === 'hourly' ? 'active' : ''}`}
                      onClick={() => setFormData(prev => ({ ...prev, pricingModel: 'hourly' }))}
                    >
                      <div className="pricing-icon">⏰</div>
                      <div className="pricing-label">Hourly</div>
                      <div className="pricing-desc">Best for cross-timezones loads</div>
                    </button>
                  </div>
                </div>

                <div className="form-section">
                  <div className="grid-2">
                    <div className="form-group">
                      <label>Linehaul Rate ($) *</label>
                      <input
                        type="text"
                        name="linehaul"
                        placeholder="e.g. 2,750"
                        value={formData.linehaul}
                        onChange={handleInputChange}
                      />
                    </div>
                    <div className="form-group">
                      <label>Fuel Surcharge ($)</label>
                      <input
                        type="text"
                        name="fuelSurcharge"
                        placeholder="Optional"
                        value={formData.fuelSurcharge}
                        onChange={handleInputChange}
                      />
                    </div>
                  </div>

                  <div className="form-section" >
                    <h4 className="section-title" style={{marginTop: '20px'}}>Advanced Pricing</h4>
                    <p className="section-desc">Add bonuses, detention, penalties</p>
                    
                    <div className="advanced-pricing-form">
                      <div className="advanced-pricing-inputs">
                        <input
                          type="text"
                          placeholder="Charge name (e.g. Detention)"
                          value={chargeName}
                          onChange={(e) => setChargeName(e.target.value)}
                          className="charge-name-input"
                        />
                        <input
                          type="text"
                          placeholder="$ Amount"
                          value={chargeAmount}
                          onChange={(e) => setChargeAmount(e.target.value)}
                          className="charge-amount-input"
                        />
                        <button 
                          className="btn small-cd add-charge-btn"
                          onClick={handleAddCharge}
                        >
                          Add
                        </button>
                      </div>

                      {formData.advancedCharges.length > 0 && (
                        <div className="charges-list">
                          {formData.advancedCharges.map((charge, index) => (
                            <div key={index} className="charge-item">
                              <div className="charge-info">
                                <span className="charge-item-name">{charge.name}</span>
                                <span className="charge-item-amount">${charge.amount}</span>
                              </div>
                              <button 
                                className="charge-remove-btn"
                                onClick={() => handleRemoveCharge(index)}
                                aria-label="Remove charge"
                              >
                                ×
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                <div className="form-section">
                  <h4 className="section-title">Carrier Requirements</h4>
                  <p className="section-desc">Only carriers meeting these criteria will see this load</p>
                  
                  <div className="requirements-grid">
                    {['Hazmat', 'Team', 'TWIC', 'Lumper', 'Tarp'].map(req => (
                      <button
                        key={req}
                        className={`requirement-tag ${formData.carrierRequirements.includes(req) ? 'active' : ''}`}
                        onClick={() => toggleRequirement(req)}
                      >
                        {req}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="form-section">
                  <h4 className="section-title">Driver Instructions</h4>
                  <p className="section-desc">Shown to the driver after booking. Be clear after booking to avoid delays or confusion.</p>
                  
                  <textarea
                    name="driverInstructions"
                    placeholder="Gate codes, check-in process, dock rules, contact details, safety requirements..."
                    value={formData.driverInstructions}
                    onChange={handleInputChange}
                    className="driver-textarea"
                  />
                </div>

                <div className="estimated-total">
                  <p><strong>Estimated Total Pay: $ —</strong> Visibility: Public Carriers</p>
                </div>

                <div className="step-actions">
                  <button className="btn small ghost-cd" onClick={handleBack}>← Back</button>
                  <button className="btn small-cd" onClick={handleNext}>Next → Visibility</button>
                </div>
              </div>
            )}

            {/* STEP 3: Visibility & Preferences */}
            {step === 3 && (
              <div className="add-loads-step">
                <div className="step-header">
                  <h2>Create New Load</h2>
                  <p className="step-subtitle">Step 3 of 3 – Visibility & Preferences</p>
                  <p className="step-description">Load ID: FP-2504-611-00123</p>
                </div>

                <div className="form-section">
                  <h4 className="section-title">Load Visibility</h4>
                  <p className="section-desc">Choose who can see and book this load</p>
                  
                  <div className="visibility-selector">
                    <button
                      className={`visibility-btn ${formData.visibility === 'public' ? 'active' : ''}`}
                      onClick={() => handleVisibilitySelect('public')}
                    >
                      <div className="visibility-icon">🌐</div>
                      <div className="visibility-label">Public Marketplace</div>
                      <div className="visibility-desc">Visible to all approved carriers</div>
                    </button>
                    <button
                      className={`visibility-btn ${formData.visibility === 'network' ? 'active' : ''}`}
                      onClick={() => handleVisibilitySelect('network')}
                    >
                      <div className="visibility-icon">🤝</div>
                      <div className="visibility-label">My Network</div>
                      <div className="visibility-desc">Preferred and contracted carriers</div>
                    </button>
                    <button
                      className={`visibility-btn ${formData.visibility === 'private' ? 'active' : ''}`}
                      onClick={() => handleVisibilitySelect('private')}
                    >
                      <div className="visibility-icon">🔒</div>
                      <div className="visibility-label">Private</div>
                      <div className="visibility-desc">Invitation only, select carriers</div>
                    </button>
                  </div>
                </div>

                <div className="form-section">
                  <h4 className="section-title">Automation</h4>
                  <p className="section-desc">Speed up booking with intelligent automation.</p>
                  
                  <div className="automation-items">
                    <div className="automation-row">
                      <div className="automation-left">
                        <div className="automation-title">Auto Match Carriers</div>
                        <div className="automation-desc">Automatically suggest best fit carriers</div>
                      </div>
                      <label className="toggle-label">
                        <input
                          type="checkbox"
                          name="autoMatch"
                          checked={formData.autoMatch}
                          onChange={handleInputChange}
                          className="toggle-input"
                        />
                        <span className="toggle-slider"></span>
                      </label>
                    </div>

                    <div className="automation-row">
                      <div className="automation-left">
                        <div className="automation-title">Instant Booking</div>
                        <div className="automation-desc">Allow carriers to book without approval</div>
                      </div>
                      <label className="toggle-label">
                        <input
                          type="checkbox"
                          name="instantBooking"
                          checked={formData.instantBooking}
                          onChange={handleInputChange}
                          className="toggle-input"
                        />
                        <span className="toggle-slider"></span>
                      </label>
                    </div>

                    <div className="automation-row">
                      <div className="automation-left">
                        <div className="automation-title">Post to Load Boards</div>
                        <div className="automation-desc">TQL, DAT, 123Loadboard</div>
                      </div>
                      <label className="toggle-label">
                        <input
                          type="checkbox"
                          name="postToLoadBoards"
                          checked={formData.postToLoadBoards}
                          onChange={handleInputChange}
                          className="toggle-input"
                        />
                        <span className="toggle-slider"></span>
                      </label>
                    </div>
                  </div>
                </div>

                <div className="form-section">
                  <h4 className="section-title">AI Recommendations</h4>
                  <p className="section-desc">Smart insights to optimize your load posting.</p>
                  
                  <div className="ai-recommendations">
                    <div className="ai-item">
                      <div className="ai-title">Best Time to Post</div>
                      <div className="ai-desc">Wednesday 10:00 AM – Max carrier engagement</div>
                      <div className="ai-icon">🕐</div>
                    </div>

                    <div className="ai-item">
                      <div className="ai-title">Rate Adjustment Suggestion</div>
                      <div className="ai-desc">Increase rate by 1% to attract high-match carriers</div>
                      <div className="ai-icon">📊</div>
                    </div>

                    <div className="ai-item">
                      <div className="ai-title">High-Match Carriers</div>
                      <div className="ai-desc">5 carriers with highest match scores</div>
                      <div className="ai-icon">✅</div>
                    </div>
                  </div>
                </div>

                <div className="review-summary">
                  <h4>Review Summary</h4>
                  <div className="summary-grid">
                    <div className="summary-item">
                      <div className="summary-label">Route</div>
                      <div className="summary-value">Origin → Destination</div>
                    </div>
                    <div className="summary-item">
                      <div className="summary-label">Equipment</div>
                      <div className="summary-value">Dry Van - FTL</div>
                    </div>
                    <div className="summary-item">
                      <div className="summary-label">Total Pay</div>
                      <div className="summary-value">$ —</div>
                    </div>
                  </div>
                  <div className="summary-notes">
                    <p>✅ Everything looks good and ready to post</p>
                    <p className="optional-note">You can edit this load later if needed</p>
                  </div>
                </div>

                <div className="step-actions">
                  <button className="btn small ghost-cd" onClick={handleBack}>← Back</button>
                  <button className="btn small-cd" onClick={handlePostLoad}>Post Load</button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
