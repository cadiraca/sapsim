# SKILL: MM — Materials Management & Procurement

## Core Concepts

SAP MM covers the Procure-to-Pay (P2P) process: from requisitioning through purchasing, goods receipt, invoice verification, and payment. It also manages inventory, material master data, and vendor evaluation.

**Key MM sub-areas:**

- **Purchasing**: Purchase Requisitions (PR), Request for Quotation (RFQ), Purchase Orders (PO), Contracts, Scheduling Agreements, Source Lists
- **Inventory Management (IM)**: Goods Receipts (GR), Goods Issues (GI), stock transfers, physical inventory
- **Logistics Invoice Verification (LIV)**: MIRO — 3-way match (PO + GR + Invoice), tolerance checks, evaluated receipt settlement (ERS)
- **Material Master**: Central data object for all materials. Organized by views (Basic Data, Purchasing, Accounting, MRP, Storage, etc.) and maintained at multiple org levels (client, plant, storage location)
- **Vendor Master (Business Partner in S/4HANA)**: General data + company code data + purchasing org data. In S/4HANA, suppliers are managed as Business Partners (BP transaction).

Key organizational elements: Purchasing Organization, Purchasing Group, Plant, Storage Location, Valuation Area (usually = Plant).

Inventory valuation methods: Moving Average Price (MAP — price control V) for raw materials; Standard Price (price control S) for finished/semi-finished goods. The choice is made in the material master Accounting view and is hard to change after GRs exist.

## Key Transactions / Technical Details

| T-Code | Purpose |
|--------|---------|
| **ME51N / ME52N / ME53N** | Create / Change / Display Purchase Requisition |
| **ME21N / ME22N / ME23N** | Create / Change / Display Purchase Order |
| **ME31K / ME32K** | Create / Change Contract |
| **ME31L / ME32L** | Create / Change Scheduling Agreement |
| **MIGO** | Goods Movement (GR, GI, transfer, reversal — supersedes MB01/MB1A/MB1B) |
| **MB52 / MB51** | Warehouse stock / Material document list |
| **MIRO / MIR7** | Enter / Park Logistics Invoice |
| **MR8M** | Cancel Invoice Document |
| **MI01 / MI04 / MI07** | Create / Enter / Post Physical Inventory |
| **ME2M / ME2L / ME2N** | Purchase orders by material / vendor / number |
| **MM01 / MM02 / MM03** | Create / Change / Display Material Master |
| **MK01 / XK01 / BP** | Create Vendor (old) / Create Vendor centrally / Business Partner (S/4HANA) |
| **OMJJ** | Customize movement types |
| **OBYC** | Automatic account determination |

Key tables: **EKKO/EKPO** (PO header/line), **EKET** (PO delivery schedule), **EBAN** (Purchase Requisition), **MKPF/MSEG** (material document header/line), **RBKP/RSEG** (Invoice document header/line), **MARA/MARC/MARD/MBEW** (material master general/plant/storage location/valuation), **LFA1/LFB1/LFM1** (vendor master general/company code/purchasing org).

## Common Challenges

- **Business Partner migration**: In S/4HANA, all vendors must be maintained as Business Partners (BP). Migrating from the old LFA1/LFB1 model to BP requires the BP-to-vendor synchronization to be active and all legacy vendors converted. Missing BP assignments cause purchasing to fail at PO creation.
- **Material master views and org levels**: Extending a material to a new plant requires maintaining all relevant views. Missing MRP, Accounting, or Storage views cause downstream failures.
- **GR/IR clearing**: If GRs and invoices don't match (quantity differences, price differences), the GR/IR account (usually mapped to BSX/WRX in OBYC) gets stuck. Regular GR/IR clearing (F.13 or MR11) is needed.
- **Moving average price issues**: Negative stocks, backdated GRs, and invoice reversals can corrupt MAP valuation. Strict process controls are needed (no negative stock allowed is a best practice).
- **Account determination (OBYC)**: The matrix of valuation class × transaction event key → G/L account must be fully configured and tested. Missing entries cause posting errors at GR.
- **Release strategies**: PR/PO release (approval workflow) configuration via characteristics and classes (CL01/CT04) is often underestimated in complexity.

## Best Practices

- Define the material master structure (views, number ranges, material types) in the first Explore workshop — it affects every other module.
- Activate Business Partner framework from day one in S/4HANA; do not defer vendor migration.
- Run the automatic payment program (F110) tests with real vendor bank data in QAS — don't discover payment method gaps at go-live.
- Configure and test evaluated receipt settlement (ERS) for high-volume vendors to eliminate manual invoice entry.
- Use purchasing info records and source lists to control which vendors can supply which materials — prevents maverick buying.
- Test MIGO with every relevant movement type (101 GR, 122 Return to vendor, 201 GI to cost center, 301 Plant transfer, 551 Scrapping) in QAS before go-live.
- Run physical inventory configuration and test before go-live — it's often forgotten until the first fiscal year-end.

## Integration Points with Other Modules

- **MM → FI**: Every goods movement posts an accounting document. OBYC controls which G/L accounts receive the postings. GR creates stock account debit + GR/IR credit; Invoice (MIRO) creates GR/IR debit + vendor payable credit.
- **MM → CO**: Purchase orders with account assignment category K (cost center), F (order), or P (project WBS) post directly to CO objects at GR.
- **MM → PP**: PP generates planned orders and purchase requisitions via MRP (MD01/MD02). Raw material procurement is triggered by production demand.
- **MM → SD**: Stock availability in SD is driven by MM inventory positions. Cross-company sales require inter-company purchasing org setup.
- **MM → WM/EWM**: Goods receipts in MM trigger transfer order creation in WM/EWM for putaway. Goods issues for production or delivery require WM pick transfer orders.
- **MM → QM**: Quality inspection lots can be triggered by goods receipts (movement type 101) if QM is active for the material/plant combination.
