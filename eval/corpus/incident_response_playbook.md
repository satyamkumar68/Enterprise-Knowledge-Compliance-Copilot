# Incident Response & Disaster Recovery Playbook

## 1. Purpose & Incident Classification
This document outlines the operational procedures for managing production outages, security breaches, and degraded service incidents across all cloud regions.

## 2. Severity Levels and Response SLAs
- **Sev-0 (Critical Emergency)**:
  - Definition: Catastrophic service outage affecting >25% of users, or confirmed active data exfiltration/breach.
  - Initial Response SLA: 15 minutes.
  - Status Page Update Cadence: Every 30 minutes.
- **Sev-1 (Major Incident)**:
  - Definition: Core functionality unavailable for a single enterprise tier, or significant latency degradation (>5000ms p95).
  - Initial Response SLA: 30 minutes.
  - Status Page Update Cadence: Every 60 minutes.
- **Sev-2 (Moderate Degraded State)**:
  - Definition: Non-critical feature failure with available customer workarounds.
  - Initial Response SLA: 2 hours.
- **Sev-3 (Minor Bug / Low Impact)**:
  - Definition: Cosmetic defects, internal tooling delays, non-customer-facing performance anomalies.
  - Initial Response SLA: 24 hours.

## 3. Incident Commander (IC) Role & Chain of Command
- The primary on-call engineer automatically assumes the role of Incident Commander (IC) upon triage.
- The IC holds sole authority over rollback decisions, production mitigations, and cross-team task delegation.
- During Sev-0 and Sev-1 incidents, all ad-hoc communications are silenced, and an official Incident War Room (Zoom/Slack #incident-war-room) is activated.

## 4. External Communications & Blackout Policy
- Only the designated Public Relations officer or Chief Information Security Officer (CISO) is authorized to communicate incident details to customers, media, or regulatory authorities.
- Employees are strictly prohibited from discussing ongoing security incidents on external social media or public forums.

## 5. Post-Mortem & Root Cause Analysis (RCA) Requirements
- A blameless post-mortem document must be authored within 72 hours of incident resolution for all Sev-0 and Sev-1 incidents.
- All action items generated in the post-mortem review must be assigned a Jira ticket and resolved within 14 business days.
