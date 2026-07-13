# Pharmacy Management System (PMS) — Nepal Edition

**Master Specification Document**  
_Version 1.0 — July 2026_

---

## Table of Contents

1. [Project Vision](#project-vision)
2. [Core Principles](#core-principles)
3. [Technology Stack](#technology-stack)
4. [Major Modules](#major-modules)
5. [Main Features](#main-features)
6. [Billing Workflow](#billing-workflow)
7. [Inventory Workflow](#inventory-workflow)
8. [Purchase Workflow](#purchase-workflow)
9. [Dashboard](#dashboard)
10. [Reports](#reports)
11. [User Roles](#user-roles)
12. [Database Overview](#database-overview)
13. [UI Guidelines](#ui-guidelines)
14. [Future Features](#future-features)
15. [Development Roadmap](#development-roadmap)

---

## Project Vision

### Purpose

The Pharmacy Management System (PMS) is a full-featured, offline-first desktop application purpose-built for retail pharmacies operating in Nepal. It replaces paper-based record keeping, memory-dependent expiry tracking, and manual billing with a modern, keyboard-friendly digital workflow. The software manages the entire lifecycle of pharmaceutical stock — from purchase order to patient sale — while ensuring regulatory compliance with Nepali pharmacy standards.

### Why Small Pharmacies Need It

Pharmacies in Nepal face unique operational challenges that generic inventory software does not address:

- **Expiry management is critical.** Medicines have short shelf lives, and selling expired stock endangers patients and invites legal action. Most small pharmacies rely on manual checking.
- **Batch tracking is mandatory.** Every medicine sold must be traceable to its supplier and batch number for recall scenarios.
- **FEFO dispensing is non-negotiable.** First Expired, First Out logic must be applied at every sale to minimize wastage.
- **Internet is unreliable.** A cloud-dependent POS system becomes useless when the connection drops. The system must work fully offline.
- **Low profit margins.** Expensive enterprise software is not an option. The system must be affordable and run on existing Windows hardware.
- **Nepali market dynamics.** Medicine names, dosages, manufacturers, and regulatory codes (e.g., DDA license numbers) follow Nepali conventions. Generic Western software fails here.

### Goals

| Goal | Description |
|------|-------------|
| **Zero learning curve** | A pharmacist should be productive within 15 minutes of first launch. |
| **Blazing fast billing** | Complete a 5-item sale in under 10 seconds using only the keyboard. |
| **100% offline operation** | Every feature works without internet. Internet is used only for optional AI scanning and future sync. |
| **Complete traceability** | Every medicine sold can be traced back to its purchase batch and supplier. |
| **Expiry zero tolerance** | No expired medicine ever reaches the counter. |
| **Professional output** | Invoices, reports, and labels look professional and comply with Nepali tax requirements. |
| **Single binary deployment** | PyInstaller packaging produces one `.exe` file. No Python runtime installation needed. |

---

## Technology Stack

| Component | Technology | Version | Rationale |
|-----------|-----------|---------|-----------|
| Language | Python | 3.11 | Excellent ecosystem, readable code, wide Windows support |
| GUI Framework | PySide6 (Qt Widgets) | 6.6+ | Mature, native-looking Windows widgets, fast rendering |
| Database | SQLite | 3.x | Zero-config, file-based, ACID-compliant, ideal for offline desktop |
| ORM | SQLAlchemy | 2.0+ | Robust, well-documented, powerful querying with SQLite |
| PDF/Printing | ReportLab | 4.x | Programmatic PDF generation for invoices and labels |
| Charts | Matplotlib | 3.8+ | Rich charting for analytics dashboard and reports |
| Packaging | PyInstaller | 6.x | Single-file `.exe` deployment, no Python dependency |
| Barcode | python-barcode / pillow | Latest | Generate and render barcodes on labels and invoices |
| OCR (optional) | Tesseract + pytesseract | Latest | Optional AI invoice text extraction |
| Search | Built-in SQLite FTS5 | 3.x | Full-text search for instant medicine lookup |

---

## Core Principles

### Fast

Every screen loads in under 500ms on a standard office PC. Search results appear as the user types (instant search). Billing actions commit in under 100ms. The application never feels sluggish.

### Simple

The UI surface is minimal. One screen per task. No buried menus. No configuration required to start billing. Defaults are sensible. Advanced features are hidden until needed.

### Reliable

The application never loses data. Every transaction is wrapped in a database transaction. Crashes during billing are recovered on restart. Automatic daily backups protect against corruption. SQLite's ACID compliance guarantees consistency.

### Offline First

Zero dependencies on internet connectivity. The database, the search index, the reporting engine — everything runs locally. The only feature that requires internet is the optional AI invoice scanner, and even that gracefully degrades when offline.

### Professional

Invoices match the quality of any commercial POS system. Reports are print-ready. The application window follows Windows 11 design language. Font sizes, spacing, and colors are deliberate, not accidental.

### Easy to Learn

Every action has a visible shortcut hint. Common workflows (bill, add stock, search) require no training. A built-in quick help overlay (F1) shows all keyboard shortcuts at a glance.

### Keyboard Friendly

Every interactive element is reachable via keyboard. Tab order follows logical workflow. All major actions have dedicated shortcuts (F2 = new bill, F3 = search, F4 = add stock, F5 = refresh, Ctrl+S = save, Esc = back). Power users never need the mouse during billing.

### Minimal Clicks

The most common workflow — billing a customer — requires exactly 5 actions: (1) type medicine name, (2) press Enter, (3) type quantity, (4) press Enter, (5) press F10 to print. No modal dialogs interrupt the flow.

### Modern UI

The interface uses a contemporary flat design with subtle shadows, rounded corners, smooth transitions, and an accent color scheme. Both dark and light themes are supported and can be toggled instantly. Icons are used consistently throughout.

---

## Major Modules

The system is organized into the following major modules. Each module corresponds to a top-level navigation item.

```
┌─────────────────────────────────────────────────────────────┐
│  Pharmacy Management System                                 │
├─────────────────────────────────────────────────────────────┤
│  [Dashboard] [Inventory] [Billing] [Purchases] [Suppliers]  │
│  [Reports] [Analytics] [Users] [Settings] [Backup]          │
└─────────────────────────────────────────────────────────────┘
```

### 1. Dashboard
The landing page. Provides an at-a-glance summary of the pharmacy's health — today's sales, profit, low stock alerts, expiring medicines, and quick-action buttons for common tasks. Non-interactive widgets update automatically every 30 seconds.

### 2. Inventory
The core medicine database. Add, edit, delete, search, and filter medicines. View stock levels, batch details, and purchase history for each item. Supports categories, manufacturers, and active/inactive status.

### 3. Billing (POS)
The point-of-sale module. Add items to a bill by searching or scanning barcodes. Auto-calculates totals, taxes, and discounts. Supports cash, card, and credit payments. Prints thermal or A4 invoices. Deducts stock in real time using FEFO logic.

### 4. Supplier Management
Maintain a directory of all suppliers with contact details, DDA license numbers, payment terms, and purchase history. Filter by active/inactive status.

### 5. Purchase Management
Record incoming stock from suppliers. Supports direct manual entry, supplier invoice import (via OCR), and partial receipts. Automatically updates inventory and batch records.

### 6. Reports
Pre-built reports for daily, weekly, monthly, and yearly periods. Covers sales, purchases, profit, inventory, expiry, and supplier performance. Exportable to PDF and CSV. Printable with one click.

### 7. Expiry Management
Dedicated module for managing near-expiry and expired stock. Color-coded alerts: yellow for 30 days, orange for 15 days, red for expired. Batch actions for marking expired stock as disposed or returned.

### 8. Low Stock Alerts
Configurable thresholds per medicine or globally. Medicines below threshold appear in dashboard alerts and in a dedicated list. Supports email/print notification for reordering.

### 9. Analytics
Visual analytics powered by Matplotlib. Sales trends, profit margins, category breakdowns, top-selling medicines, and seasonal patterns. All charts are interactive (zoom, pan, save as image).

### 10. Backup & Restore
One-click backup creates a timestamped copy of the SQLite database and configuration file. Restore from any backup file. Automatic daily backups with configurable retention period.

### 11. Settings
Application-wide configuration: pharmacy name, address, license numbers, tax rates, receipt format (thermal/A4), default low-stock threshold, backup schedule, theme (dark/light), language, currency symbol, and printer selection.

### 12. User Management
Create and manage user accounts with role-based permissions. Three roles: Admin, Pharmacist, Cashier. Supports password protection and session locking (Ctrl+L).

### 13. AI Invoice Scanner (Optional)
An experimental module that uses OCR (Tesseract) to scan supplier invoices and automatically populate purchase records. Requires internet for cloud-based OCR fallback, but can also work offline with local Tesseract.

### 14. Barcode Support
Generate barcodes for medicines. Scan barcodes during billing for instant item lookup. Print barcode labels for shelves. Supports Code 128 and EAN-13 formats.

---

## Main Features

### 1. Medicine Database

The central repository of all medicines. Each medicine record contains:

- **Generic Name** — e.g., Amoxicillin
- **Brand Name** — e.g., Amoxil
- **Dosage Form** — Tablet, Capsule, Syrup, Injection, Cream, Drops, Inhaler
- **Strength** — e.g., 500mg, 250mg/5ml
- **Category** — Antibiotic, Analgesic, Antihistamine, Vitamin, etc.
- **Manufacturer** — e.g., GSK, Sun Pharma, Cipla
- **Unit Type** — Strip, Bottle, Vial, Piece, Box
- **Packing Size** — e.g., 10 tablets/strip, 100ml/bottle
- **Re-order Level** — Minimum stock before alert triggers
- **Selling Price** — Base retail price per unit
- **Is Active** — Soft-delete; inactive items are hidden from billing but retained in database
- **DDA Schedule** — Classification per Nepal's Drug Act (A, B, C, D, E, F, G, H)
- **Barcode** — Unique barcode number for scanning
- **Created/Updated Timestamps**

The search bar supports real-time full-text search across generic name, brand name, manufacturer, and barcode. The user types and results filter instantly.

### 2. Batch Tracking

Each purchase adds one or more batches to a medicine. A batch record contains:

- **Batch Number** (from manufacturer)
- **Manufacturing Date**
- **Expiry Date**
- **Purchase Quantity**
- **Remaining Quantity** (deducted during sales)
- **Purchase Price per Unit**
- **Supplier ID**
- **Purchase Invoice Reference**
- **MRP** (Maximum Retail Price per Nepali regulations)

Batches are the atomic unit of inventory. When stock is sold, the system deducts from the soonest-expiring batch first (FEFO).

### 3. Instant Search

Every data table in the system (medicines, suppliers, sales, purchases) has an instant-search filter bar. The user types, and results are filtered in real time without pressing Enter. Search is case-insensitive and supports partial matching. The billing search additionally matches on barcode scans.

### 4. Category Management

Medicines are organized into categories. Categories are hierarchical (parent/child) to support grouping like:

```
Antibiotics
  ├── Penicillins
  ├── Cephalosporins
  └── Macrolides
Analgesics
  ├── Opioids
  └── NSAIDs
Vitamins & Supplements
```

Categories are used for reporting, filtering, and inventory organization. A medicine can belong to exactly one leaf-level category.

### 5. Supplier Management

Each supplier record contains:

- **Supplier Name**
- **Contact Person**
- **Phone Number** (mobile and landline)
- **Email Address**
- **Address** (full street address)
- **DDA License Number**
- **PAN / VAT Number** (for tax invoicing)
- **Payment Terms** (e.g., Net 30, Cash on Delivery)
- **Is Active**
- **Total Purchases To Date** (auto-calculated)
- **Notes**

Users can view purchase history for any supplier, including total value, last purchase date, and list of medicines supplied.

### 6. Billing (POS)

The POS interface is designed for speed. The layout is as follows:

```
┌──────────────────────────────────────────────────────────────┐
│  Customer: [________________]  Bill No: INV-20260713-0042    │
├────────────────────────────────┬─────────────────────────────┤
│  Search: [________________]    │  Bill Summary               │
│                                │  ───────────────────────    │
│  ┌─────────────────────────┐   │  Subtotal:    Rs 1,250.00   │
│  │ Medicine Name     Qty P │   │  Discount:    Rs   50.00    │
│  │ Amoxicillin 500mg  10 T │   │  Tax (13%):   Rs  156.00    │
│  │ Paracetamol 500mg  5 T  │   │  ───────────────────────    │
│  │ Vit. C Tablets     20 T │   │  TOTAL:       Rs 1,356.00    │
│  └─────────────────────────┘   │                             │
│                                │  [Cash] [Card] [Credit]     │
│  [F2: New] [F10: Print]       │                             │
│  [Esc: Remove] [F8: Pay]      │  Change: Rs 144.00           │
└────────────────────────────────┴─────────────────────────────┘
```

**Billing workflow (see [section 6](#billing-workflow) for full detail):**

1. Press F2 to start a new bill. Bill number is auto-generated.
2. Type medicine name or scan barcode in the search bar. Results appear instantly.
3. Select the medicine (arrow keys + Enter). Default quantity is 1.
4. Adjust quantity if needed (type number + Enter).
5. Repeat steps 2–4 for all items.
6. Press F8 to open the payment dialog. Select payment mode (Cash/Card/Credit).
7. Enter amount tendered (for cash). Change is calculated automatically.
8. Press F10 to print the receipt. Stock is deducted and FEFO is applied.
9. The bill is saved to the database and appears in the recent bills list.

Discounts can be applied per-item or to the entire bill. Tax rates are configurable in Settings. A grace period allows voiding bills within 5 minutes (requires manager authorization).

### 7. Receipt Printing

Supports two receipt formats:

- **Thermal Receipt (80mm or 58mm)** — For thermal printers. Compact, rolls-based. Contains pharmacy name, address, license numbers, item list, totals, payment details, and thank-you message.
- **A4 Invoice** — For laser/inkjet printers. Full-page format with company letterhead, itemized table, tax breakdown, and signature line. Suitable for institutional buyers.

Receipt templates are customizable via Settings. Variables like `{pharmacy_name}`, `{bill_no}`, `{date}`, `{items}` are replaced at print time.

### 8. Stock Deduction & FEFO

When a sale is confirmed, the system:

1. Groups all sold items by medicine ID.
2. For each medicine, retrieves all non-expired batches sorted by expiry date (ascending).
3. Deducts quantity from the soonest-expiring batch first.
4. If a batch is fully depleted, it is marked as `stock_out = True` but kept for historical reference.
5. If insufficient stock exists, the sale is blocked with a clear message: *"Only X units available for [medicine name]. Reduce quantity or remove item."*

This ensures that customers always receive medicines with the longest remaining shelf life for their consumption — a direct patient safety feature.

### 9. Purchase Entry

When new stock arrives:

1. User navigates to Purchases → New Purchase.
2. Select supplier from dropdown (or add new supplier inline).
3. Enter supplier invoice number and date.
4. For each medicine being purchased:
   a. Search/select the medicine.
   b. Enter batch number, manufacture date, expiry date.
   c. Enter quantity, purchase price per unit, and MRP.
   d. Optionally enter a discount or tax rate for this line.
5. The system auto-calculates the total purchase value.
6. On save:
   - A new purchase record is created.
   - New batch records are added to the inventory.
   - Stock quantities for each medicine are increased.
   - The supplier's purchase history is updated.

### 10. AI Invoice Scanner

An optional time-saving feature. The user clicks "Scan Invoice" and selects a scanned PDF or image of a supplier invoice.

The OCR engine extracts:
- Supplier name
- Invoice number and date
- Line items (medicine name, batch, expiry, quantity, rate, amount)

The extracted data is presented in a preview screen. The user verifies each line, corrects any misreads, and clicks "Import." The system then creates the purchase record and updates inventory automatically.

This is the **only** feature that may optionally use cloud-based OCR for higher accuracy. The feature degrades gracefully: if offline, it uses local Tesseract; if local Tesseract is not installed, the button is greyed out with a tooltip explaining why.

### 11. Expiry Management

The Expiry module provides a dedicated view of all batches approaching or past expiry.

- **Green zone** — More than 6 months until expiry
- **Yellow zone** — 30–90 days until expiry
- **Orange zone** — 15–30 days until expiry
- **Red zone** — Less than 15 days or expired

Users can:
- Filter by medicine, supplier, or date range
- Mark expired batches as "Disposed" or "Returned to Supplier"
- Generate an expiry report for regulatory compliance
- Print disposal certificates

Dashboard widgets show counts for each alert zone.

### 12. Low Stock Alerts

Each medicine has a configurable re-order level. When stock falls below this level:

- A red badge appears on the Dashboard and Inventory navigation icons
- The medicine appears in the Low Stock Alerts widget on the Dashboard
- The Inventory list highlights low-stock items in yellow
- A notification toast appears on application startup

Users can generate a "Re-order List" — a printable report of all low-stock medicines grouped by supplier, making phone ordering efficient.

### 13. Analytics Dashboard

Visual reports powered by Matplotlib embedded in PySide6 widgets:

- **Sales Trend** — Line chart of daily sales for the last 30 days
- **Profit Margin** — Bar chart showing profit by category
- **Top 10 Medicines** — Horizontal bar chart of best-selling items
- **Category Distribution** — Pie chart of sales by category
- **Expiry Forecast** — Gantt-style chart showing when batches expire
- **Monthly Comparison** — Side-by-side bar chart comparing current vs previous month

All charts are rendered as anti-aliased PNG images and embedded in the PySide6 window. Right-click context menus allow saving as PNG or copying to clipboard.

### 14. Backup & Restore

- **Manual Backup:** One click creates a `.pmsbak` file containing the SQLite database and `settings.json`. The file is timestamped and optionally compressed.
- **Scheduled Backup:** Configurable interval (daily, weekly, monthly). Backups are stored in a user-configurable directory. Old backups are auto-deleted based on retention setting.
- **Restore:** User selects a `.pmsbak` file. The system prompts for confirmation, then replaces the current database with the backup. A safety backup of the current database is created before restoration.
- **Auto-Recovery:** On application startup, if the database was not properly closed (detected via journal file), the system attempts automatic recovery and logs the event.

### 15. User Management

- **Create User:** Admin can add users with username, display name, password, and role.
- **Edit User:** Change display name, password, role, and active status.
- **Delete User:** Users are soft-deleted (deactivated) to preserve audit trail.
- **Session Lock:** Press Ctrl+L to lock the screen. Requires password to unlock. Useful when stepping away from the counter.
- **Login History:** View recent login attempts with timestamps and success/failure status.

### 16. Settings

All configurable settings are stored in `settings.json` and exposed through a single Settings dialog:

| Setting | Default | Description |
|---------|---------|-------------|
| Pharmacy Name | — | Printed on receipts |
| Pharmacy Address | — | Printed on receipts |
| Pharmacy PAN/VAT | — | Tax registration number |
| DDA License No. | — | Regulatory license number |
| Receipt Format | Thermal (80mm) | Thermal or A4 |
| Tax Rate | 13% | VAT/HST percentage |
| Default Discount | 0% | Default bill discount |
| Currency Symbol | Rs | Nepali Rupees |
| Low Stock Threshold | 10 | Default re-order level |
| Auto Backup | Daily | Frequency of automatic backups |
| Backup Retention | 30 days | Days to keep old backups |
| Theme | Light | Light or Dark |
| Language | English | Interface language |
| Printer | Default | Selected receipt printer |

---

## Billing Workflow

The following is the complete, step-by-step billing workflow from the moment a customer approaches the counter until the receipt is handed over.

### Step 1: Start a New Bill

- **Action:** Press **F2** or click the **New Bill** button.
- **System Response:** A new bill session begins. The left panel clears. A bill number is auto-generated in the format `INV-YYYYMMDD-XXXX` (e.g., `INV-20260713-0042`). The date/time is frozen at start time. The search bar receives keyboard focus.

### Step 2: Add Items to the Bill

- **Action:** Type the generic name, brand name, or barcode of the first medicine. The user does not press Enter to begin searching — results appear instantly.
- **System Response:** A dropdown list shows up to 20 matching medicines, including: brand name, generic name, strength, dosage form, available stock, and selling price. The first result is highlighted.
- **Action:** If the correct medicine is visible, press **Enter** to select it. If not, continue typing to refine the search, or use **Arrow Down** to select a lower result and press **Enter**.
- **Action:** After selecting the medicine, the default quantity (1) is shown. Type a different quantity if needed and press **Enter**.
- **System Response:** The item is added to the bill table with columns: S.No, Medicine Name, Batch No., Quantity, Rate, Discount %, Amount. The bill summary updates: subtotal, discount, tax, and total. The search bar clears and regains focus for the next item.
- **Repeat** for each additional medicine.

### Step 3: Adjust Items (Optional)

- **Action:** To remove an item, select it in the table and press **Delete** or **Esc**.
- **Action:** To change the quantity of an existing item, double-click the quantity cell, type the new value, and press **Enter**.
- **Action:** To apply a discount to the entire bill, press **F6** and enter a discount percentage or amount.

### Step 4: Process Payment

- **Action:** Press **F8** or click the **Pay** button.
- **System Response:** The payment dialog opens with the total amount displayed prominently.
- **Action:** Select payment mode: **Cash**, **Card**, or **Credit**.
  - **Cash:** Enter the amount tendered. The system calculates and displays the change.
  - **Card:** Enter the card reference number (optional).
  - **Credit:** Select a credit customer from the list (optional feature).
- **Action:** Press **Enter** or click **Confirm Payment**.

### Step 5: Automatic Stock Deduction

- At the moment of payment confirmation, the system executes the FEFO algorithm:
  1. For each sold medicine, fetch all batches with remaining stock > 0, sorted by expiry date (ascending).
  2. Deduct units from the soonest-expiring batch first.
  3. If a batch is fully depleted, mark it as stock_out = True.
  4. If stock is insufficient across all batches, the transaction is rolled back with an error message.
- **System Response:** A success sound plays (optional, configurable). The bill is saved to the database as `status = "completed"`.

### Step 6: Print Receipt

- **Action:** Press **F10** or click **Print**.
- **System Response:** The receipt is generated using ReportLab and sent to the configured printer. The thermal receipt includes:
  - Pharmacy name, address, phone, and license numbers (header)
  - Bill number, date, time
  - Itemized table with medicine, batch, qty, rate, amount
  - Subtotal, discount, tax, total
  - Payment mode and amount tendered
  - Change amount (if cash)
  - Thank-you message
  - Barcode of bill number (footer)
- **Action:** The bill is printed. The screen resets to a blank bill ready for the next customer.

### Step 7: Void a Bill (Within Grace Period)

- If a bill needs to be voided (e.g., customer returned), the user can find the bill in Recent Bills, select it, and click **Void**. This is only allowed within the configurable grace period (default 5 minutes). After that, only an Admin can void it. Voiding reverses the stock deduction by adding the quantities back to their respective batches.

---

## Inventory Workflow

### Adding a Medicine

1. Navigate to **Inventory → Add Medicine**.
2. Fill in the form fields:
   - **Generic Name** (required) — e.g., Amoxicillin
   - **Brand Name** (optional) — e.g., Amoxil
   - **Dosage Form** (dropdown) — Tablet, Capsule, Syrup, etc.
   - **Strength** — e.g., 500mg
   - **Category** (dropdown, select or create) — e.g., Antibiotics
   - **Manufacturer** (dropdown, select or create)
   - **Unit Type** (dropdown)
   - **Packing Size** — e.g., 10
   - **Re-order Level** (numeric)
   - **Selling Price** (numeric, required)
   - **DDA Schedule** (dropdown, optional)
   - **Barcode** (optional, can be auto-generated)
3. Click **Save**. The medicine is added to the database with `active = True`.
4. To immediately add stock, click **Add Stock** from the medicine detail view, which opens the Purchase flow.

### Editing a Medicine

1. Search for the medicine using the search bar.
2. Double-click the row or click **Edit**.
3. Modify any fields. Note: changing the selling price does not affect existing bills.
4. Click **Save**. A confirmation toast appears.

### Deleting (Deactivating) a Medicine

1. Search for the medicine.
2. Select the row and click **Delete**.
3. A confirmation dialog asks: *"Are you sure you want to deactivate [medicine name]? It will be hidden from billing and search but retained in records."*
4. Click **Confirm**. The medicine's `active` flag is set to `False`.
5. Deactivated medicines can be reactivated from the "Show Inactive" toggle in Inventory.

### Stock Updates

Stock is updated automatically during:
- **Purchase** — quantities increase
- **Sale** — quantities decrease (via FEFO)
- **Stock Adjustment** — manual correction for theft, damage, or counting errors. Requires a reason note.

To perform a manual stock adjustment:
1. Open the medicine detail view.
2. Click **Adjust Stock**.
3. Enter: new quantity, reason (e.g., "Damage during handling", "Inventory count correction"), and reference (optional).
4. The adjustment is logged and the stock is updated.

### Searching

- The inventory search bar supports real-time full-text search across: generic name, brand name, manufacturer, and barcode.
- As the user types, the table filters instantly. The search is case-insensitive and supports partial words.
- Search results can be sorted by clicking column headers.

### Filtering

- **Category** — dropdown filter to show only medicines in a selected category
- **Manufacturer** — dropdown filter
- **Stock Status** — All, In Stock, Low Stock, Out of Stock
- **Expiry Status** — All, Expiring Soon (30 days), Expired
- **Active Status** — Active, Inactive, All
- **DDA Schedule** — filter by controlled substance classification

Filters can be combined. A "Clear All Filters" button resets the view.

---

## Purchase Workflow

### Receiving Stock from a Supplier

1. Navigate to **Purchases → New Purchase**.
2. **Step 1 — Supplier Info:**
   - Select supplier from dropdown. The supplier's default payment terms and license numbers are shown.
   - Enter the supplier's invoice number and date.
3. **Step 2 — Add Items:**
   - Search and select a medicine.
   - Enter: batch number, manufacturing date, expiry date, quantity, purchase price per unit, MRP.
   - Optionally enter line-level discount and tax.
   - Click **Add to Purchase**.
   - Repeat for all items in the shipment.
4. **Step 3 — Review:**
   - Review the full purchase list. Quantities, prices, and totals are shown.
   - Edit or remove lines as needed.
5. **Step 4 — Save:**
   - Click **Save Purchase**.
   - The system creates purchase records, batch records, and updates inventory quantities atomically.
   - A purchase invoice number is auto-generated: `PO-YYYYMMDD-XXXX`.

### Partial Receiving

If a supplier ships only part of an order:

1. Create the purchase with the received quantities only.
2. Note in the "Notes" field that it is a partial receipt.
3. When the remaining stock arrives, create a new purchase referencing the same supplier invoice number.

### Manual Purchase Entry (Without Supplier)

Used for cash purchases at local distributors:

1. Select supplier as "Cash Purchase" (a built-in generic supplier).
2. Enter items normally.
3. The system records it as a cash purchase.

### AI Invoice Import

1. Click **Scan Invoice** in the Purchases module.
2. Select an image or PDF file.
3. The OCR engine processes the image and extracts:
   - Supplier name (matched against existing supplier list)
   - Invoice number and date
   - Line items with medicine names, batch numbers, expiry dates, quantities, and rates
4. A preview screen shows the extracted data with confidence scores.
5. The user:
   - Verifies each line
   - Corrects any misread fields
   - Matches medicine names to the existing database (or creates new medicines on the fly)
   - Clicks **Import**
6. The purchase is created. Inventory is updated. The user is returned to the Purchases list.

---

## Dashboard

The Dashboard is the home screen. It displays the following widgets in a grid layout. Each widget is a compact card with a title, value, and optional trend indicator.

### Widget Layout (4-column grid)

```
┌──────────────┬──────────────┬──────────────┬──────────────┐
│  Today's     │  Today's     │  Monthly     │  Inventory   │
│  Sales       │  Profit      │  Sales       │  Value       │
│  Rs 12,450   │  Rs 3,112    │  Rs 245,000  │  Rs 1.2M     │
│  ▲ 12% vs yd │  ▲ 8% vs yd  │  ▲ 15% vs lm │              │
├──────────────┴──────────────┴──────────────┴──────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │ Low Stock    │  │ Expiring     │  │ Top Selling      │ │
│  │ Alerts       │  │ Medicines    │  │ Medicines        │ │
│  │ 8 items      │  │ 5 items      │  │ 1. Amoxicillin   │ │
│  │ [View All]   │  │ [View All]   │  │ 2. Paracetamol   │ │
│  │              │  │              │  │ 3. Vit C         │ │
│  └──────────────┘  └──────────────┘  └──────────────────┘ │
├───────────────────────────────────────────────────────────┤
│  Recent Bills (last 10)                                    │
│  ┌──────┬────────────┬──────────┬────────┬────────┐       │
│  │ Bill │ Time       │ Items    │ Total  │ Status │       │
│  ├──────┼────────────┼──────────┼────────┼────────┤       │
│  │ 0042 │ 10:30 AM   │ 3        │ 1,356  │ Done   │       │
│  │ 0041 │ 10:15 AM   │ 5        │ 2,450  │ Done   │       │
│  └──────┴────────────┴──────────┴────────┴────────┘       │
└───────────────────────────────────────────────────────────┘
```

### Widget Descriptions

| Widget | Data Source | Description |
|--------|-------------|-------------|
| **Today's Sales** | Sales table, filtered by today's date | Sum of total amounts for all completed bills today. Shows percentage change vs yesterday. |
| **Today's Profit** | Sales & Purchase tables | (Selling Price - Purchase Price) × Quantity for all items sold today. |
| **Monthly Sales** | Sales table, filtered by current month | Sum of all completed bills this month. Shows percentage change vs last month. |
| **Inventory Value** | Batches table | Sum of (Remaining Quantity × Purchase Price) for all active batches. |
| **Low Stock Alerts** | Medicines & Batches | Count of medicines where total stock ≤ re-order level. Clicking opens the Low Stock report. |
| **Expiring Medicines** | Batches table | Count of batches expiring within 30 days. Clicking opens the Expiry Management module. |
| **Top Selling Medicines** | Sales Items table | Top 5 medicines by quantity sold this month. Shows med name and count. |
| **Recent Bills** | Sales table | Last 10 completed bills with bill number, time, item count, total, and status (Completed/Voided). |

### Quick Action Buttons

The Dashboard also has a toolbar with one-click actions:
- **New Bill** (F2) — Opens Billing module with a fresh bill
- **Add Medicine** — Opens Inventory → Add Medicine
- **New Purchase** — Opens Purchases → New Purchase
- **Backup Now** — Triggers an immediate backup

---

## Reports

All reports share a consistent interface:

1. **Select report type** from the left sidebar.
2. **Set date range** or filter parameters at the top.
3. **View the report** in the main area (table + optional chart).
4. **Export** to PDF or CSV.
5. **Print** directly.

### Available Reports

| Report | Description | Columns / Content |
|--------|-------------|-------------------|
| **Daily Report** | Summary of today's transactions | Total sales, total bills, total items sold, total profit, tax collected. Optional: itemized bill list. |
| **Weekly Report** | Aggregated data for the current or selected week | Day-by-day breakdown: sales, profit, bills count. Bar chart included. |
| **Monthly Report** | Full month summary | Daily totals table. Line chart of sales trend. Top 10 medicines. Category breakdown. |
| **Yearly Report** | Annual overview | Month-by-month comparison table. Year-over-year growth chart. Peak months highlighted. |
| **Inventory Report** | Current stock snapshot | Medicine name, batch, quantity, purchase price, selling price, expiry date, days until expiry, supplier. Filterable by category and stock status. |
| **Profit Report** | Profit breakdown by period | Total revenue, total cost, gross profit, profit margin %. Breakdown by category or by individual medicine. |
| **Supplier Report** | Supplier performance | Supplier name, total purchases, number of transactions, last purchase date, average delivery time (manual entry). |
| **Expiry Report** | Expiry analysis | Batch number, medicine, manufacturer, expiry date, quantity, days remaining, status (Good/Near/Expired). |
| **Purchase Report** | Purchase history | Purchase date, invoice number, supplier, item count, total value, payment status. |
| **Sales Report** | Detailed sales log | Bill number, date/time, cashier, item count, subtotal, discount, tax, total, payment mode, status. |

---

## User Roles

The system defines three user roles with progressively increasing permissions.

### Admin

Full access to every feature in the system.

- Can create, edit, and delete users
- Can view all reports and analytics
- Can void any bill (no grace period restriction)
- Can delete/void any transaction
- Can access Settings and modify system configuration
- Can perform stock adjustments
- Can restore backups
- Can view audit logs
- Can deactivate/reactivate medicines

### Pharmacist

Full operational access with restrictions on sensitive administrative actions.

- Can perform billing, add/edit medicines, manage purchases, generate reports
- Can view analytics and expiry data
- Cannot create or delete users
- Cannot access Settings or modify system configuration
- Cannot void bills older than 24 hours
- Cannot restore backups
- Can perform stock adjustments (subject to reason logging)

### Cashier

Limited to front-counter operations only.

- Can perform billing
- Can search medicines and view stock levels
- Can view today's sales widget on Dashboard
- Cannot add, edit, or delete medicines
- Cannot manage purchases or suppliers
- Cannot access reports, analytics, or users
- Cannot access Settings
- Cannot void bills (requires Admin/Pharmacist override)
- Cannot perform stock adjustments

### Permission Matrix

| Permission | Admin | Pharmacist | Cashier |
|------------|:-----:|:----------:|:-------:|
| Billing (POS) | ✅ | ✅ | ✅ |
| Search Medicines | ✅ | ✅ | ✅ |
| Add/Edit Medicines | ✅ | ✅ | ❌ |
| Deactivate Medicines | ✅ | ✅ | ❌ |
| Manage Purchases | ✅ | ✅ | ❌ |
| Manage Suppliers | ✅ | ✅ | ❌ |
| View Reports | ✅ | ✅ | ❌ (Dashboard only) |
| View Analytics | ✅ | ✅ | ❌ |
| Expiry Management | ✅ | ✅ | ✅ (view only) |
| User Management | ✅ | ❌ | ❌ |
| Settings | ✅ | ❌ | ❌ |
| Backup & Restore | ✅ | ❌ | ❌ |
| Void Any Bill | ✅ | ⚠️ (24hr limit) | ❌ |
| Stock Adjustments | ✅ | ✅ | ❌ |

---

## Database Overview

The database consists of the following tables. All tables use UUID primary keys for portability and future sync compatibility.

### Table: `medicines`

Stores the master list of all medicines.

- **id** — UUID, primary key
- **generic_name** — Text, required, indexed for full-text search
- **brand_name** — Text, optional
- **dosage_form** — Text (enum-like: Tablet, Capsule, Syrup, etc.)
- **strength** — Text, e.g., "500mg"
- **category_id** — Foreign key → `categories.id`
- **manufacturer_id** — Foreign key → `manufacturers.id`
- **unit_type** — Text (Strip, Bottle, Vial, etc.)
- **packing_size** — Integer, e.g., 10 (tablets per strip)
- **reorder_level** — Integer, default 10
- **selling_price** — Decimal (NPR)
- **dda_schedule** — Text, optional
- **barcode** — Text, unique, optional
- **is_active** — Boolean, default True
- **created_at** — DateTime
- **updated_at** — DateTime

### Table: `categories`

Hierarchical categories for classifying medicines.

- **id** — UUID, primary key
- **name** — Text, unique
- **parent_id** — Foreign key → `categories.id` (self-referential for hierarchy)
- **description** — Text, optional

### Table: `manufacturers`

Manufacturer/company directory.

- **id** — UUID, primary key
- **name** — Text, unique
- **contact** — Text, optional
- **address** — Text, optional

### Table: `batches`

Individual batches of medicine from purchases. This is the inventory table.

- **id** — UUID, primary key
- **medicine_id** — Foreign key → `medicines.id` (required)
- **batch_number** — Text, required
- **manufacturing_date** — Date
- **expiry_date** — Date, required, indexed
- **purchase_quantity** — Integer
- **remaining_quantity** — Integer (≥ 0)
- **purchase_price** — Decimal (per unit)
- **mrp** — Decimal (Maximum Retail Price)
- **supplier_id** — Foreign key → `suppliers.id`
- **purchase_id** — Foreign key → `purchases.id`
- **is_stock_out** — Boolean, default False
- **created_at** — DateTime

### Table: `suppliers`

Supplier directory.

- **id** — UUID, primary key
- **name** — Text, required
- **contact_person** — Text, optional
- **phone** — Text
- **email** — Text, optional
- **address** — Text
- **dda_license** — Text, optional
- **pan_vat** — Text, optional
- **payment_terms** — Text, optional
- **is_active** — Boolean, default True
- **notes** — Text, optional
- **created_at** — DateTime

### Table: `purchases`

Purchase transaction records.

- **id** — UUID, primary key
- **purchase_number** — Text, auto-generated, unique (PO-YYYYMMDD-XXXX)
- **supplier_id** — Foreign key → `suppliers.id`
- **supplier_invoice_no** — Text, optional
- **supplier_invoice_date** — Date
- **total_amount** — Decimal
- **discount** — Decimal
- **tax** — Decimal
- **net_amount** — Decimal
- **payment_status** — Text (Paid, Unpaid, Partial)
- **notes** — Text, optional
- **created_by** — Foreign key → `users.id`
- **created_at** — DateTime

### Table: `purchase_items`

Line items within a purchase.

- **id** — UUID, primary key
- **purchase_id** — Foreign key → `purchases.id`
- **medicine_id** — Foreign key → `medicines.id`
- **batch_number** — Text
- **manufacturing_date** — Date
- **expiry_date** — Date
- **quantity** — Integer
- **purchase_price** — Decimal
- **mrp** — Decimal
- **discount** — Decimal
- **tax** — Decimal
- **line_total** — Decimal

### Table: `sales`

Bill/sale transaction records.

- **id** — UUID, primary key
- **bill_number** — Text, auto-generated, unique (INV-YYYYMMDD-XXXX)
- **customer_name** — Text, optional
- **subtotal** — Decimal
- **discount** — Decimal
- **discount_type** — Text (Percentage, Fixed)
- **tax** — Decimal
- **tax_rate** — Decimal
- **total** — Decimal
- **payment_mode** — Text (Cash, Card, Credit)
- **amount_tendered** — Decimal
- **change_amount** — Decimal
- **status** — Text (Completed, Voided)
- **voided_at** — DateTime, nullable
- **voided_by** — Foreign key → `users.id`, nullable
- **created_by** — Foreign key → `users.id`
- **created_at** — DateTime

### Table: `sale_items`

Line items within a sale.

- **id** — UUID, primary key
- **sale_id** — Foreign key → `sales.id`
- **medicine_id** — Foreign key → `medicines.id`
- **batch_id** — Foreign key → `batches.id` (which specific batch was used)
- **quantity** — Integer
- **selling_price** — Decimal (price at time of sale)
- **purchase_price** — Decimal (cost at time of sale, for profit calc)
- **discount** — Decimal
- **line_total** — Decimal

### Table: `users`

User accounts for authentication and authorization.

- **id** — UUID, primary key
- **username** — Text, unique
- **display_name** — Text
- **password_hash** — Text (hashed with bcrypt or Argon2)
- **role** — Text (Admin, Pharmacist, Cashier)
- **is_active** — Boolean, default True
- **last_login** — DateTime, nullable
- **created_at** — DateTime
- **updated_at** — DateTime

### Table: `stock_adjustments`

Log of manual stock changes.

- **id** — UUID, primary key
- **medicine_id** — Foreign key → `medicines.id`
- **batch_id** — Foreign key → `batches.id`
- **previous_quantity** — Integer
- **new_quantity** — Integer
- **reason** — Text
- **reference** — Text, optional
- **adjusted_by** — Foreign key → `users.id`
- **created_at** — DateTime

### Table: `backups`

Backup history log.

- **id** — UUID, primary key
- **file_path** — Text
- **file_size_bytes** — Integer
- **type** — Text (Manual, Scheduled)
- **status** — Text (Success, Failed)
- **created_at** — DateTime

### Entity Relationships (Summary)

```
Medicine ──1:N──> Batch
Supplier ──1:N──> Purchase ──1:N──> PurchaseItem ──N:1──> Medicine
Purchase ──1:N──> Batch (batches created from this purchase)
Sale ──1:N──> SaleItem ──N:1──> Medicine
SaleItem ──N:1──> Batch (which specific batch was sold)
User ──1:N──> Sale (cashier)
User ──1:N──> Purchase (created by)
Medicine ──N:1──> Category
Medicine ──N:1──> Manufacturer
```

The critical relationship for FEFO is:

```
For a given Medicine → find all Batches where remaining_quantity > 0 AND expiry_date > today → sort by expiry_date ASC → deduct from earliest first
```

This is the core inventory intelligence of the entire system.

---

## UI Guidelines

### Design Language

The UI follows a **modern flat design** with subtle depth cues. It should feel professional but not decorative — every pixel serves a purpose.

### Color Palette

| Token | Light Theme | Dark Theme |
|-------|-------------|------------|
| **Primary** | `#1A73E8` (Blue) | `#4A9EFF` (Light Blue) |
| **Secondary** | `#34A853` (Green) | `#5CBF78` (Light Green) |
| **Danger** | `#EA4335` (Red) | `#FF6B5C` (Light Red) |
| **Warning** | `#FBBC04` (Amber) | `#FFD54F` (Light Amber) |
| **Background** | `#F5F5F5` (Light Gray) | `#1E1E1E` (Dark Gray) |
| **Surface** | `#FFFFFF` (White) | `#2D2D2D` (Card Gray) |
| **Text Primary** | `#212121` | `#E0E0E0` |
| **Text Secondary** | `#757575` | `#9E9E9E` |
| **Border** | `#E0E0E0` | `#404040` |

### Typography

- **Font Family:** Segoe UI (Windows native) with fallback to Arial and sans-serif
- **Base Size:** 14px (body text)
- **Scaling:** Modular scale with ratio 1.25
- **Headings:** 18px, 22px, 28px (H3, H2, H1)
- **Table Content:** 13px (for density)
- **Monospace:** Consolas for numeric columns and codes

### Component Standards

| Component | Height | Styling |
|-----------|--------|---------|
| Buttons | 36px | Rounded 6px, uppercase labels, hover lift effect |
| Text Inputs | 32px | Border 1.5px solid, rounded 4px, focus ring primary color |
| Dropdowns | 32px | Same as inputs, with chevron icon |
| Tables | Fill | Alternating row colors, header bold with sort arrows, selection highlight primary color |
| Cards | Auto | Background surface, rounded 8px, subtle shadow (0 1px 3px rgba(0,0,0,0.08)) |
| Dialogs | Min 300px | Centered, modal overlay with blur, rounded 12px corners, title bar with close button |
| Tabs | 36px | Underline style, active tab in primary color |
| Sidebar | 220px | Navigation icons + labels, active item highlighted |

### Layout Rules

- **Main Window:** Fixed 1280×800 minimum, maximizable, resizable with minimum size constraint of 1024×600
- **Navigation:** Vertical sidebar on the left with icons and labels. Current module highlighted.
- **Module Area:** The remaining space is devoted to the active module's content.
- **Toolbar:** Each module has a horizontal toolbar at the top with action buttons and filters.
- **Status Bar:** Bottom of window shows: current user, database status, last backup timestamp, bill counter.

### Responsive Behavior

The layout uses Qt's layout managers (QHBoxLayout, QVBoxLayout, QGridLayout) with stretch factors. When the window is resized:

- Tables expand/contract proportionally
- The sidebar remains fixed at 220px
- Dashboard widgets reflow from 4 columns to 2 columns if width < 1000px
- Dialogs are centered and maintain their minimum size

### Keyboard Navigation

| Shortcut | Action |
|----------|--------|
| `F1` | Show help overlay |
| `F2` | New bill (Billing module) |
| `F3` | Focus search bar (current module) |
| `F4` | Add new record (Inventory/Purchase) |
| `F5` | Refresh current view |
| `F6` | Apply discount (Billing) |
| `F8` | Process payment (Billing) |
| `F9` | Save current form |
| `F10` | Print receipt / report |
| `F11` | Toggle fullscreen |
| `F12` | Open Settings |
| `Ctrl+Q` | Quick search (global) |
| `Ctrl+L` | Lock session |
| `Ctrl+S` | Save |
| `Ctrl+P` | Print |
| `Ctrl+E` | Export (CSV/PDF) |
| `Ctrl+D` | Dashboard (home) |
| `Ctrl+N` | New (generic) |
| `Esc` | Go back / Cancel / Close dialog |
| `Delete` | Remove selected item |
| `Enter` | Confirm / Select |
| `Tab` | Next field |
| `Shift+Tab` | Previous field |

### Dark/Light Mode

- Toggle via **Settings → Theme** or quick toggle button in status bar
- All colors, icons, and surfaces switch instantly without restart
- Custom stylesheets in QSS (Qt Style Sheets) for both modes
- System default detection via Windows registry (optional)

### Animation & Micro-interactions

- **Button hover:** 0.2s ease opacity change or subtle lift
- **Navigation transition:** 0.15s ease slide
- **Toast notifications:** Slide down from top, auto-dismiss after 3 seconds
- **Search results:** Immediate (no animation — speed is priority)
- **Modal dialogs:** Fade in + scale 0.95→1.0 over 0.15s

---

## Future Features

These features are not part of the initial build but are planned for future releases.

### 1. Cloud Sync

Two-way synchronization with a cloud database (PostgreSQL) when internet is available. Allows multi-branch pharmacies to share inventory data. Sync is conflict-resolved with last-write-wins strategy.

### 2. Mobile App

A companion mobile application (Flutter/React Native) for:
- Viewing stock levels remotely
- Receiving low-stock push notifications
- Viewing sales reports
- Scanning barcodes with the phone camera
- **Not** for billing (billing remains desktop-only)

### 3. Online Backup

Automatic encrypted backups to cloud storage (Google Drive, Dropbox, or custom S3-compatible storage). Provides disaster recovery independent of local hardware.

### 4. Customer Loyalty

- Points-based loyalty program
- Customer database with purchase history
- SMS/email birthday reminders
- Discount coupons and promotional pricing

### 5. SMS Notifications

Integration with Nepal telecom providers for:
- Low-stock alerts to suppliers
- Expiry reminders to pharmacy owner
- Promotional messages to customers (opt-in)

### 6. Email Invoices

Email PDF invoices to customers automatically after billing. Supports Gmail SMTP, Outlook, or custom SMTP.

### 7. AI Business Assistant

A conversational AI interface (integrated as a chat panel) that can answer questions like:
- "What was our best-selling medicine last month?"
- "Which products are nearing expiry?"
- "Show me the sales trend for Amoxicillin this year"
- "Generate a purchase order for low-stock items"

---

## Development Roadmap

The project is divided into four phases. Each phase builds on the previous one.

### Phase 1: Core System (Weeks 1–8)

**Goal:** A working, shippable offline POS with inventory management.

| Week | Milestone |
|------|-----------|
| 1 | Project scaffolding. PySide6 main window with sidebar navigation. SQLite database setup via SQLAlchemy. Alembic migrations. |
| 2 | Medicine CRUD. Category & manufacturer management. Instant search. |
| 3 | Batch tracking. Stock management. FEFO logic. |
| 4 | Supplier management. Full-text search implementation. |
| 5 | Purchase management. Manual purchase entry. Stock updates on purchase. |
| 6 | Billing (POS) core workflow. Add items, calculate totals, payment dialog. |
| 7 | Stock deduction with FEFO during billing. Bill saving. Error handling. |
| 8 | Receipt printing (thermal + A4) via ReportLab. End-to-end billing test. |

**Deliverable:** A functional POS that can sell medicines, manage stock, and print receipts.

### Phase 2: Business Features (Weeks 9–14)

**Goal:** Reporting, analytics, user management, and backup.

| Week | Milestone |
|------|-----------|
| 9 | Dashboard widgets. Real-time data aggregation. Auto-refresh. |
| 10 | Reports module: Daily, Weekly, Monthly, Yearly. PDF/CSV export. |
| 11 | Inventory, Profit, Supplier, Expiry, Purchase, Sales reports. |
| 12 | Analytics module with Matplotlib charts. Sales trends, category breakdown, top medicines. |
| 13 | User management. Login, roles, permissions, session lock. |
| 14 | Backup & restore. Settings module. Theme support (dark/light). |

**Deliverable:** A complete business management tool with full reporting and user security.

### Phase 3: Advanced Features (Weeks 15–18)

**Goal:** Polish, barcode support, expiry management, and low-stock alerts.

| Week | Milestone |
|------|-----------|
| 15 | Barcode generation. Barcode scanning integration. Label printing. |
| 16 | Expiry management module. Color-coded alerts. Disposal/return workflow. |
| 17 | Low-stock alerts. Re-order list generation. Notification system. |
| 18 | UI polish. Performance optimization. Edge case handling. Testing. |

**Deliverable:** A production-ready application with professional features.

### Phase 4: AI Features (Weeks 19–22)

**Goal:** Optional AI-powered features for workflow acceleration.

| Week | Milestone |
|------|-----------|
| 19 | OCR setup (Tesseract). Image preprocessing. Text extraction pipeline. |
| 20 | AI Invoice Scanner UI. Supplier/matching logic. Preview and import workflow. |
| 21 | Error handling for OCR. Offline fallback. User testing and corrections. |
| 22 | Final testing, bug fixes, documentation, PyInstaller packaging. |

**Deliverable:** A complete, packaged Pharmacy Management System with optional AI scanning.

### Post-Launch

- User feedback collection
- Bug fixes and stability patches
- Begin work on Future Features (cloud sync, mobile app, etc.)

---

## Appendix: File Structure (Reference)

```
pharmacy-management/
├── main.py                      # Application entry point
├── requirements.txt             # Python dependencies
├── settings.json                # User configuration (auto-created)
├── database/
│   ├── connection.py            # SQLAlchemy engine & session
│   ├── models.py                # All ORM models
│   └── migrations/              # Alembic migration scripts
├── ui/
│   ├── main_window.py           # Main window with sidebar navigation
│   ├── styles/                  # QSS stylesheets for dark/light
│   ├── dashboard/               # Dashboard module
│   ├── inventory/               # Inventory module
│   ├── billing/                 # POS billing module
│   ├── purchases/               # Purchase management module
│   ├── suppliers/               # Supplier management module
│   ├── reports/                 # Reports module
│   ├── analytics/               # Analytics charts module
│   ├── expiry/                  # Expiry management module
│   ├── users/                   # User management module
│   ├── settings/                # Settings module
│   └── backup/                  # Backup & restore module
├── widgets/
│   ├── search_bar.py            # Reusable instant-search component
│   ├── data_table.py            # Reusable sortable/filterable table
│   ├── toast.py                 # Notification toast widget
│   └── card.py                  # Dashboard card widget
├── services/
│   ├── inventory_service.py     # Stock/Batch/FEFO business logic
│   ├── billing_service.py       # Sale creation and FEFO deduction
│   ├── purchase_service.py      # Purchase creation and stock update
│   ├── report_service.py        # Data aggregation for reports
│   └── backup_service.py        # Backup and restore logic
├── utils/
│   ├── bill_number.py           # Auto-generation of bill numbers
│   ├── receipt_generator.py     # ReportLab receipt PDF generation
│   ├── barcode_utils.py         # Barcode generation
│   ├── ocr_engine.py            # AI invoice OCR integration
│   └── validators.py            # Input validation helpers
├── assets/
│   ├── icons/                   # SVG/PNG icons for navigation
│   └── fonts/                   # Custom fonts (if needed)
└── dist/                        # PyInstaller output directory
```

---

*This document serves as the master specification for the Pharmacy Management System (PMS). All development decisions should reference this document. Updates and amendments must be documented in a new version with a changelog entry.*

---

**End of Document**