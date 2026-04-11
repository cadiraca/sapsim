# SKILL: WM/EWM — Warehouse Management

## Core Concepts

SAP offers two warehouse management solutions: classic **WM (Warehouse Management)** embedded in SAP ECC/S/4HANA, and **EWM (Extended Warehouse Management)** — a more powerful system available as decentralized EWM or embedded EWM in S/4HANA. SAP's roadmap recommendation for new implementations is Embedded EWM.

**Classic WM concepts:**

- **Warehouse Number**: Top-level WM organizational unit. Linked to plant + storage location in MM.
- **Storage Type**: Physical area within the warehouse (high-rack, bulk storage, goods receipt zone, picking area). Each has capacity check rules, putaway and picking strategies.
- **Storage Section**: Subdivision of a storage type for further organization (fast-movers vs. slow-movers).
- **Storage Bin**: The physical bin location (like a shelf coordinate: R01-01-01). The atomic unit of stock placement.
- **Transfer Order (TO)**: The WM execution document. Every stock movement within the warehouse creates a TO. Must be confirmed to complete the movement.
- **Transfer Requirement (TR)**: Request for a movement, generated from MM GR/GI. The TO is created from the TR.
- **Quant**: A stock record within a bin — material + batch + quantity at a specific bin.

**EWM additional concepts:**
- **Warehouse Order (WO)**: Groups multiple transfer orders/tasks for a warehouse worker.
- **Handling Units (HU)**: Packaging structure — pallets, boxes, cartons. HU management tracks packaging material.
- **Wave Management**: Groups deliveries into waves for optimized picking.
- **Yard Management**: Controls truck dock assignments and yard movements.
- **Labor Management**: Tracks worker productivity and time per task.
- **RFUI / RF Framework**: Radio frequency / mobile device integration for warehouse floor operations.

## Key Transactions / Technical Details

**Classic WM:**

| T-Code | Purpose |
|--------|---------|
| **LT01 / LT0A** | Create Transfer Order manually / for TR |
| **LT1A / LT0E** | TO for delivery (inbound / outbound) |
| **LT12** | Confirm Transfer Order |
| **LB01 / LB10** | Create / Display Transfer Requirement |
| **LS01N / LS03N** | Create / Display Storage Bin |
| **LI01 / LI04 / LI20** | Create / Enter / Post WM Inventory |
| **LS26** | Warehouse stock overview (by material) |
| **LX01 / LX02** | Empty bins list / Bin stock list |
| **LS33** | Display Quant |
| **OMB4** | Storage type search strategies configuration |

**Embedded EWM (S/4HANA):**

| T-Code / App | Purpose |
|--------|---------|
| **/SCWM/MON** | EWM Monitor — central operations screen |
| **/SCWM/TO** | Display/manage Transfer Orders |
| **/SCWM/TRMON** | Transfer Request Monitor |
| **/SCWM/WRKC** | Work Center management |
| **/SCWM/RFUI** | RF User Interface framework |
| **/SCWM/HUID** | Handling Unit management |
| **/SCWM/WAVE** | Wave management |

Key tables (WM): **LGKO** (warehouse number header), **LGPLA** (storage bin master), **LGPL** (quant), **LQUA** (quant data), **LTAP** (transfer order item), **LTBP** (transfer requirement item), **VBBE** (SD delivery requirements).

Key tables (EWM): **/SCWM/AQUA** (quant), **/SCWM/ORDIM** (warehouse order items), **/SCWM/T_HUSID** (handling units).

## Common Challenges

- **WM-MM interface design**: The decision of which storage locations are WM-managed (linked to warehouse number) vs. non-WM-managed must be made early. Changing this post go-live is highly disruptive.
- **Putaway and picking strategy configuration**: Many customers assume they can fine-tune strategies after go-live. In reality, strategy changes require bin-level reclassification and process retraining.
- **Transfer order confirmation gaps**: If warehouse staff confirm TOs in the system late (or not at all), WM and MM stock are out of sync. This is one of the most common go-live issues.
- **Handling Unit complexity**: HU-managed warehouses require receiving, putaway, picking, and shipping processes to all reference the HU consistently. Missing HU handling in one step breaks the chain.
- **RF device configuration**: Mobile device screens must be designed and tested with actual hardware and wifi infrastructure. Last-minute RF issues on go-live are a classic nightmare.
- **EWM vs. WM decision**: Some customers start with WM and plan to "upgrade to EWM later." This is a full reimplementation, not an upgrade. Make the decision before configuration starts.

## Best Practices

- Conduct a physical warehouse walk-through with the WM consultant before any configuration begins — warehouse logic cannot be designed from a spreadsheet.
- Define storage type and bin structure to match physical reality, not an ideal future state. Start realistic.
- Test the RF device flows (receive, putaway, pick, pack, ship) with actual scanners on the actual wifi network during SIT — not just desktop simulation.
- Align WM Transfer Order confirmation with the shift structure. If shifts don't confirm TOs at end of shift, MRP and SD availability checks will be wrong the next morning.
- For EWM: implement wave management only if the warehouse volume justifies it. Complexity without volume is maintenance overhead without benefit.
- Run a physical inventory pilot in the test environment before go-live — it validates bin structure and stock data accuracy.

## Integration Points with Other Modules

- **WM/EWM → MM**: Goods receipt (MIGO 101) triggers Transfer Requirement → TO creation for putaway. Goods issue (MIGO 261) requires TO creation and confirmation before MM stock is reduced. Stock values in MM reflect WM-managed stock.
- **WM/EWM → SD**: Outbound delivery (VL01N/VL10) triggers WM pick TO. Pick confirmation updates delivery picked quantity. Post Goods Issue is blocked until TO is confirmed.
- **WM/EWM → PP**: Component staging for production orders creates internal WM movements from storage to production supply area. Finished goods receipt posts to WM-managed bins.
- **WM/EWM → QM**: Quality inspection stock is managed in a dedicated WM storage type (e.g., quality inspection area). Release from QM moves stock to unrestricted-use storage type via TO.
- **EWM → TM (Transportation Management)**: EWM integrates with SAP TM for inbound/outbound shipment planning, dock scheduling, and carrier collaboration.
- **EWM → Yard Management**: Trucks check in at yard, dock assignment is managed, and EWM coordinates unloading/loading with the warehouse execution processes.
