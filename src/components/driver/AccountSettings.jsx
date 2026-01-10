import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { API_URL } from '../../config';
import '../../styles/driver/AccountSettings.css';

export default function AccountSettings({ onProfileUpdate }) {
  const { currentUser } = useAuth();
  const fileInputRef = useRef(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [profileData, setProfileData] = useState({
    fullName: '',
    email: '',
    phone: '',
    address: '',
    profilePicture: null,
    emergency_contact_name: '',
    emergency_contact_relationship: '',
    emergency_contact_phone: ''
  });
  const [message, setMessage] = useState({ type: '', text: '' });

  useEffect(() => {
    fetchProfileData();
  }, [currentUser]);

  const fetchProfileData = async () => {
    if (!currentUser) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const token = await currentUser.getIdToken();
      const response = await fetch(`${API_URL}/onboarding/data`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      if (response.ok) {
        const data = await response.json();
        if (data.data) {
          setProfileData({
            fullName: data.data.fullName || '',
            email: data.data.email || currentUser.email || '',
            phone: data.data.phone || '',
            address: data.data.address || '',
            profilePicture: data.data.profile_picture_url || null,
            emergency_contact_name: data.data.emergency_contact_name || '',
            emergency_contact_relationship: data.data.emergency_contact_relationship || '',
            emergency_contact_phone: data.data.emergency_contact_phone || ''
          });
        }
      }
    } catch (error) {
      console.error('Error fetching profile:', error);
      setMessage({ type: 'error', text: 'Failed to load profile data' });
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (field, value) => {
    setProfileData(prev => ({ ...prev, [field]: value }));
  };

  const handlePhotoClick = () => {
    fileInputRef.current?.click();
  };

  const handlePhotoChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'];
    if (!allowedTypes.includes(file.type)) {
      setMessage({ type: 'error', text: 'Invalid file type. Please upload JPG, PNG, GIF, or WebP' });
      return;
    }

    // Validate file size (5MB)
    if (file.size > 5 * 1024 * 1024) {
      setMessage({ type: 'error', text: 'File size must be less than 5MB' });
      return;
    }

    try {
      setUploading(true);
      setMessage({ type: '', text: '' });
      const token = await currentUser.getIdToken();
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(`${API_URL}/auth/profile/picture`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });

      if (response.ok) {
        const result = await response.json();
        setProfileData(prev => ({ ...prev, profilePicture: result.profile_picture_url }));
        setMessage({ type: 'success', text: 'Profile picture uploaded successfully!' });
        if (onProfileUpdate) onProfileUpdate();
        setTimeout(() => setMessage({ type: '', text: '' }), 3000);
      } else {
        const error = await response.json();
        setMessage({ type: 'error', text: error.detail || 'Failed to upload profile picture' });
      }
    } catch (error) {
      console.error('Error uploading picture:', error);
      setMessage({ type: 'error', text: 'Failed to upload profile picture' });
    } finally {
      setUploading(false);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleSaveProfile = async () => {
    if (!currentUser) return;

    try {
      setSaving(true);
      setMessage({ type: '', text: '' });
      const token = await currentUser.getIdToken();
      
      const updateData = {
        phone: profileData.phone,
        address: profileData.address,
        emergency_contact_name: profileData.emergency_contact_name,
        emergency_contact_relationship: profileData.emergency_contact_relationship,
        emergency_contact_phone: profileData.emergency_contact_phone
      };

      // Add name field if it exists
      if (profileData.fullName) {
        updateData.name = profileData.fullName;
        const nameParts = profileData.fullName.split(' ');
        if (nameParts.length > 0) {
          updateData.first_name = nameParts[0];
          if (nameParts.length > 1) {
            updateData.last_name = nameParts.slice(1).join(' ');
          }
        }
      }

      const response = await fetch(`${API_URL}/auth/profile/update`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(updateData)
      });

      if (response.ok) {
        setMessage({ type: 'success', text: 'Profile updated successfully!' });
        if (onProfileUpdate) onProfileUpdate();
        setTimeout(() => setMessage({ type: '', text: '' }), 3000);
      } else {
        const error = await response.json();
        setMessage({ type: 'error', text: error.detail || 'Failed to update profile' });
      }
    } catch (error) {
      console.error('Error saving profile:', error);
      setMessage({ type: 'error', text: 'Failed to update profile' });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="account-settings-container">
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '400px' }}>
          <i className="fas fa-spinner fa-spin" style={{ fontSize: '2rem', color: '#3b82f6' }}></i>
          <span style={{ marginLeft: '10px' }}>Loading profile...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="account-settings-container">
      <header className="account-settings-header">
        <h2>Account & Settings</h2>
        <p>Manage your profile, preferences, security, and integrations</p>
      </header>

      {message.text && (
        <div className={`profile-message ${message.type}`} style={{
          padding: '12px 16px',
          marginBottom: '20px',
          borderRadius: '8px',
          backgroundColor: message.type === 'success' ? '#d1fae5' : '#fee2e2',
          color: message.type === 'success' ? '#065f46' : '#991b1b',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <i className={`fa-solid ${message.type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'}`}></i>
          {message.text}
        </div>
      )}

      {/* Profile & Preferences Section */}
      <div className="profile-preferences-section">
        {/* Profile Card */}
        <div className="profile-card">
          <h2 className="profile-card-title">
            Profile
          </h2>
          <div className="profile-card-header">
            <img 
              src={profileData.profilePicture || "https://randomuser.me/api/portraits/men/32.jpg"} 
              alt="Profile" 
              className="profile-avatar"
              onError={(e) => {
                e.target.src = "https://randomuser.me/api/portraits/men/32.jpg";
              }}
            />
            <div>
              <div className="profile-name">{profileData.fullName || 'Driver'}</div>
              <button 
                className="change-photo-btn" 
                onClick={handlePhotoClick}
                disabled={uploading}
              >
                {uploading ? 'Uploading...' : 'Change Photo'}
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/jpg,image/png,image/gif,image/webp"
                onChange={handlePhotoChange}
                style={{ display: 'none' }}
              />
            </div>
          </div>
          <div className="profile-field">
            <label>Full Name</label>
            <input 
              type="text" 
              value={profileData.fullName} 
              onChange={(e) => handleInputChange('fullName', e.target.value)}
              placeholder="Full Name"
            />
          </div>
          <div className="profile-field">
            <label>Phone</label>
            <input 
              type="text" 
              value={profileData.phone} 
              onChange={(e) => handleInputChange('phone', e.target.value)}
              placeholder="+1 (555) 123-4567"
            />
          </div>
          <div className="profile-field">
            <label>Email</label>
            <input 
              type="email" 
              value={profileData.email} 
              readOnly 
              style={{ backgroundColor: '#f3f4f6', cursor: 'not-allowed' }}
            />
          </div>
          <div className="profile-field">
            <label>Address</label>
            <textarea 
              value={profileData.address} 
              rows={2}
              onChange={(e) => handleInputChange('address', e.target.value)}
              placeholder="123 Main St, Dallas, TX 75201"
            />
          </div>
          <div className="emergency-contact-label">Emergency Contact</div>
          <div className="profile-field">
            <input 
              type="text" 
              placeholder="Contact Name"
              value={profileData.emergency_contact_name}
              onChange={(e) => handleInputChange('emergency_contact_name', e.target.value)}
            />
          </div>
          <div className="profile-field">
            <input 
              type="text" 
              placeholder="Relationship"
              value={profileData.emergency_contact_relationship}
              onChange={(e) => handleInputChange('emergency_contact_relationship', e.target.value)}
            />
          </div>
          <div className="profile-field">
            <input 
              type="text" 
              placeholder="Phone Number"
              value={profileData.emergency_contact_phone}
              onChange={(e) => handleInputChange('emergency_contact_phone', e.target.value)}
            />
          </div>
          <button 
            className="btn small-cd" 
            onClick={handleSaveProfile}
            disabled={saving}
            style={{ marginTop: '16px' }}
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
          <button className="btn small-cd" style={{ marginTop: '8px' }}>
            Preview Marketplace Profile
          </button>
        </div>

        {/* Preferences Card */}
        <div className="preferences-card">
          <h2 className="preferences-card-title">
            Preferences
          </h2>
          <div className="preferences-field">
            <label>Language</label>
            <select defaultValue="English">
              <option>English</option>
              <option>Spanish</option>
            </select>
          </div>
          <div className="preferences-section-label">Notifications</div>
          <div className="preferences-checkbox">
            <label>Compliance Alerts</label>
            <label className="toggle-switch">
              <input type="checkbox" checked readOnly />
              <span className="slider"></span>
            </label>
          </div>
          <div className="preferences-checkbox">
            <label>Messages</label>
            <label className="toggle-switch">
              <input type="checkbox" checked readOnly />
              <span className="slider"></span>
            </label>
          </div>
          <div className="preferences-checkbox">
            <label>AI Tips</label>
            <label className="toggle-switch">
              <input type="checkbox" readOnly />
              <span className="slider"></span>
            </label>
          </div>
          <div className="preferences-link">
            <a href="#">View Notification History</a>
          </div>
          <div className="preferences-field">
            <label>Calendar Sync</label>
            <select defaultValue="Google Calendar">
              <option>Google Calendar</option>
              <option>Outlook</option>
            </select>
          </div>

        </div>
      </div>
      
      {/* Security & Accessibility Section */}
      <div className="security-accessibility-section">
        <div className="security-card">
          <h3 className="card-title">Security</h3>
          <ul className="action-list">
            <li className="action-item">Change Password <span className="chev">›</span></li>
            <li className="action-item">
              <div className="action-left">
                <div className="action-title">Two-Factor Authentication</div>
                <div className="int-status-badge active">Enabled</div>
              </div>
              <span className="chev">›</span>
            </li>
            <li className="action-item">Biometric Login <span className="chev">›</span></li>
            <li className="action-item">Session & Device Management <span className="chev">›</span></li>
          </ul>
        </div>

        <div className="accessibility-card">
          <h3 className="card-title">Accessibility</h3>
          <div className="access-field">
            <label>Font Size</label>
            <select defaultValue="Medium">
              <option>Small</option>
              <option>Medium</option>
              <option>Large</option>
            </select>
          </div>
          <div className="preferences-section-label">Assistive Features</div>
          <div className="preferences-checkbox">
            <label>High Contrast Mode</label>
            <label className="toggle-switch">
              <input type="checkbox" readOnly />
              <span className="slider"></span>
            </label>
          </div>
          <div className="preferences-checkbox">
            <label>Screen Reader Compatible</label>
            <label className="toggle-switch">
              <input type="checkbox" checked readOnly />
              <span className="slider"></span>
            </label>
          </div>
          <div className="preferences-checkbox muted">
            <label>Voice Commands</label>
            <div className="coming-soon">Coming Soon</div>
          </div>
        </div>
      </div>

       {/* Reports & Integrations Section */}
      <div className="reports-integrations-section">
        <div className="reports-card">
          <h3 className="card-title">Reports</h3>
          <ul className="action-list">
            <li className="action-item">Compliance Report <span className="download"><i className='fa-solid fa-download'></i></span></li>
            <li className="action-item">Load Report <span className="download"><i className='fa-solid fa-download'></i></span></li>
            <li className="action-item">Activity Log <span className="download"><i className='fa-solid fa-download'></i></span></li>
          </ul>

          <div className="divider" />
          <div className="export-label">Export Options</div>
          <div className="export-options">
            <button className="btn small-cd" style={{width: '100%'}}>PDF</button>
            <button className="btn small-cd" style={{width: '100%'}}>CSV</button>
          </div>
          <button className="btn small ghost-cd">Request Full Data Download</button>
        </div>

        <div className="integrations-card">
          <h3 className="card-title">Integrations</h3>
          <ul className="integration-list">
            <li className="integration-item">
              <div>
                <div className="integration-title">ELD Device</div>
                <div className="integration-desc">Garmin eLog 2.0 - Device ID: #GL2024567</div>
              </div>
              <div className="int-status-badge active">Connected</div>
            </li>
            <li className="integration-item">
              <div>
                <div className="integration-title">Fuel Services</div>
                <div className="integration-desc">TVC Pro Driver - Fleet Card Integration</div>
              </div>
              <div className="int-status-badge active">Connected</div>
            </li>
            <li className="integration-item">
              <div>
                <div className="integration-title">Training Provider</div>
                <div className="integration-desc">Connect training services for compliance tracking</div>
              </div>
              <div className="int-status-badge disconnected">Not Connected</div>
            </li>
          </ul>
          <button className="btn small-cd" style={{marginTop: '20px'}}>Manage Permissions</button>
        </div>
      </div>
      {/* Support & Help Section */}
      <div className="support-help-section">
        <div className="support-card">
          <h3 className="card-title">Support & Help</h3>
          <ul className="action-list">
            <li className="action-item">Help Center & FAQ <span className="external">↗</span></li>
            <li className="action-item">Contact Support <span className="chev">›</span></li>
          </ul>
        </div>
      </div>
    </div>
  );
}
