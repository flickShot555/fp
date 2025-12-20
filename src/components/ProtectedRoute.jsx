import React, { useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { auth, db } from '../firebase';
import { onAuthStateChanged } from 'firebase/auth';
import { doc, getDoc } from 'firebase/firestore';

/**
 * ProtectedRoute - Guards dashboard routes
 * 
 * Checks:
 * 1. User is authenticated (Firebase)
 * 2. User's email is verified
 * 3. Optionally checks role-based access
 * 
 * Redirects:
 * - To /login if not authenticated
 * - To /verify if email not verified (for MFA users)
 */
const ProtectedRoute = ({ children, allowedRoles = [] }) => {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState(null);
  const [userData, setUserData] = useState(null);
  const location = useLocation();

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      if (firebaseUser) {
        setUser(firebaseUser);
        
        // Fetch user data from Firestore
        try {
          const userDocRef = doc(db, "users", firebaseUser.uid);
          const userDoc = await getDoc(userDocRef);
          if (userDoc.exists()) {
            setUserData(userDoc.data());
          }
        } catch (err) {
          console.error("Error fetching user data:", err);
        }
      } else {
        setUser(null);
        setUserData(null);
      }
      setLoading(false);
    });

    return () => unsubscribe();
  }, []);

  // Show loading spinner while checking auth
  if (loading) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
        background: '#f5f7fa'
      }}>
        <div style={{
          width: '40px',
          height: '40px',
          border: '4px solid #e0e0e0',
          borderTop: '4px solid #2563eb',
          borderRadius: '50%',
          animation: 'spin 1s linear infinite'
        }} />
        <style>{`
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    );
  }

  // Not authenticated - redirect to login
  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Email not verified - redirect to verification
  // Note: For Firebase phone auth, emailVerified might be false but phone is verified
  // We check both email verification and if user came through proper flow
  if (!user.emailVerified && userData?.mfa_enabled) {
    return <Navigate to="/verify" state={{ 
      phone: userData?.phone,
      role: userData?.role,
      fromProtectedRoute: true 
    }} replace />;
  }

  // Role-based access control (if allowedRoles specified)
  if (allowedRoles.length > 0 && userData) {
    const userRole = userData.role?.toLowerCase();
    const allowed = allowedRoles.map(r => r.toLowerCase());
    
    if (!allowed.includes(userRole)) {
      // Redirect to appropriate dashboard based on actual role
      const roleRedirects = {
        'carrier': '/carrier-dashboard',
        'driver': '/driver-dashboard',
        'shipper': '/shipper-dashboard',
        'admin': '/admin-dashboard',
        'super_admin': '/super-admin-dashboard'
      };
      
      const correctDashboard = roleRedirects[userRole] || '/carrier-dashboard';
      return <Navigate to={correctDashboard} replace />;
    }
  }

  // All checks passed - render the protected content
  return children;
};

export default ProtectedRoute;

