# SKILL: FI — Financial Accounting

## Core Concepts

SAP FI (Financial Accounting) is the external accounting module that records all financial transactions and produces statutory reporting. In S/4HANA, FI is deeply integrated with the Universal Journal (table **ACDOCA**), which consolidates all FI and CO postings into a single line-item table — eliminating the need for reconciliation between FI and CO.

**Key FI sub-modules:**
- **FI-GL**: General Ledger — chart of accounts, company codes, posting periods, financial statements
- **FI-AP**: Accounts Payable — vendor master, invoice processing, payment runs, dunning
- **FI-AR**: Accounts Receivable — customer master, billing integration, cash application, credit management
- **FI-AA**: Asset Accounting — fixed asset register, depreciation runs, asset transfers and retirements
- **FI-BL**: Bank Ledger / Bank Accounting — bank master data, payment methods, bank statement processing (MT940, CAMT.053)

**New GL** (available since ECC 6.0, standard in S/4HANA): enables parallel ledgers (e.g., IFRS + local GAAP), document splitting, and real-time CO-FI reconciliation.

Key configuration objects: Company Code, Chart of Accounts (CoA), Fiscal Year Variant, Posting Period Variant, Tolerance Groups, Document Types, Number Ranges.

## Key Transactions / Technical Details

| T-Code | Purpose |
|--------|---------|
| **FS00** | G/L account master (centrally) |
| **FB01 / FB60 / FB70** | Post G/L / vendor invoice / customer invoice |
| **F110** | Automatic Payment Program (APP) — payment run |
| **F-28 / F-32** | Post incoming payment / clear open items |
| **FB03 / FBL3N** | Display document / G/L line items |
| **FBL1N / FBL5N** | Vendor / Customer line item display |
| **F.07 / F-03** | Carry forward / manual G/L clearing |
| **FAGLB03** | G/L balances (New GL) |
| **AW01N** | Asset Explorer — individual asset view |
| **AFAB** | Depreciation run |
| **FF67 / FEBP** | Manual bank statement / Electronic bank statement |
| **OB52** | Open/close posting periods |
| **OBA7** | Document type configuration |

Key tables: **BKPF** (document header), **BSEG** (document line items — still relevant for legacy), **ACDOCA** (Universal Journal in S/4HANA), **LFA1/LFB1** (vendor master general/company code), **KNA1/KNB1** (customer master), **ANLA/ANLZ** (asset master), **SKA1/SKB1** (G/L account master).

## Common Challenges

- **Chart of Accounts alignment**: Global CoA vs. local CoA vs. country-specific CoA — getting this right early avoids painful rework. S/4HANA supports Group CoA and Operational CoA simultaneously.
- **Parallel ledgers configuration**: Setting up IFRS and local GAAP ledgers requires careful mapping of accounting principles and depreciation areas (FI-AA).
- **Document splitting**: A powerful but complex feature. Splitting rules must be defined per business transaction category, and incorrect setup causes imbalances in segment/profit center reporting.
- **Payment run (F110) tuning**: Incorrect payment method configuration, missing bank details on vendor master, or wrong due date logic leads to payment failures on go-live day.
- **Legacy data migration cutover**: Open items (AP/AR) must be migrated at balance level AND at open item level. Mismatches between total balance and sum of open items are a classic cutover issue.
- **Asset cutover**: Taking over assets mid-year requires careful handling of accumulated depreciation and posted depreciation values.

## Best Practices

- Define the Chart of Accounts and account groups in the first Explore workshop — everything downstream depends on it.
- Use substitution rules (transaction **OBBH**) to auto-populate profit center and segment from cost center assignments.
- Test the F110 payment run with real bank details in QAS before go-live — surprises on payment day are catastrophic.
- Reconcile ACDOCA totals with legacy trial balance at every migration trial load, not just the final cutover.
- Configure electronic bank statement (MT940/CAMT) processing early in Realize — manual bank statement entry does not scale.
- Set up meaningful tolerance groups and separate document types for automated vs. manual postings to simplify audit trails.

## Integration Points with Other Modules

- **MM → FI**: Goods Receipt triggers automatic posting to GR/IR clearing account (OBYC — transaction event key WRX). Invoice verification (MIRO) clears the GR/IR against vendor liability.
- **SD → FI**: Billing document (VF01) creates FI document automatically via account determination (VKOA). Revenue recognition is configured here.
- **PP → CO → FI**: Production order settlements post cost variances to FI-GL via CO-PA or cost center accounts.
- **FI-AA → FI-GL**: Depreciation run (AFAB) posts to G/L accounts defined in the asset class configuration (AO90).
- **CO → FI**: In S/4HANA, CO postings are real FI postings in ACDOCA — the reconciliation ledger is gone.
- **Treasury/TRM**: Bank accounts managed in FI-BL; cash management uses FI open items for liquidity forecasting.
