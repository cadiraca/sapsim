# SKILL: SAP Change Management (Organizational Change Management)

## Core Concepts

In SAP implementations, "Change Management" refers to **Organizational Change Management (OCM)** — the structured approach to transitioning people, processes, and culture to adopt new SAP-driven ways of working. This is distinct from IT change management (transport management). OCM is consistently cited as the top factor differentiating successful SAP go-lives from failed ones; Prosci research and SAP's own project retrospectives show that projects with excellent change management are 6x more likely to meet objectives.

SAP implementations don't just change software — they standardize and often fundamentally redesign business processes. Users who have operated legacy systems for years must unlearn existing habits and adopt SAP's process-driven paradigm. Resistance, workarounds, and low adoption rates are the primary OCM risks.

The **Prosci ADKAR model** is widely used in SAP contexts: Awareness (why change?), Desire (want to participate), Knowledge (how to change), Ability (demonstrate skills), Reinforcement (sustain the change). SAP Activate methodology (the official SAP implementation framework) includes OCM as a cross-cutting workstream across all project phases.

## Key Transactions / Tools

- **No dedicated SAP transaction for OCM** — this is primarily a project management and people-focused discipline.
- **SAP Enable Now**: SAP's learning content authoring and delivery platform. Creates simulations, step-by-step guides, and context-sensitive help embedded in the SAP Fiori UI.
- **SAP Learning Hub**: Cloud-based training platform for end-user and consultant training materials.
- **Solution Manager (CHARM)**: Change Request Management for IT change governance — separate from OCM but overlaps in project communication.
- **Fiori Launchpad**: UI configuration matters for OCM — a well-organized launchpad with role-appropriate tiles reduces user confusion at go-live.

## Common Challenges

**Stakeholder Resistance**: Department heads and power users often resist SAP implementations that reduce their operational autonomy or require process standardization. Early stakeholder mapping (influence vs. impact matrix) and executive sponsorship are critical mitigants.

**Insufficient Training**: End users trained too early forget before go-live; trained too late lack confidence. The optimal window is 2-4 weeks before go-live. Training should use the configured system, not a sandbox, so users practice real company codes, materials, and transaction codes they'll use on day one.

**Super-User Model Failure**: The "train the trainer" model fails when super-users are not given adequate time away from their regular jobs to support the OCM program. Super-users need 20-30% dedicated time during stabilization.

**Process Documentation Gaps**: When business process procedures (BPPs) are not finalized before training development begins, training content is created on unstable foundations and requires costly rework.

**Go-Live Fear**: Users default to legacy systems or manual workarounds when SAP feels uncertain. Clear communication of legacy system retirement dates removes the safety net and drives adoption.

## Best Practices

- Appoint a dedicated OCM Lead (not a technical consultant doubling as OCM) who reports to the project sponsor.
- Conduct stakeholder impact assessments at project start and refresh them before each phase transition.
- Build a change champion network: identify and engage informal influencers in each department — they are more trusted than management mandates.
- Develop role-based training curricula aligned to PFCG role design — users learn exactly what they will do, using their authorized transactions.
- Measure adoption post-go-live: track active user counts per module, error rates in key processes, and help-desk ticket volumes by category.

## Integration Points

OCM connects directly to project governance (steering committee communication), functional design (process changes drive training content), security (role design drives training audience segmentation), and testing (key users in UAT become super-users). SAP Enable Now integrates with Fiori Launchpad for contextual help, reducing the dependency on instructor-led training for routine SAP navigation questions. Hypercare planning (first 30-60 days post go-live) is an OCM deliverable that coordinates IT support, super-users, and business stakeholders.
