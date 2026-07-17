# Pharmacy Management System — Nepal 🇳🇵

> **Browser-based POS** for retail pharmacies in Nepal. Built with Python 3 + Flask + SQLAlchemy. Dark/light theme, fully responsive, works offline.

---

## Quick Start

```bash
# Clone & install
git clone https://github.com/Kismat-Adhikari06/pharmacy-management.git
cd pharmacy-management
pip install -r requirements.txt

# Run
python app.py
```

The app starts at **http://127.0.0.1:5000**.

The database (`data/pharmacy.db`) is created automatically on first launch.

---

## Features

| Module | What it does |
|--------|-------------|
| **Dashboard** | Today's sales, total stock count, expiring-soon counter, low stock count, recent sales table |
| **Billing (POS)** | Real-time search by name/generic/company/barcode, batch-level tracking (FEFO), quantity controls, per-item & global discount, VAT, multiple payment methods (Cash / Card / Online / Credit). Auto-generates bill numbers (`BILL-YYYYMMDD-####`). |
| **Sales History** | Browse past transactions, filter by bill number, view itemized details with medicine name, batch, quantity, pricing, discount, VAT |
| **Inventory** | Full medicine CRUD — name, generic, company, category, barcode, rack location, minimum stock. Batch sub-management: add/edit/delete batches with expiry date, purchase & selling price, quantity. Instant search. |
| **AI Invoice Extraction** | Upload invoice image/PDF in the **Add Medicine** modal (Scan mode). Uses Groq Llama 4 Scout/Maverick vision models to extract medicine names, batch numbers, expiry dates, quantities, prices. Results fill the form automatically. |
| **Purchases** | Record supplier purchases with multiple line items. Each item auto-creates a batch (medicine, batch#, expiry, prices, quantity). Search by invoice number. View purchase details with all items. |
| **Suppliers** | Full supplier directory — name, contact person, phone, email, address, PAN/VAT, registration number, status (Active/Inactive). Search across all fields. Detail page with purchase history & stats (total purchases, outstanding balance, last purchase date). |
| **Expiry Tracker** | 90-day lookahead. Color-coded status badges: **Expired** (red), **Critical ≤30d** (red), **Warning ≤60d** (yellow), **Caution ≤90d** (blue). Shows days left, stock quantity, buy/sell prices. |
| **Low Stock Alert** | Lists all medicines at or below their configured `minimum_stock` threshold. Shows current vs minimum stock. Out-of-stock items highlighted in red. |
| **Backup & Restore** | One-click database backup stored as `.db` files in `backups/`. Download, delete, or restore any backup. |
| **Settings** | Tabbed settings panel — **General** (pharmacy name, address, phone, email, PAN, registration), **Billing** (default VAT %, currency symbol, receipt footer), **Appearance** (dark/light theme toggle, expiry warning days), **Backup** (folder path, max backups retention), **AI/OCR** (Groq API key, model selection). |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3, Flask 3.x |
| **Database** | SQLite via SQLAlchemy 2.x ORM (WAL mode, foreign keys ON) |
| **Frontend** | Vanilla JavaScript, CSS Custom Properties, no frameworks |
| **Theming** | Dark & Light themes via CSS variables + localStorage + server-side persistence |
| **AI Vision** | Groq Cloud API — Llama 4 Scout (17B) / Maverick (17B) vision models via OpenAI SDK |
| **Image Upload** | Catbox.moe temp hosting for invoice image processing |

---

## Database Models

| Model | Table | Purpose |
|-------|-------|---------|
| `Medicine` | `medicines` | Name, generic, company, category, barcode, rack location, minimum stock threshold |
| `Batch` | `batches` | Batch number, expiry date, purchase/selling price, quantity, FK→medicine |
| `Supplier` | `suppliers` | Contact info, PAN/VAT, registration, status, outstanding balance, purchase stats |
| `Purchase` | `purchases` | Supplier FK, invoice number, date, total amount, notes |
| `PurchaseItem` | `purchase_items` | Links purchase → batch with quantity & unit price |
| `Sale` | `sales` | Bill number (auto-generated), date, total, discount, VAT, payment method |
| `SaleItem` | `sale_items` | Links sale → batch with quantity, selling price, discount |
| `User` | `users` | Username, password hash (SHA-256), role, full name |
| `Settings` | `settings` | Single-row config: pharmacy info, billing, theme, backup, Groq API key, etc. |

---

## FEFO (First Expired, First Out)

The billing engine sorts available batches by **expiry date ascending**, encouraging FEFO deduction at the point of sale. Stock is validated before completing any sale — insufficient stock is rejected with a clear error message.

---

## AI Invoice Import (optional)

1. Get a free API key from [Groq Console](https://console.groq.com) (free tier available)
2. Go to **Settings → AI/OCR** and paste your Groq API key
3. In **Inventory**, click **Add Medicine** → switch to **Scan Invoice** tab → upload invoice image/PDF
4. The AI extracts medicine names, batch numbers, expiry dates, quantities, purchase & selling prices
5. Click any extracted item to auto-fill the medicine form — batch fields appear automatically

**Supported file types:** JPG, PNG, WebP, BMP, TIFF, PDF

---

## Project Structure

```
.
├── app.py                  # Flask app — all routes & API endpoints
├── models.py               # SQLAlchemy ORM models (9 tables)
├── db.py                   # Database connection, session, WAL + FK pragmas
├── requirements.txt        # Python dependencies
├── static/
│   ├── css/style.css       # Complete dark/light theme (~600 lines)
│   └── js/app.js           # Theme toggle, modals, AJAX helper, flash auto-dismiss
├── templates/
│   ├── base.html           # Layout: sidebar nav, header, theme toggle, flash messages
│   ├── dashboard.html      # Stats cards + recent sales table
│   ├── billing.html        # Full POS: search, cart, qty controls, discount, checkout
│   ├── inventory.html      # Medicine table + Add/Edit/Batch modals + AI Scan mode
│   ├── purchases.html      # Purchase list + New Purchase modal with multi-item entry
│   ├── suppliers.html      # Supplier directory + Add/Edit modals, status filter
│   ├── supplier_detail.html# Supplier detail with purchase history & financial stats
│   ├── sales_history.html  # Transaction list + sale detail modal (itemized)
│   ├── expiry.html         # Expiring batches table with color-coded status badges
│   ├── low_stock.html      # Low stock medicines table with current vs minimum stock
│   ├── backup.html         # Backup list + create/download/delete/restore
│   ├── settings.html       # Tabbed settings (5 sections: General, Billing, Appearance, Backup, AI/OCR)
│   └── ocr_import.html     # Standalone OCR import page (text paste + file upload)
└── data/
    └── pharmacy.db         # SQLite database (auto-created on first run)
```

---

**Built with ❤️ for pharmacies across Nepal.**
