# Changelog

All notable changes to the Pharmacy Management System are documented here.

## [1.0.0] — 2026-07-14

### Task 2 — Project Foundation

#### Project Structure
- Created full directory tree: `app/core`, `app/ui/windows`, `app/ui/widgets`, `app/ui/pages`, `app/ui/dialogs`, `app/database`, `app/models`, `app/services`, `app/utils`, `app/resources/icons`, `app/resources/styles`, `tests`, `docs`, `logs`, `backups`
- Created `__init__.py` files for all Python packages

#### Files Created
- `main.py` — Application entry point
- `config.py` — Centralised, immutable application configuration
- `requirements.txt` — PySide6 and SQLAlchemy dependencies
- `CHANGELOG.md` — This file

#### Core
- `app/core/app.py` — Application bootstrapper (font, stylesheet, window launch)

#### UI — Widgets
- `app/ui/widgets/sidebar.py` — Left navigation sidebar with 9 labelled buttons
- `app/ui/widgets/header.py` — Top bar with app name, live clock, and logged-in user
- `app/ui/widgets/status_bar.py` — Bottom status bar with ready state, DB status, version

#### UI — Pages
- `app/ui/pages/welcome_page.py` — Welcome landing page with app info

#### UI — Windows
- `app/ui/windows/main_window.py` — Main window assembling sidebar, header, content stack, status bar

#### Resources
- `app/resources/styles/dark.qss` — Modern dark Catppuccin-style Qt stylesheet

#### Features Included
- Sidebar with Dashboard, Inventory, Billing (POS), Purchases, Suppliers, Reports, Analytics, Expiry, Settings
- Header with live date/time updating every second and logged-in user display
- Status bar with Ready message, Database: Not Connected, and Version
- Welcome page with Nepal flag, version, and welcome message
- Dark theme with rounded buttons, professional spacing, and readable fonts
- Window centered on screen, 1400x850 default, 1200x700 minimum

### Task 3 — Database Foundation

#### Modified Files
- `config.py` — Added `DATA_DIR`; `db_path` now points to `data/pharmacy.db`
- `app/core/app.py` — Added logging setup; calls `DatabaseManager.init_db()` before window launch
- `app/models/__init__.py` — Re-exports all 9 ORM models

#### Database Engine
- `app/database/engine.py` — Singleton SQLAlchemy engine, session factory, `new_session()` helper
- `app/models/base.py` — Shared `DeclarativeBase` for all models

#### ORM Models (9 tables)
- `app/models/medicine.py` — Medicine: name, generic, company, category, barcode, rack, min_stock, timestamps
- `app/models/batch.py` — Batch: batch_number, expiry_date, purchase/selling price, quantity; FK → Medicine
- `app/models/supplier.py` — Supplier: name, phone, email, address, PAN
- `app/models/purchase.py` — Purchase: supplier FK, invoice_number, date, total_amount
- `app/models/purchase_item.py` — PurchaseItem: purchase FK, batch FK, quantity, purchase_price
- `app/models/sale.py` — Sale: bill_number, date, total_amount, payment_method
- `app/models/sale_item.py` — SaleItem: sale FK, batch FK, quantity, selling_price
- `app/models/user.py` — User: username, password_hash, role, full_name
- `app/models/settings.py` — Settings: pharmacy_name, address, phone, PAN, default_theme

#### Relationships
- Medicine → has many Batches
- Supplier → has many Purchases
- Purchase → has many PurchaseItems
- Sale → has many SaleItems
- Batch belongs to Medicine
- PurchaseItem belongs to Purchase and Batch
- SaleItem belongs to Sale and Batch

#### Database Manager
- `app/database/manager.py` — `DatabaseManager.init_db()`: creates tables, seeds defaults (idempotent)

#### Seed Data (auto-created on first launch)
- Admin user: `admin` / `admin` (SHA-256 hashed)
- Default settings: pharmacy_name="My Pharmacy", default_theme="dark"

#### Behaviour
- `data/pharmacy.db` created automatically in `data/` directory
- All 9 tables created on first run
- Re-running does not duplicate seed data
- Application launches normally after database init

### Task 4 — Navigation System

#### New Files
- `app/ui/pages/base_page.py` — Reusable `BasePage` widget with icon, title, description layout
- `app/ui/pages/dashboard_page.py` — Dashboard page
- `app/ui/pages/inventory_page.py` — Inventory management page
- `app/ui/pages/billing_page.py` — Billing (POS) page
- `app/ui/pages/purchases_page.py` — Purchases page
- `app/ui/pages/suppliers_page.py` — Suppliers page
- `app/ui/pages/reports_page.py` — Reports page
- `app/ui/pages/analytics_page.py` — Analytics page
- `app/ui/pages/expiry_page.py` — Expiry management page
- `app/ui/pages/settings_page.py` — Settings page

