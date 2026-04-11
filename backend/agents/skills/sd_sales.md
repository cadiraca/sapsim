# SKILL: SD — Sales & Distribution

## Core Concepts

SAP SD covers the Order-to-Cash (O2C) process: from customer inquiry through quotation, sales order, delivery, goods issue, billing, and cash collection. It manages pricing, credit, and the customer-facing logistics chain.

**Key SD sub-areas:**

- **Sales (VA)**: Inquiry → Quotation → Sales Order → Returns. Document types define the behavior (OR = standard order, RE = returns, CS = cash sales, etc.).
- **Shipping (VL)**: Delivery document creation, picking (WM/EWM integration), packing, goods issue posting. Outbound delivery is the bridge between SD and MM/WM.
- **Billing (VF)**: Invoice creation from deliveries or orders, credit/debit memos, pro-forma invoices. Billing posts the FI revenue document via account determination (VKOA).
- **Pricing**: The condition technique — condition types, condition tables, access sequences, pricing procedures. Prices, discounts, surcharges, taxes, and freight are all conditions.
- **Credit Management**: SAP FSCM Credit Management (S/4HANA standard) or classic FI-AR credit management. Credit checks on sales orders against customer credit limit.

Key organizational elements: Sales Organization, Distribution Channel, Division (together = Sales Area), Sales Office, Sales Group. These determine which customers, materials, and pricing are applicable.

Customer master is now a Business Partner (BP) in S/4HANA. Sold-to, ship-to, bill-to, and payer can be the same BP or different ones (partner functions).

## Key Transactions / Technical Details

| T-Code | Purpose |
|--------|---------|
| **VA01 / VA02 / VA03** | Create / Change / Display Sales Order |
| **VA11 / VA21** | Create Inquiry / Quotation |
| **VL01N / VL02N / VL03N** | Create / Change / Display Outbound Delivery |
| **VL10A / VL10C** | Delivery due list (by sales orders / purchase orders) |
| **VF01 / VF02 / VF03** | Create / Change / Display Billing Document |
| **VF04** | Billing due list — process all billable items |
| **VK11 / VK12 / VK13** | Create / Change / Display Condition Records |
| **VKOA** | Account determination: billing → FI G/L accounts |
| **VOV8** | Sales document type configuration |
| **VTLA / VTFL** | Copy controls (order→delivery / delivery→billing) |
| **FD32 / UKM_MY_APPLICATIONS** | Classic / FSCM credit limit maintenance |
| **VD01 / VD02 / BP** | Create Customer / Business Partner (S/4HANA) |
| **SD11** | Data model display (SD tables reference) |
| **VBAK / VBAP** | Sales document header / line display (SE16N) |

Key tables: **VBAK/VBAP** (sales order header/line), **VBFA** (document flow — tracks all related documents), **LIKP/LIPS** (delivery header/line), **VBRK/VBRP** (billing header/line), **KONV** (pricing conditions per document), **KNVV** (customer master sales area data), **KNA1/KNVP** (customer general data / partner functions), **T685T** (condition types), **PRCD_ELEMENTS** (new pricing table in S/4HANA 1809+).

## Common Challenges

- **Pricing procedure determination**: The combination of sales area + customer pricing procedure + document pricing procedure must resolve to exactly one pricing procedure. Incorrect determination leads to wrong pricing or missing conditions.
- **Condition record maintenance**: Pricing hierarchies (customer group → customer → material) must be defined clearly. Gaps cause orders to price at zero or fall back to incorrect levels.
- **Output determination (messages)**: Order confirmations, delivery notes, invoices — all driven by condition technique. Printer and email output requires careful configuration and testing.
- **Copy controls**: The controls from order to delivery to billing define which fields are copied and how quantities are handled. Missing or incorrect copy control configuration causes billing errors (billing quantity = 0, missing references).
- **Credit management integration**: Credit checks that are too strict block legitimate orders; too lenient and credit risk exposure grows. FSCM credit management requires separate Customizing and master data setup.
- **Revenue recognition**: Complex scenarios (milestone billing, service orders) require Revenue Accounting and Reporting (RAR/IFRS 15) configuration — often underestimated.
- **Returns and credit memo process**: The flow RE → return delivery (LR) → credit memo (RE billing) requires specific document types and copy controls. Often broken in Realize testing.

## Best Practices

- Define the pricing procedure and condition type list in the first SD workshop — changes during Realize are expensive.
- Use the document flow (VBFA) constantly for debugging — it shows every related document from inquiry to payment.
- Test the billing due list (VF04) with batch processing early — manual VF01 per order does not scale in production.
- Configure output (forms/emails) in parallel with configuration, not as a final step before go-live.
- Validate account determination (VKOA) for every revenue type, every tax scenario, every company code — one missing entry causes billing to fail with a hard error.
- Agree on the credit management strategy (FSCM vs. classic) at the start of the project — switching late requires significant rework.
- Run the full O2C cycle end-to-end (order → delivery → goods issue → billing → FI posting → AR → payment) in every integration test cycle.

## Integration Points with Other Modules

- **SD → FI**: Billing document (VF01/VF04) creates FI revenue and tax posting via VKOA account determination. Customer open item in AR.
- **SD → MM**: Outbound delivery goods issue (VL02N → Post Goods Issue) creates MM material document and reduces inventory. Availability check (ATP) reads MM stock.
- **SD → CO-PA**: Revenue and deductions transfer to CO-PA at billing for profitability reporting. Condition types are mapped to CO-PA value fields.
- **SD → WM/EWM**: Delivery triggers pick transfer order creation in WM/EWM. Confirmed pick quantity flows back to delivery.
- **SD → PP**: Sales orders can trigger MPS/MRP (make-to-order strategy). Planned orders are created for production to fulfill the sales order requirement.
- **SD → Credit (FSCM)**: Credit check at sales order save and delivery creation. Released credit blocks via FD32 or UKM workflow.
