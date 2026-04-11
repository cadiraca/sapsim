# SKILL: SAP Security and Authorization

## Core Concepts

SAP security is built on an authorization concept using a role-based access control (RBAC) model. Users are assigned roles, roles contain authorization profiles, and profiles contain authorization objects with specific field values. An **authorization object** defines a permission check — for example, F_BKPF_BUK checks a user's authorization to post to a specific company code in FI. The check hierarchy is: User → Role → Profile → Authorization Object → Field Values. SAP provides two role types: **Single Roles** (direct object-to-profile mapping) and **Composite Roles** (grouping of single roles assigned to user groups). The Profile Generator (PFCG) automates profile generation from role menu entries — a critical tool that links menu navigation with underlying authorization objects.

Segregation of Duties (SoD) is a regulatory requirement (SOX, GDPR, audit compliance) that ensures no single user has conflicting authorizations — such as creating and approving purchase orders. SAP GRC (Governance, Risk, and Compliance) Access Control automates SoD analysis, emergency access management (Firefighter), and access request workflows.

## Key Transactions

- **SU01**: User administration — create, lock, unlock, and maintain user master records. Assign roles and force password resets.
- **PFCG**: Role Maintenance — the central tool for creating and editing roles, generating authorization profiles.
- **SU53**: Authorization check failure analysis. After an authorization error, run SU53 as the affected user to see the missing object/field.
- **SU24**: Maintain authorization default values for transactions. Used to fine-tune what PFCG auto-generates.
- **SUIM**: User Information System — reporting on who has what access. Critical for audits.
- **SU10**: Mass user maintenance — efficient for locking/unlocking multiple users or assigning roles in bulk.
- **STAUTHTRACE (SAT)**: Authorization trace — captures all authorization checks during a transaction to identify required objects for role design.
- **SM19/SM20**: Security audit log configuration and analysis. Tracks logons, transaction starts, and report executions.

## Common Challenges

**SoD Conflicts**: Users accumulate roles over time without proper deprovisioning, leading to conflicting access combinations. Annual user access reviews (UAR) using SUIM reporting are required to detect and remediate.

**Authorization Errors After Transport**: When roles are transported without regenerating profiles in target systems, users get authorization failures. Always regenerate profiles (PFCG → Generate) in target client after role import.

**Over-Authorization via SAP_ALL**: Granting SAP_ALL or SAP_NEW profiles to users — even temporarily — creates audit findings and security gaps. Use Firefighter (GRC) for emergency access instead.

**PFCG Authorization Object Missing**: Custom Z-programs may not have SU24 entries, causing PFCG to miss required checks. Developers must run STAUTHTRACE and maintain SU24 defaults for all custom transactions.

## Best Practices

- Follow the principle of least privilege — assign minimum necessary authorizations.
- Implement Firefighter IDs (GRC Emergency Access) for all privileged production activities instead of permanent broad access.
- Lock all standard SAP users (DDIC, SAP*, EARLYWATCH) that are not in active use. Change default passwords on initial system setup.
- Schedule monthly SUIM reports for users with critical authorizations (S_TCODE with SE38, SM59, SCC4, etc.).
- Use naming conventions for roles: Z_[MODULE]_[ROLE_TYPE]_[DESCRIPTION] for easy sorting and audit readability.

## Integration Points

Security integrates across all SAP modules — every transaction executes authorization checks. GRC integrates with HR for role provisioning based on position/job code (role mining). Identity Management (IdM) solutions (SAP IDM or external like SailPoint) connect to SU01 via BAPI_USER_CHANGE for automated provisioning. Single Sign-On (SSO) configurations use SM59 trust relationships and X.509 certificates. In S/4HANA, Fiori app authorization uses both ABAP backend roles and Fiori catalog/group assignments (PFCG + Fiori Launchpad configuration).