#### Modified Files
- `app/ui/widgets/header.py` — Added `set_page_title()` method; title updates on navigation
- `app/ui/widgets/sidebar.py` — Kept existing structure; navigation signal drives page switching
- `app/ui/windows/main_window.py` — `PAGE_MAP` dict maps labels to page classes; `_create_pages()` instantiates all once; `_on_nav()` switches stack + header title
- `app/resources/styles/dark.qss` — Added `#PageTitle`, `#PageDescription` styles; sidebar `:pressed` state; active button hover/pressed variants

#### Navigation Architecture
- `QStackedWidget` holds all 9 pages (created once, never recreated)
- Sidebar emits `navigation_clicked(str)` signal
- `MainWindow._on_nav()` calls `stack.setCurrentWidget()` and `header.set_page_title()`
- Dashboard highlighted and shown by default on launch

#### Page Design
- Each page inherits `BasePage` with icon emoji, title, and description
- Professional spacing, centered layout, ready for future widgets

### Task 5 — Inventory Management (Part 1)

#### New Files
- `app/services/inventory_service.py` — `InventoryService` with full CRUD: `get_all`, `search`, `create`, `update`, `delete`
- `app/ui/dialogs/medicine_dialog.py` — `MedicineDialog` reusable add/edit dialog with field validation

#### Rewritten Files
- `app/ui/pages/inventory_page.py` — Complete inventory page with toolbar, table, search, empty state

#### Modified Files
- `app/resources/styles/dark.qss` — Added styles for `#ToolbarButton`, `#PrimaryButton`, `#SearchBox`, `QTableWidget`, `QHeaderView`, `#EmptyState`, `QDialog`, `QLineEdit`, `QSpinBox`, `QMessageBox`

#### Service Layer
- `InventoryService.get_all()` — returns all medicines ordered by name
- `InventoryService.search(query)` — case-insensitive search across name, generic, company, category, barcode
- `InventoryService.create(...)` — creates medicine; raises `DuplicateMedicineError` on conflict
- `InventoryService.update(id, ...)` — updates medicine; raises `DuplicateMedicineError` or `MedicineNotFoundError`
- `InventoryService.delete(id)` — deletes medicine; raises `MedicineInUseError` if batches exist
- All operations use real SQLite database, no in-memory storage

#### Dialog
- Add Medicine dialog with 7 fields (name required, others optional)
- Edit Medicine dialog pre-populated with existing data
- Validation: empty name blocked, negative stock blocked, duplicate name blocked
- Friendly `QMessageBox` error messages

#### Inventory Page
- Toolbar: Add Medicine, Edit, Delete, Refresh, Search box
- Sortable `QTableWidget` with 9 columns, column resizing, row selection
- Double-click to edit
- Instant search with 250ms debounce
- Empty state: "No medicines found." when no results
- All data persisted in SQLite via `InventoryService`

### Task 6 — Batch Management

#### New Files
- `app/services/batch_service.py` — `BatchService` with CRUD: `get_for_medicine`, `get_stock`, `create`, `update`, `delete`, `expiry_status`
- `app/ui/dialogs/batch_dialog.py` — `BatchDialog` add/edit dialog with validation

#### Modified Files
- `app/services/inventory_service.py` — `MedicineResult` now includes `total_stock` computed from batches; `get_all`/`search` eagerly load batches
- `app/ui/pages/inventory_page.py` — Split into medicine table (top) + batch table (bottom) via `QSplitter`
- `app/resources/styles/dark.qss` — Added `#SectionTitle`, `#StockLabel`, `#BatchTable`, `QDoubleSpinBox` styles

#### Batch Service
- `BatchService.get_for_medicine(id)` — returns batches sorted by expiry date (earliest first)
- `BatchService.get_stock(id)` — returns sum of all batch quantities
- `BatchService.create(...)` — creates batch; raises `DuplicateBatchError` on conflict
- `BatchService.update(id, ...)` — updates batch; raises `BatchNotFoundError` or `DuplicateBatchError`
- `BatchService.delete(id)` — deletes batch; raises `BatchInUseError` if used in sales
- `BatchService.expiry_status(date)` — returns "Good" / "Expiring Soon" / "Expired"

#### Batch Dialog
- Fields: Batch Number, Expiry Date (YYYY-MM-DD), Purchase Price (Rs.), Selling Price (Rs.), Quantity
- Validation: batch number required, expiry date valid format, selling < purchase triggers confirmation
- Duplicate batch numbers per medicine blocked

#### Inventory Page Redesign
- Split layout: medicine table (top 60%) + batch table (bottom 40%)
- Medicine table now shows "Stock" column (sum of batch quantities)
- Selecting a medicine loads its batches in the bottom section
- Batch toolbar: Add Batch, Edit, Delete, Refresh
- Expiry status color-coded: green (Good), yellow (Expiring Soon), red (Expired)
- Empty states for both tables

### Task 7 — Purchase Management

