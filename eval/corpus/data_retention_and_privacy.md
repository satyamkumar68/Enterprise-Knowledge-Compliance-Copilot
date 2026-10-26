# Global Data Retention, GDPR Compliance & Privacy Policy

## 1. Overview
This policy defines the lifecycle, retention periods, and irreversible disposal criteria for customer data, operational telemetry, and financial records in accordance with GDPR, CCPA, and enterprise regulatory standards.

## 2. Customer Personal Data (PII) Retention Schedules
- Customer personally identifiable information (PII) must be retained only for the duration of the active subscription agreement.
- Following contract termination, all associated customer PII must be permanently sanitized and purged within 30 calendar days.
- Backup snapshots containing customer PII are retained in immutable warm storage for a maximum of 90 days before automatic rolling deletion.

## 3. Financial, Audit, and Compliance Records
- Financial transactions, invoicing histories, and tax reporting data must be retained for exactly 7 years to satisfy corporate audit compliance.
- Security audit logs (login attempts, permission changes, database access logs) must be retained for at least 365 days in encrypted, tamper-evident cold storage (WORM storage).

## 4. GDPR Article 17: Right to Erasure ("Right to Be Forgotten")
- Data deletion requests submitted by European Union data subjects must be reviewed by the Data Protection Officer (DPO) within 5 business days.
- Upon approval, the user's personal identifiers must be completely removed or cryptographically pseudonymized across all primary databases within 30 calendar days.
- Hardcopy paper records containing PII must be cross-cut shredded on-site.

## 5. Cross-Border Data Transfers
- Personal data originating in the European Economic Area (EEA) must not be transferred outside the EEA without approved Standard Contractual Clauses (SCCs) or adequacy decisions.
- All cross-border data replication streams must be encrypted in transit using TLS 1.3 with forward secrecy.
