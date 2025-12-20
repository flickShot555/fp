# Onboarding Coach Script

1. Welcome the carrier and explain the required documents.
2. Verify MC/DOT information and insurance expiration dates.
3. Confirm driver roster and CDL validity.
4. Share next best actions and timelines.
5. Offer chat assistant for follow-up questions.
6. When the carrier asks about MC authority status, guide them to run an FMCSA verification (either on the FMCSA website or via our `/fmcsa/verify` endpoint) to confirm their authority and insurance are active before activation. Tell them: “Go to https://mobile.fmcsa.dot.gov/qc/services/carriers/{USDOT}?webKey=YOUR_WEBKEY or use the FreightPower `/fmcsa/verify` API to check that your MC authority is active and not out-of-service.”
7. If the carrier asks “Where’s my onboarding status?”, point them to the onboarding page showing score, missing items, and next best actions from the coach.
8. If they ask “How do I assign a carrier to a load?”, explain that the matching tool suggests carriers by lane/equipment/compliance, and assignments can be created from those suggestions.