#### New Files
- `app/services/supplier_service.py` — `SupplierService` with CRUD: `get_all`, `search`, `get_by_id`, `create`, `update`, `delete`
- `app/services/purchase_service.py` — `PurchaseService` with `get_all`, `search`, `create_purchase`, `get_detail`
- `app/ui/dialogs/supplier_dialog.py` — `SupplierDialog` add/edit supplier with validation
- `app/ui/dialogs/new_purchase_dialog.py` — `NewPurchaseDialog` full purchase entry with header, items table, medicine search

#### Rewritten Files
- `app/ui/pages/purchases_page.py` — Purchase history table with toolbar, search, double-click detail view
- `app/ui/pages/suppliers_page.py` — Supplier management table with full CRUD + search

#### Modified Files
- `app/models/purchase.py` — Added `notes` field (Text, nullable)
- `app/database/manager.py` — Added `_migrate_columns()` for automatic schema evolution (adds missing columns to existing tables)
- `app/resources/styles/dark.qss` — Added `QComboBox`, `QDateEdit`, `QCalendarWidget` styles

#### Supplier Service
- `SupplierService.get_all()` — returns all suppliers ordered by name
- `SupplierService.search(query)` — searches across name, phone, email, PAN
- `SupplierService.get_by_id(id)` — returns single supplier
- `SupplierService.create(...)` — creates supplier; raises `DuplicateSupplierError`
- `SupplierService.update(id, ...)` — updates supplier; raises errors on not found or duplicate
- `SupplierService.delete(id)` — deletes supplier; raises `SupplierInUseError` if purchases exist

#### Purchase Service
- `PurchaseService.get_all()` — returns all purchases, newest first
- `PurchaseService.search(query)` — searches by invoice number
- `PurchaseService.create_purchase(...)` — transactional save: creates Purchase + PurchaseItems + Batches in single transaction; rolls back on error
- `PurchaseService.get_detail(id)` — returns full purchase detail with items and medicine names

#### New Purchase Dialog
- Header: Supplier (combo), Invoice Number, Invoice Date (calendar), Notes
- Items table: Medicine (with search), Batch Number, Expiry Date, Quantity, Purchase Price, Selling Price, Line Total
- Add Row, Duplicate Row, Delete Row buttons
- Auto-calculates line totals and grand total
- Medicine search across name/generic/barcode; auto-creates medicine if not found
- Full validation: supplier required, invoice required, at least one item, expiry/qty/price checks
- Selling price < purchase price triggers confirmation

#### Purchases Page
- Toolbar: New Purchase, Refresh, Search Invoice
- History table: Invoice, Supplier, Date, Items count, Total
- Double-click opens detail view (QMessageBox with formatted info)

#### Suppliers Page
- Full CRUD: Add, Edit, Delete, Refresh, Search
- Table: Supplier Name, Phone, Email, Address, PAN
- Delete blocked if supplier has purchases

### Task 8 — Billing (POS) System

#### New Files
- `app/services/billing_service.py` — `BillingService` with FEFO batch allocation, transactional sale creation, bill number generation, medicine search for POS
- `app/ui/dialogs/payment_dialog.py` — `PaymentDialog` for payment method selection and discount entry

#### Modified Files
- `app/models/sale.py` — Added `discount` (Float) and `vat_amount` (Float) fields
- `app/models/sale_item.py` — Added `discount` (Float) field
- `app/ui/pages/billing_page.py` — Complete rewrite: split POS layout with search, results cards, bill table, summary, payment flow
- `app/resources/styles/dark.qss` — Added `#MedicineCard`, `#BillTable` styles

#### Billing Service
- `BillingService.search_medicines(query)` — searches medicines with available (non-expired) stock
- `BillingService.get_fefo_batches(medicine_id)` — returns batches in FEFO order (earliest expiry first)
- `BillingService.create_sale(items, payment_method, discount, vat_rate)` — transactional: creates Sale + SaleItems + reduces batch quantities in single transaction; rolls back on error
- Auto-generates sequential bill numbers: `BILL-YYYYMMDD-0001`

#### Payment Dialog
- Payment method: Cash, Card, QR Payment, Credit
- Discount field (Rs. prefix, range limited to grand total)
- Live summary: "You Pay" updates on discount change
- Cancel / Complete Sale buttons

#### Billing Page (POS)
- Split layout: Left (medicine search + results cards) / Right (bill table + summary + actions)
- Medicine search with 250ms debounce, searches name/generic/company/barcode
- Medicine cards: clickable, shows name, generic, company, price, stock
- Click to add: single-batch adds directly with qty 1; multi-batch opens quantity picker dialog
- FEFO: earliest-expiry batch selected first
- Bill table: row number, medicine name, batch, quantity (inline QSpinBox), unit price, line total
- Quantity change auto-recalculates line totals and summary
- Summary: Subtotal, Discount, VAT (13% default), Grand Total
- Remove selected item (Delete key), Clear Bill (Ctrl+D with confirmation)
- Payment dialog triggered by "Pay" button or F8
- Sale completion shows bill number, total, payment method; clears bill
- Emits `sale_completed` signal with bill number and total

