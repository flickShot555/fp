import firebase_admin
from firebase_admin import credentials, firestore
import os

# Initialize Firebase only once
if not firebase_admin._apps:
    # Get the directory where this file is located
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up one level to get to the apps folder
    apps_dir = os.path.dirname(current_dir)
    # Path to serviceAccountKey.json
    service_account_path = os.path.join(apps_dir, "serviceAccountKey.json")
    
    cred = credentials.Certificate(service_account_path)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# Helper to log actions
def log_action(user_id: str, action: str, details: str, ip: str = None):
    try:
        db.collection("audit_logs").add({
            "user_id": user_id,
            "action": action,
            "details": details,
            "ip_address": ip,
            "timestamp": firestore.SERVER_TIMESTAMP
        })
    except Exception as e:
        print(f"Audit log error: {e}")