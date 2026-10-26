# Enterprise Access Control & SOC 2 Compliance Policy

## 1. Scope and Objective
This policy governs access to all production databases, infrastructure, and internal enterprise services. All employees, contractors, and third-party vendors must comply with these guidelines to maintain SOC 2 Type II compliance.

## 2. Principle of Least Privilege
Access to production systems is granted strictly on a need-to-know and least-privilege basis. Employees are only permitted access required for their directly assigned responsibilities.

## 3. Production Database Access Approval
- Employees must obtain written approval from their direct engineering manager and the Security Operations Team before receiving production database credentials.
- Temporary elevated access (break-glass access) is valid for a maximum duration of 8 hours and requires an active Jira incident ticket.
- Production database credentials must never be shared through public channels, direct messages, email, or unencrypted notes.

## 4. Credential Rotation & Password Requirements
- User passwords for all internal enterprise systems must be at least 16 characters in length and contain alphanumeric characters and symbols.
- User passwords must be rotated every 90 days.
- Automated service account API tokens must be rotated every 180 days.
- Multi-Factor Authentication (MFA) via hardware security keys (FIDO2/WebAuthn) or time-based one-time password (TOTP) apps is mandatory for all employee accounts. SMS-based 2FA is strictly prohibited.

## 5. Employee Deprovisioning & Offboarding SLA
- Upon employee termination or reassignment, all system access, SSH keys, VPN certificates, and database accounts must be completely revoked within 24 hours.
- Emergency deprovisioning (for adverse departures) must be executed within 1 hour of notification by Human Resources.

## 6. Remote Access & VPN
- All remote access to production environments must pass through the corporate Zero-Trust Network Access (ZTNA) gateway or wireguard-based VPN with device posture checking enabled.