#### Keyboard Shortcuts
- `F4` — Focus search box
- `F8` — Open payment dialog
- `Delete` — Remove selected item
- `Ctrl+D` — Clear bill

### Task 9 — Receipt Printing & Billing Completion

#### New Files
- `app/services/receipt_service.py` — `ReceiptService` with ReportLab PDF generation for 58mm, 80mm thermal receipts and A4 invoices; system print support
- `app/services/sales_history_service.py` — `SalesHistoryService` with `get_all` and `search` for sales history queries
- `app/ui/dialogs/receipt_preview_dialog.py` — `ReceiptPreviewDialog` with PDF preview, paper size selection, save PDF, and print buttons
- `app/ui/pages/sales_history_page.py` — `SalesHistoryPage` with sales history table, search, double-click receipt preview, reprint

#### Modified Files
- `app/ui/dialogs/payment_dialog.py` — Added cash received field, change calculation, validation (cash >= total required)
- `app/ui/pages/billing_page.py` — Added Preview (Ctrl+P), Save PDF, Print (F10) buttons; receipt generation after sale; stores last sale bill number
- `app/ui/widgets/sidebar.py` — Added "Sales History" nav item after Billing (POS)
- `app/ui/windows/main_window.py` — Added `SalesHistoryPage` to PAGE_MAP
- `requirements.txt` — Added `reportlab>=4.0.0`

#### Receipt Service
- `ReceiptService.load_sale_data(sale_id, bill_number)` — loads sale, items, and pharmacy settings from DB
- `ReceiptService.generate_pdf(data, output, paper)` — generates PDF receipt in 58mm, 80mm, or A4 format
- `ReceiptService.print_pdf(pdf_path)` — sends PDF to system default printer (Windows: `os.startfile print`, macOS/Linux: `lpr`)
- Receipt includes: pharmacy name/address/phone/PAN, bill number, date/time, cashier, medicine table, subtotal/discount/VAT/grand total, payment method/cash/change, thank you footer
- Temp PDFs stored in system temp dir under `pms_receipts/`

#### Payment Dialog Updates
- Cash received field (QDoubleSpinBox, auto-set to grand total)
- Live change calculation (green when positive, red when remaining)
- Validation: cash received must be >= payable amount
- Cash-specific fields hidden for Card/QR/Credit methods

#### Billing Page Updates
- After sale completion: Preview, Save PDF, and Print buttons become enabled
- Preview opens `ReceiptPreviewDialog` with paper size selector
- Save PDF opens file dialog to choose save location
- Print sends 80mm receipt to system printer with confirmation
- Last sale bill number stored for receipt access

#### Sales History Page
- Table: Bill Number, Date, Items, Total, Payment Method
- Search by bill number with 250ms debounce
- Double-click or "Preview Receipt" button opens receipt preview
- "Reprint" button sends selected receipt to printer
- Empty state when no sales recorded
- Refresh button for manual reload

#### Keyboard Shortcuts
- `F10` — Print receipt (Billing page)
- `Ctrl+P` — Preview receipt (Billing page)
- `Ctrl+Shift+P` — Reprint selected receipt (Sales History page)

### Task 10 — Professional Dashboard

#### New Files
- `app/services/dashboard_service.py` — `DashboardService` with all read-only queries: top cards, charts, recent sales, low stock, expiry alerts

#### Modified Files
- `app/ui/pages/dashboard_page.py` — Complete rewrite: replaced placeholder with live dashboard containing KPI cards, Matplotlib charts, recent sales table, low stock panel, expiry panel
- `app/resources/styles/dark.qss` — Added `#DashboardCard` styles

#### Dashboard Service
- `DashboardService.get_top_cards()` — 8 KPI cards: Today's Sales, Today's Profit, Bills Today, Total Medicines, Inventory Value, Low Stock, Expiring (90d), Expired
- `DashboardService.daily_sales_last_7_days()` — bar chart data for last 7 days
- `DashboardService.monthly_sales_last_6_months()` — bar chart data for last 6 months
- `DashboardService.top_selling_medicines(limit)` — horizontal bar chart of top sellers by quantity
- `DashboardService.category_distribution()` — pie chart of medicines per category
- `DashboardService.recent_sales(limit)` — latest 10 bills with item counts
- `DashboardService.low_stock_medicines()` — medicines at or below minimum stock
- `DashboardService.expiring_medicines()` — batches expiring within 90 days + expired

#### Dashboard UI
- **Top cards**: 8 KPI cards in a 4-column grid with icon, value, and label; colour-coded accents
- **Charts**: 2x2 grid of Matplotlib figures embedded via `FigureCanvasQTAgg`; bar charts for daily/monthly sales and top sellers; pie chart for category distribution; charts resize with window
- **Recent sales table**: 10 most recent bills with Bill Number, Time, Items, Total, Payment; double-click opens receipt preview
- **Low stock panel**: table of medicines below minimum stock with current stock (red if zero, orange if low) and minimum stock columns
- **Expiry panel**: table of batches expiring within 90 days with colour-coded expiry dates (red <=30d, orange <=60d, yellow <=90d, green >90d)
- **Refresh button**: manually reloads all dashboard data
- **Auto-refresh**: dashboard reloads each time it becomes visible via `showEvent`

