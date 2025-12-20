// src/contexts/AuthContext.jsx
import React, { useContext, useState, useEffect } from "react";
import { auth, db } from "../firebase";
import { API_URL } from "../config";
import { 
  signInWithEmailAndPassword, 
  signOut, 
  onAuthStateChanged,
  RecaptchaVerifier,
  signInWithPhoneNumber,
  sendEmailVerification,
  sendPasswordResetEmail // NEW IMPORT
} from "firebase/auth";
import { doc, getDoc } from "firebase/firestore";

const AuthContext = React.createContext();

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(null);
  const [userRole, setUserRole] = useState(null);
  const [isVerified, setIsVerified] = useState(false);
  const [loading, setLoading] = useState(true);

  // --- 1. SIGNUP ---
  async function signup(email, password, name, phone, role) {
    const response = await fetch(`${API_URL}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, name, phone, role })
    });
    
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Signup failed");
    return data;
  }

  // --- 2. LOGIN WITH MFA CHECK (UPDATED) ---
  async function login(email, password) {
    // A. Standard Firebase Login
    const result = await signInWithEmailAndPassword(auth, email, password);
    const uid = result.user.uid;

    // B. Check Firestore for MFA Setting
    const docRef = doc(db, "users", uid);
    const docSnap = await getDoc(docRef);
    
    let mfaRequired = false;
    let phone = "";

    if (docSnap.exists()) {
      const data = docSnap.data();
      phone = data.phone; // Get phone from DB for SMS
      if (data.mfa_enabled === true) {
        mfaRequired = true;
      }
    }

    // C. Handle MFA or Log Success
    if (mfaRequired && phone) {
      // Trigger SMS immediately
      // Note: We return specific status so Login.jsx knows to redirect to /verify
      await sendOtp(phone);
      return { user: result.user, mfaRequired: true, phone: phone };
    } else {
      // No MFA? Log the login immediately
      await logLoginToBackend(result.user);
      return { user: result.user, mfaRequired: false };
    }
  }

  // Helper to log login (moved out to be reusable)
  async function logLoginToBackend(user) {
    try {
      const token = await user.getIdToken();
      await fetch(`${API_URL}/auth/log-login`, {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
    } catch (err) {
      console.error("Audit Log Failed:", err);
    }
  }

  // --- 3. PASSWORD RESET (NEW) ---
  function resetPassword(email) {
    return sendPasswordResetEmail(auth, email);
  }

  // --- 4. VERIFICATION UTILS ---
  const sendVerificationLink = async (user) => {
    if (user) {
      await sendEmailVerification(user, {
        url: 'http://localhost:5173/login', 
        handleCodeInApp: true
      });
    }
  };

  function setupRecaptcha(elementId) {
    if (window.recaptchaVerifier) {
      try { window.recaptchaVerifier.clear(); } catch (e) {}
      window.recaptchaVerifier = null;
    }
    // Ensure the element exists in DOM before attaching
    if(!document.getElementById(elementId)) return; 
    
    window.recaptchaVerifier = new RecaptchaVerifier(auth, elementId, {
      'size': 'invisible',
    });
  }

  async function sendOtp(phoneNumber) {
    setupRecaptcha("recaptcha-container");
    const appVerifier = window.recaptchaVerifier;
    return await signInWithPhoneNumber(auth, phoneNumber, appVerifier);
  }

  async function confirmOtpVerification() {
    if (!auth.currentUser) throw new Error("No user logged in");
    
    const token = await auth.currentUser.getIdToken();
    
    const response = await fetch(`${API_URL}/auth/verify-otp`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
    });

    if (!response.ok) throw new Error("Backend verification failed");
    
    setIsVerified(true);
    // If this was an MFA check, we should log the login now
    await logLoginToBackend(auth.currentUser);
    
    return true;
  }

  function logout() {
    return signOut(auth);
  }

  // --- MONITOR SESSION ---
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (user) => {
      if (user) {
        try {
          await user.reload(); 
          const docRef = doc(db, "users", user.uid);
          const docSnap = await getDoc(docRef);
          if (docSnap.exists()) {
            const data = docSnap.data();
            setUserRole(data.role);
            const isEmailVerified = user.emailVerified;
            setIsVerified(data.is_verified || isEmailVerified); 
          }
        } catch (e) {
          console.error("Fetch Role Error:", e);
        }
      } else {
        setUserRole(null);
        setIsVerified(false);
      }
      setCurrentUser(user);
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  const value = {
    currentUser,
    userRole,
    isVerified,
    signup,
    login,
    logout,
    resetPassword, // EXPORTED
    sendOtp,
    confirmOtpVerification,
    sendVerificationLink
  };

  return (
    <AuthContext.Provider value={value}>
      {!loading && children}
    </AuthContext.Provider>
  );
}