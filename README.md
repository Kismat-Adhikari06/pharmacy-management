# Pharmacy Management System — Nepal 🇳🇵

> Offline-first Windows desktop POS for retail pharmacies in Nepal. Built with Python 3.11 + PySide6.

---

## Quick Overview

A full-featured pharmacy management system designed specifically for Nepali pharmacies. Handles everything from billing to expiry tracking — no internet required.

**Stack:** Python 3.11 · PySide6 (Qt Widgets) · SQLite · SQLAlchemy · ReportLab · Matplotlib · PyInstaller

---

## Features

| Module | What it does |
|--------|-------------|
| **Dashboard** | At-a-glance: today's sales, profit, low stock, expiring meds, top sellers |
| **Billing (POS)** | Keyboard-first billing with instant search & barcode scanning. F10 to print. |
| **Inventory** | Full medicine DB with batch tracking, categories, manufacturers, instant search |
| **Purchases** | Receive stock, record supplier invoices, AI-powered OCR import (optional) |
| **Suppliers** | Directory with purchase history, DDA licenses, PAN/VAT |
| **Reports** | Daily / Weekly / Monthly / Yearly — sales, profit, inventory, expiry, suppliers |
| **Analytics** | Matplotlib charts: sales trends, top meds, category breakdowns |
| **Expiry Mgmt** | Color-coded alerts (green → yellow → orange → red). FEFO deduction. |
| **Low Stock** | Configurable thresholds. Auto-generated re-order lists by supplier. |
| **Backup** | One-click backup & restore. Auto-scheduled daily backups. |
| **Users** | 3 roles: Admin, Pharmacist, Cashier. Session lock (Ctrl+L). |
| **Settings** | Pharmacy info, tax rates, receipt format (thermal/A4), dark/light theme |

---

## FEFO (First Expired, First Out)

The system automatically deducts stock from the soonest-expiring batch at every sale. No expired medicine reaches the counter.

```
Medicine → find all batches with stock > 0 → sort by expiry ASC → deduct from earliest first
```

---

## Billing Workflow (5 seconds per bill)

1. **F2** → New bill
2. Type medicine name → results appear instantly → **Enter** to select
3. Enter quantity → **Enter**
4. **F8** → Payment (Cash / Card / Credit)
5. **F10** → Print receipt. Stock deducted automatically.

---

## User Roles

| Permission | Admin | Pharmacist | Cashier |
|------------|:-----:|:----------:|:-------:|
| Billing | ✅ | ✅ | ✅ |
| Inventory | ✅ | ✅ | ❌ |
| Purchases | ✅ | ✅ | ❌ |
| Reports | ✅ | ✅ | ❌ |
| User Mgmt | ✅ | ❌ | ❌ |
| Settings | ✅ | ❌ | ❌ |
| Backup | ✅ | ❌ | ❌ |

---

## Quick Start

```bash
# Clone & install
git clone https://github.com/Kismat-Adhikari06/pharmacy-management.git
cd pharmacy-management
pip install -r requirements.txt

# Run
python main.py

# Package for distribution
pyinstaller --onefile --windowed main.py
```

---

## Development Roadmap

| Phase | Weeks | Goal |
|-------|-------|------|
| **1** | 1–8 | Core POS + Inventory + Purchases + Receipt printing |
| **2** | 9–14 | Dashboard, Reports, Analytics, Users, Backup |
| **3** | 15–18 | Barcodes, Expiry Mgmt, Low Stock Alerts, Polish |
| **4** | 19–22 | AI Invoice Scanner (OCR), Final packaging |

---

*See [PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md) for the full 20-page specification document.*

---

**Built with ❤️ for pharmacies across Nepal.**