#### Performance
- All queries use efficient SQLAlchemy aggregations with `func.sum`, `func.count`, `func.coalesce`
- Charts rendered lazily on first load
- Dashboard loads in under 2 seconds for typical pharmacy datasets

### Task 11 — Reports & Analytics

#### New Files
- `app/services/reports_service.py` — `ReportsService` with all 10 report types, filter options, summary calculations, and CSV/Excel export

#### Modified Files
- `app/ui/pages/reports_page.py` — Complete rewrite: filter sidebar, summary cards, Matplotlib charts, sortable/searchable table, CSV and Excel export
- `app/ui/pages/dashboard_page.py` — Fixed missing `QHeaderView` import
- `app/resources/styles/dark.qss` — Added `#ReportFilterPanel` styles

#### Reports Service
- 10 report types: Daily Sales, Weekly Sales, Monthly Sales, Yearly Sales, Profit Report, Inventory Report, Low Stock Report, Expiry Report, Purchase Report, Top Selling Medicines
- `FilterParams` dataclass: date_from, date_to, medicine_id, supplier_id, category, payment_method
- `ReportResult` dataclass: headers, rows, summary, chart_labels, chart_values, chart_values2
- `ReportSummary` dataclass: total_sales, total_profit, total_bills, total_medicines_sold, avg_bill_value
- Filter option loaders: `get_medicine_options()`, `get_supplier_options()`, `get_category_options()`, `get_payment_methods()`
- `export_csv()` — writes report to CSV with summary section
- `export_excel()` — writes Excel-compatible XML spreadsheet with styled headers and summary

#### Reports UI
- **Filter sidebar**: Report type dropdown, date range (from/to date pickers), medicine/supplier/category/payment method combo boxes, Generate button
- **Summary cards**: 5 KPI cards — Total Sales, Total Profit, Bills, Medicines Sold, Avg Bill Value — colour-coded
- **Charts**: 2 Matplotlib bar charts — primary sales trend + secondary (profit or distribution); charts resize with window
- **Table**: Full sortable table with all report columns; right-aligned monetary columns; click header to sort; search bar to filter rows live
- **Export**: CSV and Excel buttons; Print button placeholder; record count display
- **Report types**: Each type shows appropriate columns and chart data (e.g. Profit Report shows Sales/Cost/Profit/Margin; Inventory Report shows stock values; Expiry Report colour-codes urgency)

---

## Task 12 — Expiry & Low Stock Management

**Date**: 2026-07-14

### Summary
Dedicated expiry and low stock pages with grouped alerts, colour-coded tables, filtering, CSV/Excel export, clickable dashboard cards, and startup warning dialogs.

### New Files
- `app/services/expiry_service.py` — `ExpiryService` with expired/expiring/low stock queries, filter options, summary counts, startup warnings, CSV/Excel export
- `app/ui/pages/low_stock_page.py` — `LowStockPage` with summary cards, category/company/out-of-stock filters, sortable table, export

### Modified Files
- `app/ui/pages/expiry_page.py` — Complete rewrite: `ExpiryPage` (QWidget) with 4 summary cards (Expired/Critical/Warning/Caution), status filter buttons, category/company dropdowns, sortable table with 9 columns, CSV/Excel export
- `app/ui/pages/dashboard_page.py` — Added `ClickableCard` class, `card_clicked` signal, `_CARD_NAV_MAP` for Low Stock/Expiring(90d)/Expired cards to navigate to dedicated pages
- `app/ui/widgets/sidebar.py` — Added "Low Stock" nav item with 📉 icon
- `app/ui/windows/main_window.py` — Added `LowStockPage` import, "Low Stock" to PAGE_MAP, wired `DashboardPage.card_clicked` signal to `_on_nav`
- `app/core/app.py` — Added startup warning dialogs: scans DB on launch, shows QMessageBox with expired/expiring/low stock items with detailed text

### Expiry Service
- `get_expiring_batches()` — all non-expired batches expiring within 90 days + already expired batches still in stock; filtered by category/company
- `get_expired_batches()` — only already-expired batches still in stock
- `get_expiry_summary()` — counts for Expired, Critical (≤30d), Warning (≤60d), Caution (≤90d) cards
- `get_low_stock_medicines()` — medicines where current stock ≤ minimum_stock; includes latest supplier name; filtered by category/company
- `get_low_stock_summary()` — counts for Out of Stock, Low Stock cards
- `get_startup_warnings()` — returns dict with expired, expiring_30, low_stock string lists for startup dialog
- `get_categories()` / `get_companies()` — filter option loaders
- `export_csv()` / `export_excel()` — generic table data export

