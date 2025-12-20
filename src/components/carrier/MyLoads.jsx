import React, { useState } from 'react';
import '../../styles/carrier/MyLoads.css';
import AddLoads from './AddLoads';

const sampleData = {
  tendered: [
    { id: '#LD2024001', origin: 'Chicago, IL', destination: 'Dallas, TX', broker: 'FreightBroker Co.', price: '$2,850', pickup: 'Dec 28, 2024' },
    { id: '#LD2024002', origin: 'Atlanta, GA', destination: 'Miami, FL', broker: 'LogiTrans LLC', price: '$1,650', pickup: 'Dec 29, 2024' }
  ],
  accepted: [
    { id: '#LD2024003', origin: 'Phoenix, AZ', destination: 'Denver, CO', broker: 'Swift Logistics', price: '$3,200', driver: 'John Martinez' }
  ],
  inTransit: [
    { id: '#LD2024004', origin: 'Los Angeles, CA', destination: 'Seattle, WA', broker: 'Pacific Freight', price: '$4,100', driver: 'Sarah Wilson' }
  ],
  delivered: [
    { id: '#LD2024005', origin: 'Houston, TX', destination: 'New Orleans, LA', broker: 'Gulf Coast Trans', price: '$1,850', driver: 'Mike Johnson' }
  ],
  pod: [
    { id: '#LD2024006', origin: 'Detroit, MI', destination: 'Cleveland, OH', broker: 'Midwest Freight', price: '$950', driver: 'Tom Anderson' }
  ],
  invoiced: [
    { id: '#LD2024007', origin: 'Boston, MA', destination: 'New York, NY', broker: 'Northeast Express', price: '$1,200', invoice: '#INV-2024-007' }
  ],
  settled: [
    { id: '#LD2024008', origin: 'Portland, OR', destination: 'San Francisco, CA', broker: 'WestLine Logistics', price: '$1,400' }
  ]
};

function Column({ title, items }) {
  const key = title ? title.toLowerCase() : '';
  const isTender = key === 'tendered' || key.includes('tender');
  const isAccepted = key === 'accepted' || key.includes('accept');
  const isInTransit = key === 'in transit' || key.includes('transit') || key.includes('in transit');
  const isDelivered = key === 'delivered' || key.includes('deliver');
  const isPod = key === 'pod' || key.includes('pod');
  const isInvoiced = key === 'invoiced' || key.includes('invoice') || key.includes('invoiced');
  const isSettled = key === 'settled' || key.includes('settled');
  return (
    <div className={`ml-column ${isTender ? 'tender-column' : ''} ${isAccepted ? 'accepted-column' : ''} ${isInTransit ? 'in-transit-column' : ''} ${isDelivered ? 'delivered-column' : ''} ${isPod ? 'pod-column' : ''} ${isInvoiced ? 'invoiced-column' : ''} ${isSettled ? 'settled-column' : ''}`}>
      <div className="ml-column-inner">
        <div className="ml-column-header">
          <h4>{title}</h4>
          <span className="ml-count">{items.length}</span>
        </div>
        <div className="ml-column-list">
          {items.map((it) => (
            <div className={`ml-card ${isTender ? 'tender-card' : ''} ${isAccepted ? 'accepted-card' : ''} ${isInTransit ? 'in-transit-card' : ''} ${isDelivered ? 'delivered-card' : ''} ${isPod ? 'pod-card' : ''} ${isInvoiced ? 'invoiced-card' : ''} ${isSettled ? 'settled-card' : ''}`} key={it.id} role="article">
              <div className="ml-card-top">
                <div className="ml-id">{it.id}</div>
                <div className="ml-tag">{title}</div>
              </div>
              <div className="ml-card-body">
                <div className="ml-route"><span className="ml-dot green" />{it.origin}</div>
                <div className="ml-route"><span className="ml-dot red" />{it.destination}</div>
                {/* Broker row */}
                <div className="ml-broker">{it.broker}</div>

                {/* Driver or Invoice row (for non-tendered) */}
                {!isTender && it.driver && (
                  <div className="ml-driver-row">
                    <div className="muted">Driver: {it.driver}</div>
                    <div className="ml-price">{it.price}</div>
                  </div>
                )}

                {it.invoice && <div className="muted">Invoice: {it.invoice}</div>}

                {/* Pickup for tendered entries (pickup left, price right) */}
                {isTender && it.pickup && (
                  <div className="ml-pickup-row">
                    <div className="ml-pickup muted">Pickup: {it.pickup}</div>
                    <div className="ml-price">{it.price}</div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function MyLoads() {
  const [showAddLoads, setShowAddLoads] = useState(false);

  return (
    <div className="myloads-root">
      <div className="ml-header">
        <div className="fp-header-titles">
          <h2>My Loads</h2>
          <p className="fp-subtitle">Track and manage your active loads</p>
        </div>
        <div className="ml-actions">
          <div className="ml-toolbar">
            {/* <button className="btn small">Kanban</button>
            <button className="btn ghost small">List</button>
            <button className="btn ghost small">Map</button> */}
            <input className="ml-search" placeholder="Search loads..." />
            <button className="btn small-cd" onClick={() => setShowAddLoads(true)}>+ Add Load</button>
          </div>
        </div>
      </div>

      <div className="ml-board">
        <Column title="Tendered" items={sampleData.tendered} />
        <Column title="Accepted" items={sampleData.accepted} />
        <Column title="In Transit" items={sampleData.inTransit} />
        <Column title="Delivered" items={sampleData.delivered} />
        <Column title="POD" items={sampleData.pod} />
        <Column title="Invoiced" items={sampleData.invoiced} />
        <Column title="Settled" items={sampleData.settled} />
      </div>

      {showAddLoads && <AddLoads onClose={() => setShowAddLoads(false)} />}
    </div>
  );
}
