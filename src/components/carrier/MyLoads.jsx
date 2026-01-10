import React, { useState, useEffect } from 'react';
import '../../styles/carrier/MyLoads.css';
import AddLoads from './AddLoads';
import { API_URL } from '../../config';
import { auth } from '../../firebase';

// Map backend statuses to columns
const statusToColumn = {
  'draft': 'draft',
  'posted': 'tendered',
  'tendered': 'tendered',
  'accepted': 'accepted',
  'in_transit': 'inTransit',
  'delivered': 'delivered',
  'completed': 'settled',
  'cancelled': 'cancelled'
};

function Column({ title, items, isLoading, onItemClick }) {
  const key = title ? title.toLowerCase() : '';
  const isTender = key === 'tendered' || key.includes('tender');
  const isAccepted = key === 'accepted' || key.includes('accept');
  const isInTransit = key === 'in transit' || key.includes('transit') || key.includes('in transit');
  const isDelivered = key === 'delivered' || key.includes('deliver');
  const isPod = key === 'pod' || key.includes('pod');
  const isInvoiced = key === 'invoiced' || key.includes('invoice') || key.includes('invoiced');
  const isSettled = key === 'settled' || key.includes('settled');
  const isDraft = key === 'draft' || key.includes('draft');
  
  return (
    <div className={`ml-column ${isTender ? 'tender-column' : ''} ${isAccepted ? 'accepted-column' : ''} ${isInTransit ? 'in-transit-column' : ''} ${isDelivered ? 'delivered-column' : ''} ${isPod ? 'pod-column' : ''} ${isInvoiced ? 'invoiced-column' : ''} ${isSettled ? 'settled-column' : ''} ${isDraft ? 'draft-column' : ''}`}>
      <div className="ml-column-inner">
        <div className="ml-column-header">
          <h4>{title}</h4>
          <span className="ml-count">{items.length}</span>
        </div>
        <div className="ml-column-list">
          {isLoading ? (
            <div style={{padding: '20px', textAlign: 'center', color: '#6b7280'}}>Loading...</div>
          ) : items.length === 0 ? (
            <div style={{padding: '20px', textAlign: 'center', color: '#9ca3af'}}>No loads</div>
          ) : (
            items.map((it) => (
              <div 
                className={`ml-card ${isTender ? 'tender-card' : ''} ${isAccepted ? 'accepted-card' : ''} ${isInTransit ? 'in-transit-card' : ''} ${isDelivered ? 'delivered-card' : ''} ${isPod ? 'pod-card' : ''} ${isInvoiced ? 'invoiced-card' : ''} ${isSettled ? 'settled-card' : ''} ${isDraft ? 'draft-card' : ''}`} 
                key={it.id} 
                role="article"
                onClick={() => isDraft && onItemClick && onItemClick(it)}
                style={{cursor: isDraft ? 'pointer' : 'default'}}
              >
                <div className="ml-card-top">
                  <div className="ml-id">{it.id}</div>
                  <div className="ml-tag">{it.status}</div>
                </div>
                <div className="ml-card-body">
                  <div className="ml-route"><span className="ml-dot green" />{it.origin}</div>
                  <div className="ml-route"><span className="ml-dot red" />{it.destination}</div>
                  
                  {it.equipment && (
                    <div className="ml-broker">{it.equipment} • {it.weight ? `${it.weight} lbs` : 'N/A'}</div>
                  )}

                  {!isTender && it.driver && (
                    <div className="ml-driver-row">
                      <div className="muted">Driver: {it.driver}</div>
                      <div className="ml-price">{it.price}</div>
                    </div>
                  )}

                  {it.invoice && <div className="muted">Invoice: {it.invoice}</div>}

                  {isTender && it.pickup && (
                    <div className="ml-pickup-row">
                      <div className="ml-pickup muted">Pickup: {it.pickup}</div>
                      <div className="ml-price">{it.price}</div>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

export default function MyLoads() {
  const [showAddLoads, setShowAddLoads] = useState(false);
  const [resumeLoad, setResumeLoad] = useState(null); // For resuming draft loads
  const [loads, setLoads] = useState({
    draft: [],
    tendered: [],
    accepted: [],
    inTransit: [],
    delivered: [],
    pod: [],
    invoiced: [],
    settled: []
  });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch loads from backend
  useEffect(() => {
    fetchLoads();
  }, []);

  const fetchLoads = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const user = auth.currentUser;
      if (!user) {
        throw new Error('Not authenticated');
      }
      
      const token = await user.getIdToken();
      const response = await fetch(`${API_URL}/loads`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        throw new Error('Failed to fetch loads');
      }

      const data = await response.json();
      
      // Group loads by status into columns
      const grouped = {
        draft: [],
        tendered: [],
        accepted: [],
        inTransit: [],
        delivered: [],
        pod: [],
        invoiced: [],
        settled: []
      };

      data.loads.forEach(load => {
        const column = statusToColumn[load.status] || 'tendered';
        grouped[column].push({
          id: load.load_id,
          origin: load.origin,
          destination: load.destination,
          broker: 'FreightPower',
          equipment: load.equipment_type?.replace('_', ' '),
          weight: load.weight,
          price: load.total_rate ? `$${load.total_rate.toLocaleString()}` : 'N/A',
          pickup: load.pickup_date,
          status: load.status,
          driver: null, // Will be added when loads are assigned
          fullData: load // Store full load data for draft resume
        });
      });

      setLoads(grouped);
    } catch (err) {
      setError(err.message);
      console.error('Fetch loads error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDraftClick = (draftCard) => {
    setResumeLoad(draftCard.fullData);
    setShowAddLoads(true);
  };

  const handleLoadAdded = () => {
    // Refresh loads after adding new one
    fetchLoads();
    setShowAddLoads(false);
    setResumeLoad(null); // Clear resume state
  };

  return (
    <div className="myloads-root">
      {error && (
        <div style={{backgroundColor: '#fee2e2', color: '#991b1b', padding: '12px', borderRadius: '8px', marginBottom: '16px'}}>
          Error: {error}
        </div>
      )}
      
      <div className="ml-header">
        <div className="fp-header-titles">
          <h2>My Loads</h2>
          <p className="fp-subtitle">Track and manage your active loads</p>
        </div>
        <div className="ml-actions">
          <div className="ml-toolbar">
            <input className="ml-search" placeholder="Search loads..." />
            <button className="btn small-cd" onClick={() => setShowAddLoads(true)}>+ Add Load</button>
          </div>
        </div>
      </div>

      <div className="ml-board">
        <Column title="Draft" items={loads.draft} isLoading={isLoading} onItemClick={handleDraftClick} />
        <Column title="Tendered" items={loads.tendered} isLoading={isLoading} />
        <Column title="Accepted" items={loads.accepted} isLoading={isLoading} />
        <Column title="In Transit" items={loads.inTransit} isLoading={isLoading} />
        <Column title="Delivered" items={loads.delivered} isLoading={isLoading} />
        <Column title="POD" items={loads.pod} isLoading={isLoading} />
        <Column title="Invoiced" items={loads.invoiced} isLoading={isLoading} />
        <Column title="Settled" items={loads.settled} isLoading={isLoading} />
      </div>

      {showAddLoads && <AddLoads onClose={handleLoadAdded} draftLoad={resumeLoad} />}
    </div>
  );
}