### Expiry Page
- **Summary cards**: 4 cards — 🔴 Expired, 🟠 ≤30 Days (Critical), 🟡 ≤60 Days (Warning), 🟢 ≤90 Days (Caution) — each showing batch count and status label
- **Filter bar**: Category dropdown, Company dropdown, Status filter buttons (All/Expired/30d/60d/90d), Export CSV, Export Excel
- **Table**: 9 columns — Status, Medicine, Generic, Company, Category, Batch, Expiry, Qty, Selling Price; colour-coded status and expiry; sortable; shows count
- **Auto-refresh**: `showEvent` triggers `refresh()` via `QTimer.singleShot`

### Low Stock Page
- **Summary cards**: 3 cards — 📉 Total Low Stock, 🔴 Out of Stock, 🟠 Low Stock
- **Filter bar**: Category dropdown, Company dropdown, "Out of Stock Only" toggle, Export CSV, Export Excel
- **Table**: 8 columns — Medicine, Generic, Company, Category, Current Stock, Min Stock, Deficit, Latest Supplier; colour-coded stock (red=0, orange>0); sorted by deficit; sortable

### Dashboard Clickable Cards
- **Low Stock** card → navigates to "Low Stock" page
- **Expiring (90d)** card → navigates to "Expiry" page
- **Expired** card → navigates to "Expiry" page
- Clickable cards show pointer cursor on hover
- `card_clicked` signal wired from DashboardPage to MainWindow._on_nav

### Startup Warnings
- On app launch, `Application._show_startup_warnings()` runs after 200ms delay
- Scans DB for expired batches, batches expiring within 30 days, and low stock medicines
- Shows QMessageBox.warning with summary and detailed text (expandable)
- Truncated to 10 items per category in summary, full list in detailed text

---

## Task 13 — Settings & Configuration

**Date**: 2026-07-14

### Summary
Complete settings module with 6 sections: Pharmacy Info, Billing, Notifications, Appearance, Backup, and AI Settings. All settings persist in SQLite and load automatically on startup.

### New Files
- `app/services/settings_service.py` — `SettingsService` with load/save/reset, `AppSettings` dataclass, in-memory cache, `DEFAULTS` dict

### Modified Files
- `app/models/settings.py` — Expanded from 6 columns to 23 columns covering all 6 settings sections (pharmacy info, billing, notifications, appearance, backup, AI)
- `app/ui/pages/settings_page.py` — Complete rewrite from stub to full QWidget page with section navigation sidebar, stacked forms, save/reset/cancel buttons, input validation, status messages
- `app/core/app.py` — Added `_load_settings()` on startup, applies theme and font size from saved settings, respects notification enable/disable flags in startup warnings
- `app/resources/styles/dark.qss` — Added `#SettingsNavBtn`, `#SettingsContent`, `#SettingsSectionHeader`, and `QCheckBox` styles

### Settings Model — 23 Columns
- **Pharmacy Info (6)**: pharmacy_name, address, phone, email, pan_number, registration_number
- **Billing (5)**: default_vat, receipt_width, currency_symbol, receipt_footer, auto_print
- **Notifications (3)**: enable_expiry_warnings, enable_low_stock_warnings, expiry_warning_days
- **Appearance (2)**: default_theme, font_size
- **Backup (4)**: backup_folder, auto_backup_daily, auto_backup_weekly, max_backups
- **AI Settings (3)**: groq_api_key, groq_model, ocr_engine

### Settings Service
- `load()` — reads from DB, creates defaults if missing, returns `AppSettings` dataclass
- `get()` — returns cached settings (loads if not yet cached)
- `save(settings)` — persists to DB and updates cache
- `reset()` — resets all settings to factory defaults

### Settings Page UI
- **Left sidebar**: 6 section buttons with icons (Pharmacy Info, Billing, Notifications, Appearance, Backup, AI Settings)
- **Right content**: `QStackedWidget` with scrollable form for each section
- **Bottom bar**: Status label, Cancel, Reset to Defaults, Save buttons
- **Pharmacy Info**: 6 text fields (name, address, phone, email, PAN, registration)
- **Billing**: VAT spinner (0-100%), receipt width combo (58mm/80mm/A4), currency symbol, footer message, auto-print toggle
- **Notifications**: Expiry warnings checkbox, low stock warnings checkbox, days-before-expiry spinner (7-365)
- **Appearance**: Theme combo (dark/light/system), font size combo (Small/Medium/Large)
- **Backup**: Folder path with Browse button, daily/weekly auto-backup checkboxes, max backups spinner
- **AI Settings**: Groq API key (password field), Groq model combo (editable), OCR engine combo
- **Validation**: Pharmacy name required; success/error status messages

### Startup Behaviour
- `Application._load_settings()` loads persisted settings before font/stylesheet
- Font size applied from settings (Small=9pt, Medium=10pt, Large=12pt)
- Theme applied from settings (dark.qss loaded; light.qss fallback to dark if missing)
- Startup warnings respect `enable_expiry_warnings`, `enable_low_stock_warnings`, and `expiry_warning_days` settings

