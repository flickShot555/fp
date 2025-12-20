# FreightPower Onboarding FAQs

## What paperwork do I need?
- Certificate of Insurance (COI) showing active coverage
- IRS Form W-9 with TIN and signature
- CDL for every active driver

## How do I upload documents?
Use the FreightPower portal’s onboarding section or send PDFs directly through the `/documents` API endpoint; only PDF files are accepted right now.

## How fast do approvals happen?
Once we receive clean paperwork we update status within one business day.

## Who do I contact for help?
Use the FreightPower assistant or email ai-onboarding@freightpower.example

## What if my COI is about to expire?
Upload the renewed COI as soon as it is available; expired or soon-to-expire certificates will block activation until fresh coverage is on file.

## Can I see why my onboarding score is low?
Yes—the onboarding screen lists missing fields and next-best actions (e.g., “Upload current CDL” or “Connect MC/DOT profile”) pulled directly from the validation results.

## How do I check my MC authority status?
Run an FMCSA verification (e.g., via `/fmcsa/verify` or FMCSA QCMobile) to confirm your authority and insurance are active; the onboarding coach will surface any warnings.

## How do I assign a carrier to a load?
Use the matching tool to get top carrier suggestions for your lane/equipment; then assign the carrier in the load workflow and notify them. Matches include reasons (lane, compliance, FMCSA).

## Can you auto-fill my forms?
Yes—upload your CDL/medical docs and we can auto-fill driver registration, clearinghouse consent, and MVR release drafts. You’ll still need to review and sign.