---

## Task 14 — Backup & Restore

**Date**: 2026-07-14

### Summary
Complete backup and restore system with manual/automatic backups, ZIP compression, backup history, safe restore with validation, and automatic cleanup of old backups.

### New Files
- `app/services/backup_service.py` — `BackupService` with create/restore/list/delete/cleanup/auto-backup logic
- `app/ui/pages/backup_page.py` — `BackupPage` with Create Backup, Restore, History, and Settings sections

### Modified Files
- `app/ui/widgets/sidebar.py` — Added "Backup" nav item with 💾 icon
- `app/ui/windows/main_window.py` — Added `BackupPage` import and "Backup" to PAGE_MAP
- `app/core/app.py` — Added `_run_auto_backup()` on startup (runs before startup warnings)
- `app/resources/styles/dark.qss` — Added `#BackupCard` and `#BackupProgressBar` styles

### Backup Service
- `create_backup(dest_folder, include_logs)` — Creates ZIP with `Pharmacy_Backup_YYYY-MM-DD_HH-MM.zip` naming; includes database + optionally logs; uses `ZIP_DEFLATED` compression
- `restore_backup(zip_path)` — Validates backup, creates safety backup of current DB, extracts DB to temp file, atomic replace; rolls back on failure
- `validate_backup(zip_path)` — Checks file exists, is valid ZIP, contains database file, DB not empty
- `get_backup_history(folder)` — Lists all backup ZIPs sorted newest-first with filename, date, size, location
- `delete_backup(zip_path)` — Removes a backup file
- `run_auto_backup()` — Checks daily/weekly settings, creates backup if conditions met, runs cleanup
- `cleanup_old_backups()` — Enforces `max_backups` limit by deleting oldest entries
- `_should_run_daily()` / `_should_run_weekly()` — Marker-file based scheduling (once per day/week)

### Backup Page UI
- **Create Backup card**: Destination folder with Browse, Include logs checkbox, "Create Backup Now" button
- **Restore Backup card**: Select file button, file display, validation status, "Restore Now" button with confirmation dialog
- **Backup History table**: Filename, Date Created, Size, Location columns; Actions column with Open Folder / Restore / Delete buttons per row; empty state message
- **Backup Settings card**: Folder path with Browse, Daily/Weekly auto-backup checkboxes, Max Backups spinner, Save Settings button
- **Status bar**: Coloured feedback messages (green=success, red=error, blue=info)

### Restore Flow
1. User selects backup ZIP file
2. File is validated (ZIP check, database presence, non-empty)
3. Warning dialog explains data replacement + safety backup
4. Safety backup of current DB created in `_pre_restore/` folder
5. DB extracted to temp file, then atomic replace (delete old → rename new)
6. On failure: safety backup restored automatically
7. Restart prompt after successful restore (spawns new process, quits current)

### Automatic Backups
- Runs on app startup if daily or weekly auto-backup is enabled
- Daily: once per day (marker file tracks last run)
- Weekly: once per week (marker file tracks last run)
- After backup: enforces `max_backups` limit by deleting oldest files
- Runs silently in background, logged to console

### Task 15 — Barcode Scanner & Barcode Management

#### New Files
- `app/services/barcode_service.py` — Barcode generation, validation, detection, lookup, and label data
- `app/ui/dialogs/barcode_label_dialog.py` — Barcode label preview and print dialog (ReportLab PDF)

#### Database — Settings Model
- Added 7 new columns to `settings` table: `barcode_prefix`, `scanner_suffix`, `auto_add_after_scan`, `play_success_sound`, `play_error_sound`, `barcode_label_width`, `barcode_label_font_size`
- Migration handled automatically by `_migrate_columns()`

#### Settings Service
- `AppSettings` dataclass expanded with 7 barcode fields (defaults: prefix=PHM, suffix=empty, auto_add=Yes, sounds=No, label=50x30mm, font=8)
- `DEFAULTS` dict updated with barcode settings
- `load()` and `save()` methods updated to persist barcode settings

#### Barcode Service (`barcode_service.py`)
- `generate(prefix)` — Generates a 13-char barcode (prefix + random digits)
- `generate_unique(prefix)` — Generates a guaranteed-unique barcode (50 retry attempts)
- `validate(barcode)` — Checks format (alphanumeric/hyphens, 4-50 chars)
- `is_unique(barcode, exclude_id)` — Checks barcode is not already assigned
- `check_duplicate(barcode, exclude_id)` — Returns the owner medicine name or None
- `detect_scan(raw, prefix, suffix)` — Parses scanner input: strips prefix/suffix, detects barcode vs text search
- `find_by_barcode(barcode)` — Exact barcode lookup returning Medicine ORM object
- `get_label_data(medicine_id)` — Returns LabelData with medicine name, barcode, price, batch, expiry
- `get_label_data_batch(batch_id)` — Returns LabelData for a specific batch

#### Barcode Label Dialog
- White preview card showing medicine name, generic, company, barcode text, price, batch, expiry
- Print count spinner (1-100)
- Generates A4 PDF with labels arranged in grid (50x30mm each)
- Uses ReportLab canvas; sends to system printer via `ReceiptService.print_pdf()`

#### Billing Page — Barcode Auto-Detection
- Search input now detects barcode scanner input via `BarcodeService.detect_scan()`
- Strips configured prefix/suffix from scanner input
- Pure numeric input >= 8 chars treated as barcode
- Barcode match: looks up medicine, auto-adds to bill (single batch → qty 1, multiple → qty picker)
- Success/error beep feedback via `QCoreApplication.beep()` (configurable in settings)
- Text search still works normally for non-barcode input

#### Inventory Page — Barcode Actions
- "Generate Barcode" toolbar button: generates unique barcode for selected medicine, saves to DB
- "Print Label" toolbar button: opens BarcodeLabelDialog for selected medicine
- Handles existing barcode (prompts to replace), missing barcode (prompts to generate first)

#### Medicine Dialog — Enhanced Barcode
- "Generate" button added next to barcode field for inline barcode generation
- On save: validates barcode format (4-50 chars, alphanumeric/hyphens)
- On save: checks for duplicate barcode (shows owner medicine name on conflict)
- Passes `medicine_id` from inventory edit to exclude self from duplicate check

#### Settings Page — Barcode Section
- New 7th section "Barcode" in settings navigation with barcode icon
- Fields: Barcode Prefix, Scanner Suffix, Auto-Add on Scan checkbox, Success/Error Sound checkboxes, Label Size dropdown, Label Font Size spinner
- Form load/save/reset all handle barcode settings

#### Stylesheet
- Added `#BarcodeLabelPreview` style for white-background label preview card
- Added `#InventoryTable` style for inventory table (alternating rows, selection, hover)

### Task 16 — OCR Foundation (Invoice Import)

#### New Files
- `app/services/ocr_service.py` — Offline OCR engine abstraction with PaddleOCR/EasyOCR fallback
- `app/ui/pages/ocr_invoice_page.py` — AI Invoice Import page with upload, preview, and text extraction

#### OCR Service (`ocr_service.py`)
- `OCRService.extract_text(file_path)` — Main API: extracts text from image or PDF, returns `OCRResult`
- `OCRService.extract_text_from_images(images, file_name)` — OCR from list of image bytes/paths
- `OCRService.get_active_engine()` — Returns name of currently active engine (PaddleOCR/EasyOCR/None)
- `OCRService.is_available()` — Check if any OCR engine is installed
- `OCRService.is_supported(file_path)` — Check file extension support
- Engine initialization: lazy-loads PaddleOCR first, falls back to EasyOCR
- PDF processing: uses PyMuPDF (`fitz`) to render each page at 2x resolution, OCR each page
- Image processing: directly OCR single images
- Result dataclasses: `OCRResult` (file info, text, stats, page results), `PageResult` (per-page text/confidence)
- Error hierarchy: `OCRError` base, `UnsupportedFileError`, `UnreadableFileError`, `OCREngineError`, `EmptyDocumentError`
- Supported formats: JPG, JPEG, PNG, BMP, TIFF, WebP, PDF

#### OCR Invoice Import Page (`ocr_invoice_page.py`)
- **Upload buttons**: Upload Image (JPG/PNG), Upload PDF, Paste Image from Clipboard
- **Drag & Drop zone**: Accepts image files, PDFs, and pasted images; visual feedback on drag hover
- **Document preview**: Shows loaded image or first page of PDF in scrollable preview area
- **Extracted text panel**: Read-only monospace text display with full extracted text
- **Stats panel**: Engine used, pages processed (current/total), processing time, word count, confidence %, line count, character count
- **Actions**: Copy All (clipboard), Clear, Process Document
- **Background processing**: OCR runs in QThread worker to keep UI responsive; cursor changes to wait during processing
- **Error handling**: Friendly messages for unsupported files, unreadable images, OCR failure, empty documents, missing engine
- **Engine check**: Disables upload buttons if no OCR engine is available, shows install instructions

#### Sidebar & Navigation
- Added "AI Invoice Import" (📷) to sidebar navigation between Low Stock and Backup
- Added `OCRInvoicePage` to `PAGE_MAP` in main window

#### Dependencies
- Added `PyMuPDF>=1.23.0` for PDF page rendering
- Added `Pillow>=10.0.0` for image handling
- Added `paddleocr>=2.7.0` and `paddlepaddle>=2.5.0` for primary OCR engine
- Added `easyocr>=1.7.0` for fallback OCR engine

#### Stylesheet
- Added `#OCDDropZone` style for drag-and-drop zone (dashed border, hover highlight)
- Added `#OCRStats` style for stats panel card
- Added `#OCRTextDisplay` style for monospace extracted text display
