"""Flask web application - pharmacy management system."""
from __future__ import annotations

import shutil
from pathlib import Path
from datetime import date, datetime, timedelta

ROOT = Path(__file__).resolve().parent

from flask import (
    Flask, render_template, request, redirect, url_for,
    jsonify, flash, send_file, session, Response, stream_with_context,
)
from sqlalchemy import func, or_, extract, case
from sqlalchemy.orm import joinedload

from db import get_db, db_session, init_db
from models import (
    Base, Medicine, Batch, Supplier, Purchase, PurchaseItem,
    Sale, SaleItem, User, Settings,
)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "pharmacy-web-dev-key"
app.config["JSON_SORT_KEYS"] = False

# Ensure database tables and columns exist on startup
init_db()

NAV_GROUPS = [
    (None, ["Dashboard"]),
    (None, ["Billing (POS)"]),
    (None, ["Inventory"]),
    ("REPORTS", ["Sales History", "Expiry", "Low Stock"]),
    (None, ["Settings"]),
]

PAGE_URLS = {
    "Dashboard": "dashboard",
    "Billing (POS)": "billing",
    "Sales History": "sales_history",
    "Inventory": "inventory",
    "Suppliers": "suppliers",
    "Expiry": "expiry",
    "Low Stock": "low_stock",
    "Backup": "backup",
    "Settings": "settings",
}


@app.context_processor
def inject_nav():
    return {"nav_groups": NAV_GROUPS, "page_urls": PAGE_URLS}


@app.teardown_appcontext
def shutdown(exc=None):
    pass


def get_settings(db):
    s = db.query(Settings).first()
    if not s:
        s = Settings()
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


def _now():
    return datetime.now()


def _today():
    return date.today()


def _filter_active(query):
    """Filter a Medicine query to only active (non-deleted) records."""
    return query.filter(Medicine.is_active == 1)


@app.route("/")
def index():
    return redirect(url_for("dashboard"))


# ─── Dashboard ──────────────────────────────────────────────
@app.route("/dashboard")
def dashboard():
    db = get_db()
    try:
        today = _today()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())

        today_sales = db.query(func.coalesce(func.sum(Sale.total_amount), 0.0)).filter(
            Sale.sale_date.between(today_start, today_end)
        ).scalar()
        today_bills = db.query(func.count(Sale.id)).filter(
            Sale.sale_date.between(today_start, today_end)
        ).scalar()

        total_inventory = db.query(func.coalesce(func.sum(Batch.quantity), 0)).scalar()

        low_stock_count = db.query(func.count(Medicine.id)).filter(
            Medicine.id.in_(
                db.query(Batch.medicine_id)
                .group_by(Batch.medicine_id)
                .having(func.coalesce(func.sum(Batch.quantity), 0) <= Medicine.minimum_stock)
                .correlate(Medicine)
                .scalar_subquery()
            )
        ).scalar() if False else 0

        low_stock_items = _filter_active(db.query(Medicine)).all()
        low_stock_list = []
        low_stock_count = 0
        for m in low_stock_items:
            stock = sum(b.quantity for b in m.batches)
            if stock <= m.minimum_stock:
                low_stock_count += 1
                low_stock_list.append({
                    "name": m.medicine_name,
                    "generic": m.generic_name or "",
                    "stock": stock,
                    "min": m.minimum_stock,
                })

        expiry_threshold = today + timedelta(days=90)
        expiring_count = db.query(Batch).filter(
            Batch.expiry_date <= expiry_threshold,
            Batch.quantity > 0,
        ).count()

        recent_sales = db.query(Sale).order_by(Sale.sale_date.desc()).limit(5).all()

        return render_template("dashboard.html",
                               today_sales=today_sales,
                               today_bills=today_bills,
                               total_inventory=total_inventory,
                               low_stock_count=low_stock_count,
                               low_stock_list=low_stock_list,
                               expiring_count=expiring_count,
                               recent_sales=recent_sales,
                               today=today,
                               active_page="Dashboard")
    finally:
        db.close()


# ─── Inventory ──────────────────────────────────────────────
@app.route("/inventory")
def inventory():
    db = get_db()
    try:
        q = request.args.get("q", "").strip()
        query = db.query(Medicine).options(joinedload(Medicine.batches))
        query = _filter_active(query)
        if q:
            pattern = f"%{q}%"
            query = query.filter(
                or_(
                    Medicine.medicine_name.ilike(pattern),
                    Medicine.generic_name.ilike(pattern),
                    Medicine.company.ilike(pattern),
                )
            )
        medicines = query.order_by(Medicine.medicine_name).all()
        return render_template("inventory.html", medicines=medicines, q=q, active_page="Inventory")
    finally:
        db.close()


@app.route("/api/inventory", methods=["POST"])
def api_inventory_create():
    db = get_db()
    try:
        data = request.json
        name = data.get("medicine_name", "").strip()
        if not name:
            return jsonify({"error": "Medicine name is required"}), 400
        med_form = data.get("med_form", "").strip() or None
        dup = db.query(Medicine).filter(
            func.lower(Medicine.medicine_name) == name.lower(),
            Medicine.is_active == 1,
        )
        if med_form:
            dup = dup.filter(func.lower(Medicine.med_form) == med_form.lower())
        dup = dup.first()
        if dup:
            return jsonify({"error": "Medicine already exists"}), 400

        # Convert empty strings to None for columns with UNIQUE constraints
        # so multiple empty entries don't violate the constraint.
        # Handles both missing key, empty string, and explicit JSON null.
        def _null_if_empty(val):
            v = data.get(val)
            if not v or not isinstance(v, str):
                return None
            return v.strip() or None

        m = Medicine(
            medicine_name=name,
            generic_name=data.get("generic_name", ""),
            company=data.get("company", ""),
            category=data.get("category", ""),
            med_form=med_form,
            barcode=_null_if_empty("barcode"),
            rack_location=data.get("rack_location", ""),
            minimum_stock=int(data.get("minimum_stock", 0)),
        )
        db.add(m)
        db.commit()
        db.refresh(m)
        return jsonify({"id": m.id, "message": "Created"})
    except Exception as e:
        db.rollback()
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    finally:
        db.close()


@app.route("/api/inventory/<int:med_id>", methods=["PUT"])
def api_inventory_update(med_id):
    db = get_db()
    try:
        m = db.get(Medicine, med_id)
        if not m:
            return jsonify({"error": "Not found"}), 404
        data = request.json
        name = data.get("medicine_name", "").strip()
        new_form = data.get("med_form", "").strip() or None
        check_name = name.lower() if name else m.medicine_name.lower()
        check_form = new_form.lower() if "med_form" in data else (m.med_form.lower() if m.med_form else None)
        dup = db.query(Medicine).filter(
            func.lower(Medicine.medicine_name) == check_name,
            Medicine.id != med_id,
            Medicine.is_active == 1,
        )
        if check_form:
            dup = dup.filter(func.lower(Medicine.med_form) == check_form)
        else:
            dup = dup.filter(Medicine.med_form.is_(None))
        dup = dup.first()
        if dup:
            return jsonify({"error": "Medicine with same name and form already exists"}), 400
        if name:
            m.medicine_name = name
        if "generic_name" in data:
            m.generic_name = data["generic_name"]
        if "company" in data:
            m.company = data["company"]
        if "category" in data:
            m.category = data["category"]
        if "med_form" in data:
            m.med_form = data["med_form"] if data["med_form"] else None
        if "barcode" in data:
            bc = data["barcode"]
            m.barcode = bc.strip() if bc and isinstance(bc, str) else None
        if "rack_location" in data:
            m.rack_location = data["rack_location"]
        if "minimum_stock" in data:
            m.minimum_stock = int(data["minimum_stock"])
        db.commit()
        return jsonify({"message": "Updated"})
    finally:
        db.close()


@app.route("/api/inventory/<int:med_id>", methods=["DELETE"])
def api_inventory_delete(med_id):
    db = get_db()
    try:
        m = db.get(Medicine, med_id)
        if not m:
            return jsonify({"error": "Not found"}), 404

        # Check if any batch has been used in sales or purchases
        has_history = any(
            b.sale_items or b.purchase_items
            for b in m.batches
        )

        if has_history:
            # Has sales/purchase history — soft-delete to preserve records
            m.is_active = 0
            for batch in m.batches:
                batch.is_active = 0
                batch.quantity = 0
            db.commit()
            return jsonify({"message": "Medicine archived (has sales/purchase history). Stock set to 0."})

        # No history — permanently delete
        for batch in list(m.batches):
            db.delete(batch)
        db.delete(m)
        db.commit()
        return jsonify({"message": "Updated"})
    finally:
        db.close()


@app.route("/api/inventory/<int:med_id>/batches", methods=["GET"])
def api_inventory_batches(med_id):
    """Return all active batches for a medicine, sorted by expiry date (soonest first)."""
    db = get_db()
    try:
        med = db.get(Medicine, med_id)
        if not med:
            return jsonify({"error": "Not found"}), 404
        batches = db.query(Batch).filter(
            Batch.medicine_id == med_id,
            Batch.is_active == 1,
        ).order_by(Batch.expiry_date.asc()).all()
        return jsonify([
            {
                "id": b.id,
                "batch_number": b.batch_number,
                "expiry_date": b.expiry_date.isoformat() if b.expiry_date else None,
                "purchase_price": b.purchase_price,
                "selling_price": b.selling_price,
                "quantity": b.quantity,
            }
            for b in batches
        ])
    finally:
        db.close()


@app.route("/api/inventory/bulk-delete", methods=["POST"])
def api_inventory_bulk_delete():
    """Bulk delete multiple medicines.
    Hard-deletes if no sales/purchase history, otherwise soft-deletes.
    """
    db = get_db()
    try:
        data = request.json
        ids = data.get("ids", [])
        if not ids:
            return jsonify({"error": "No IDs provided"}), 400

        deleted = 0
        archived = 0
        for med_id in ids:
            m = db.get(Medicine, int(med_id))
            if not m:
                continue
            has_history = any(
                b.sale_items or b.purchase_items
                for b in m.batches
            )
            if has_history:
                m.is_active = 0
                for batch in m.batches:
                    batch.is_active = 0
                    batch.quantity = 0
                archived += 1
            else:
                for batch in list(m.batches):
                    db.delete(batch)
                db.delete(m)
                deleted += 1
        db.commit()
        parts = []
        if deleted:
            parts.append(f"{deleted} permanently deleted")
        if archived:
            parts.append(f"{archived} archived (has history)")
        return jsonify({"message": ", ".join(parts) + ".", "count": deleted + archived})
    finally:
        db.close()


# ─── AI Invoice Extraction — Streaming SSE endpoint ──────
@app.route("/api/inventory/extract-invoice", methods=["POST"])
def api_extract_invoice():
    """Accept an uploaded image, extract invoice data via OpenRouter vision, stream results as SSE."""
    import json, io, base64

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "No file selected"}), 400

    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in ("jpg", "jpeg", "png", "bmp", "webp", "tiff", "tif", "pdf"):
        return jsonify({"error": "Unsupported file type. Use JPG, PNG, BMP, WebP, or PDF."}), 400

    _db = get_db()
    try:
        settings = get_settings(_db)
        api_key = settings.openrouter_api_key if settings else ""
    finally:
        _db.close()

    if not api_key or not api_key.strip():
        return jsonify({"error": "No API key configured. Add your OpenRouter API key in Settings > AI / OCR to enable AI scanning."}), 400

    api_key = api_key.strip()

    # Read file bytes before streaming (Flask closes the stream otherwise)
    file_bytes = f.read()

    system_prompt = """Parse this Nepali pharmaceutical invoice photograph. Correct garbled OCR text using pharmaceutical knowledge. Return ONLY valid JSON — no explanation, no markdown, no extra text.

JSON structure:
{
  "supplier_name": "", "supplier_pan": "", "invoice_number": "",
  "transaction_date": "YYYY-MM-DD", "payment_mode": "Cash or Credit",
  "buyer_name": "", "buyer_pan": "",
  "total": 0.0, "discount": 0.0, "net_total": 0.0,
  "items": [{
    "medicine_name": "full name with strength and dosage form",
    "generic_name": "", "company": "", "med_form": "Tablet/Capsule/Syrup/Injection/Ointment/Drops",
    "batch_number": "", "expiry_date": "YYYY-MM-DD", "quantity": 0,
    "rate": 0.0, "amount": 0.0, "mrp": 0.0
  }]
}
Rules: Prices in Rs (numeric only). Qty is integer. Expiry as YYYY-MM-DD (if MM/YYYY given, use last day of month). Omit missing fields. Do not guess data."""

    user_prompt = "Extract all fields from this Nepali pharmaceutical invoice. Correct garbled OCR text. Return JSON only."

    def generate():
        import json, io, re, base64
        nonlocal file_bytes

        try:
            from PIL import Image as PILImage

            # Resize and compress image for vision model (stay under token limits)
            image_data = file_bytes
            if ext.lower() != "pdf":
                try:
                    img = PILImage.open(io.BytesIO(file_bytes))
                    orig_size = len(file_bytes)
                    max_dim = 1568
                    if max(img.size) > max_dim:
                        ratio = max_dim / max(img.size)
                        img = img.resize((int(img.size[0] * ratio), int(img.size[1] * ratio)), PILImage.LANCZOS)
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=85, optimize=True)
                    image_data = buf.getvalue()
                    print(f"[OCR] Compressed: {orig_size} -> {len(image_data)} bytes, {img.size}", flush=True)
                except Exception as e:
                    print(f"[OCR] Compression failed, using original: {e}", flush=True)

            # Encode image as base64 data URI
            if ext == "png":
                mime = "image/png"
            elif ext == "webp":
                mime = "image/webp"
            elif ext == "bmp":
                mime = "image/bmp"
            elif ext in ("tiff", "tif"):
                mime = "image/tiff"
            else:
                mime = "image/jpeg"

            b64_data = base64.b64encode(image_data).decode("utf-8")
            image_data_uri = f"data:{mime};base64,{b64_data}"

            # Call OpenRouter with automatic fallback across free vision models
            from openai import OpenAI
            import time

            models_to_try = [
                "google/gemma-4-31b-it:free",
                "nvidia/nemotron-nano-12b-v2-vl:free",
                "nvidia/nemotron-3-nano-omni:free",
            ]

            raw_text = ""
            last_error = None
            for model_name in models_to_try:
                try:
                    print(f"[OCR] Trying model: {model_name}", flush=True)
                    client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": [
                                {"type": "text", "text": user_prompt},
                                {"type": "image_url", "image_url": {"url": image_data_uri}},
                            ]},
                        ],
                        temperature=0.1,
                        max_tokens=8192,
                    )
                    raw_text = response.choices[0].message.content.strip()
                    print(f"[OCR] Success with model: {model_name}", flush=True)
                    break
                except Exception as e:
                    last_error = str(e)
                    print(f"[OCR] Model {model_name} failed: {e}", flush=True)
                    if "429" in str(e) and model_name != models_to_try[-1]:
                        time.sleep(1)
                        continue
                    elif model_name == models_to_try[-1]:
                        raise

            # Strip markdown code fences and extra text around JSON
            if raw_text.startswith("```"):
                raw_text = re.sub(r'^```\w*\n?', '', raw_text)
            if raw_text.endswith("```"):
                raw_text = re.sub(r'\n?```\s*$', '', raw_text)
            raw_text = raw_text.strip()

            items = _stream_extract_items(raw_text, 0)
            for item in items:
                yield f"event: item\ndata: {json.dumps(item)}\n\n"

            metadata = _stream_extract_metadata(raw_text)
            if metadata:
                yield f"event: metadata\ndata: {json.dumps(metadata)}\n\n"

            yield f"event: done\ndata: {json.dumps({'count': len(items)})}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


def _stream_extract_items(text: str, seen_count: int) -> list:
    """Parse complete medicine objects from a partial JSON buffer.
    Scans for the 'items' array and extracts fully-formed {object}s.
    Returns only items beyond seen_count.
    """
    import json

    # Find the items array
    marker = '"items"'
    idx = text.find(marker)
    if idx == -1:
        return []

    # Find the opening [ of the items array
    bracket = text.find('[', idx)
    if bracket == -1:
        return []

    # Scan character by character tracking object depth
    depth = 0
    in_str = False
    escaped = False
    obj_start = -1
    objects_raw = []

    for i in range(bracket + 1, len(text)):
        ch = text[i]

        if escaped:
            escaped = False
            continue

        if ch == '\\' and in_str:
            escaped = True
            continue

        if ch == '"' and not escaped:
            in_str = not in_str
            continue

        if in_str:
            continue

        if ch == '{':
            if depth == 0:
                obj_start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and obj_start >= 0:
                obj_str = text[obj_start:i + 1]
                try:
                    parsed = json.loads(obj_str)
                    objects_raw.append(parsed)
                except json.JSONDecodeError:
                    pass
                obj_start = -1

    # Return only new objects beyond seen_count
    if seen_count >= len(objects_raw):
        return []
    return objects_raw[seen_count:]


def _stream_extract_metadata(text: str) -> dict:
    """Extract top-level invoice metadata (header/footer fields) from JSON text.
    Returns a dict with supplier_name, supplier_pan, invoice_number, dates,
    payment_mode, buyer info, and footer totals. Missing fields are omitted.
    """
    import json, re

    METADATA_KEYS = [
        "supplier_name", "supplier_pan", "invoice_number",
        "transaction_date", "issue_date", "payment_mode",
        "buyer_name", "buyer_pan",
        "total", "discount", "rounding", "net_total",
    ]
    NUMERIC_KEYS = {"total", "discount", "rounding", "net_total"}

    result = {}
    for key in METADATA_KEYS:
        # Match "key": "value" or "key": numeric_value
        str_pattern = re.compile(r'"' + re.escape(key) + r'"\s*:\s*"([^"]*)"')
        num_pattern = re.compile(r'"' + re.escape(key) + r'"\s*:\s*([0-9.]+)')

        m = str_pattern.search(text)
        if m:
            result[key] = m.group(1)
            continue
        m = num_pattern.search(text)
        if m and key in NUMERIC_KEYS:
            try:
                result[key] = float(m.group(1))
            except ValueError:
                pass
    return result


# ─── Batches (sub-resource of inventory) ────────────────────
@app.route("/api/batches", methods=["POST"])
def api_batch_create():
    db = get_db()
    try:
        data = request.json
        med_id = int(data.get("medicine_id", 0))
        med = db.get(Medicine, med_id)
        if not med:
            return jsonify({"error": "Medicine not found"}), 404
        batch_num = data.get("batch_number", "").strip()
        dup = db.query(Batch).filter(
            func.lower(Batch.batch_number) == batch_num.lower(),
            Batch.medicine_id == med_id,
        ).first()
        if dup:
            return jsonify({"error": "Batch number already exists for this medicine"}), 400
        b = Batch(
            medicine_id=med_id,
            batch_number=batch_num,
            expiry_date=date.fromisoformat(data["expiry_date"]),
            purchase_price=float(data["purchase_price"]),
            selling_price=float(data["selling_price"]),
            quantity=int(data.get("quantity", 0)),
        )
        db.add(b)
        db.commit()
        db.refresh(b)
        return jsonify({"id": b.id, "message": "Created"})
    finally:
        db.close()


@app.route("/api/batches/<int:batch_id>", methods=["PUT"])
def api_batch_update(batch_id):
    db = get_db()
    try:
        b = db.get(Batch, batch_id)
        if not b:
            return jsonify({"error": "Not found"}), 404
        data = request.json
        if "batch_number" in data:
            b.batch_number = data["batch_number"]
        if "expiry_date" in data:
            b.expiry_date = date.fromisoformat(data["expiry_date"])
        if "purchase_price" in data:
            b.purchase_price = float(data["purchase_price"])
        if "selling_price" in data:
            b.selling_price = float(data["selling_price"])
        if "quantity" in data:
            b.quantity = int(data["quantity"])
        db.commit()
        return jsonify({"message": "Updated"})
    finally:
        db.close()


@app.route("/api/batches/<int:batch_id>", methods=["DELETE"])
def api_batch_delete(batch_id):
    db = get_db()
    try:
        b = db.get(Batch, batch_id)
        if not b:
            return jsonify({"error": "Not found"}), 404
        if b.sale_items:
            # Batch has been used in sales — soft-delete by zeroing stock and marking inactive
            b.quantity = 0
            b.is_active = 0
            db.commit()
            return jsonify({"message": "Batch archived (used in sales). Stock set to 0."})
        # No sales — can safely delete purchase items and the batch
        for pi in b.purchase_items:
            db.delete(pi)
        db.delete(b)
        db.commit()
        return jsonify({"message": "Deleted"})
    finally:
        db.close()


# ─── Billing (POS) ──────────────────────────────────────────
@app.route("/billing")
def billing():
    db = get_db()
    try:
        settings = get_settings(db)
        return render_template("billing.html", settings=settings, active_page="Billing (POS)")
    finally:
        db.close()


@app.route("/api/billing/search")
def api_billing_search():
    db = get_db()
    try:
        q = request.args.get("q", "").strip()
        today = _today()
        query = (
            db.query(Batch)
            .join(Medicine)
            .filter(
                Batch.quantity > 0,
                Batch.is_active == 1,
                Medicine.is_active == 1,
            )
        )
        if q:
            pattern = f"%{q}%"
            query = query.filter(
                or_(
                    Medicine.medicine_name.ilike(pattern),
                    Medicine.generic_name.ilike(pattern),
                    Medicine.company.ilike(pattern),
                    Medicine.barcode.ilike(pattern),
                    Medicine.med_form.ilike(pattern),
                )
            )
        batches = query.options(joinedload(Batch.medicine)).order_by(
            Medicine.medicine_name, Batch.expiry_date
        ).all()
        results = []
        for b in batches:
            days_left = (b.expiry_date - today).days
            if days_left < 0:
                exp_status = "Expired"
            elif days_left <= 30:
                exp_status = f"Exp: {days_left}d"
            elif days_left <= 90:
                exp_status = f"Exp: {days_left}d"
            else:
                exp_status = ""
            results.append({
                "batch_id": b.id,
                "medicine_id": b.medicine_id,
                "medicine_name": b.medicine.medicine_name,
                "generic_name": b.medicine.generic_name or "",
                "med_form": b.medicine.med_form or "",
                "batch_number": b.batch_number,
                "expiry_date": b.expiry_date.isoformat(),
                "expiry_status": exp_status,
                "selling_price": b.selling_price,
                "quantity": b.quantity,
                "company": b.medicine.company or "",
            })
        return jsonify(results)
    finally:
        db.close()


@app.route("/api/billing/sale", methods=["POST"])
def api_billing_sale():
    db = get_db()
    try:
        data = request.json
        items = data.get("items", [])
        if not items:
            return jsonify({"error": "No items"}), 400

        payment_method = data.get("payment_method", "Cash")
        discount = float(data.get("discount", 0))
        vat_rate = float(data.get("vat_rate", 0))

        today = _today()
        date_str = today.strftime("%Y%m%d")
        last_sale = db.query(Sale).filter(
            Sale.bill_number.like(f"BILL-{date_str}-%")
        ).order_by(Sale.bill_number.desc()).first()
        if last_sale:
            num = int(last_sale.bill_number.split("-")[-1]) + 1
        else:
            num = 1
        bill_number = f"BILL-{date_str}-{num:04d}"

        subtotal = 0.0
        sale_items = []
        for item in items:
            batch = db.get(Batch, item["batch_id"])
            if not batch:
                db.rollback()
                return jsonify({"error": f"Batch {item['batch_id']} not found"}), 400
            qty = int(item["quantity"])
            if batch.quantity < qty:
                db.rollback()
                return jsonify({"error": f"Insufficient stock for {batch.medicine.medicine_name}"}), 400
            sp = float(item.get("selling_price", batch.selling_price))
            item_discount = float(item.get("discount", 0))
            subtotal += sp * qty - item_discount
            batch.quantity -= qty
            sale_items.append({
                "batch_id": batch.id,
                "quantity": qty,
                "selling_price": sp,
                "discount": item_discount,
            })

        vat_amount = subtotal * vat_rate / 100 if vat_rate > 0 else 0
        total = subtotal - discount + vat_amount

        sale = Sale(
            bill_number=bill_number,
            total_amount=total,
            discount=discount,
            vat_amount=vat_amount,
            payment_method=payment_method,
        )
        db.add(sale)
        db.flush()

        for si in sale_items:
            db.add(SaleItem(
                sale_id=sale.id,
                batch_id=si["batch_id"],
                quantity=si["quantity"],
                selling_price=si["selling_price"],
                discount=si["discount"],
            ))

        db.commit()
        db.refresh(sale)
        return jsonify({"sale_id": sale.id, "bill_number": bill_number, "total": total})
    finally:
        db.close()


@app.route("/api/billing/undo-last", methods=["POST"])
def api_billing_undo_last():
    db = get_db()
    try:
        sale = db.query(Sale).order_by(Sale.id.desc()).first()
        if not sale:
            return jsonify({"error": "No sales to undo"}), 400

        for item in sale.items:
            batch = db.get(Batch, item.batch_id)
            if batch:
                batch.quantity += item.quantity

        db.delete(sale)
        db.commit()
        return jsonify({"message": "Last sale undone", "bill_number": sale.bill_number})
    finally:
        db.close()


# ─── Sales History ──────────────────────────────────────────
@app.route("/sales-history")
def sales_history():
    db = get_db()
    try:
        q = request.args.get("q", "").strip()
        query = db.query(Sale)
        if q:
            query = query.filter(Sale.bill_number.ilike(f"%{q}%"))
        sales = query.order_by(Sale.sale_date.desc()).limit(200).all()
        return render_template("sales_history.html", sales=sales, q=q, active_page="Sales History")
    finally:
        db.close()


@app.route("/api/sales/<int:sale_id>")
def api_sale_detail(sale_id):
    db = get_db()
    try:
        sale = db.query(Sale).options(
            joinedload(Sale.items).joinedload(SaleItem.batch).joinedload(Batch.medicine)
        ).get(sale_id)
        if not sale:
            return jsonify({"error": "Not found"}), 404
        items = []
        for si in sale.items:
            items.append({
                "medicine_name": si.batch.medicine.medicine_name if si.batch and si.batch.medicine else "N/A",
                "batch_number": si.batch.batch_number if si.batch else "N/A",
                "quantity": si.quantity,
                "selling_price": si.selling_price,
                "discount": si.discount,
                "subtotal": si.selling_price * si.quantity - si.discount,
            })
        return jsonify({
            "bill_number": sale.bill_number,
            "sale_date": sale.sale_date.isoformat() if sale.sale_date else "",
            "total_amount": sale.total_amount,
            "discount": sale.discount,
            "vat_amount": sale.vat_amount,
            "payment_method": sale.payment_method,
            "items": items,
        })
    finally:
        db.close()


# ─── Purchases ──────────────────────────────────────────────
@app.route("/purchases")
def purchases():
    db = get_db()
    try:
        q = request.args.get("q", "").strip()
        query = db.query(Purchase).options(joinedload(Purchase.supplier))
        if q:
            query = query.filter(Purchase.invoice_number.ilike(f"%{q}%"))
        purchases_list = query.order_by(Purchase.id.desc()).limit(200).all()
        suppliers = db.query(Supplier).filter(Supplier.status == "Active").order_by(Supplier.supplier_name).all()
        return render_template("purchases.html", purchases=purchases_list, suppliers=suppliers, q=q, active_page="Purchases")
    finally:
        db.close()


@app.route("/api/purchases", methods=["POST"])
def api_purchase_create():
    db = get_db()
    try:
        data = request.json
        supplier_id = int(data.get("supplier_id", 0))
        invoice_number = data.get("invoice_number", "").strip()
        purchase_date_str = data.get("purchase_date", "")
        items = data.get("items", [])
        notes = data.get("notes", "")

        if not supplier_id or not invoice_number or not items:
            return jsonify({"error": "Missing required fields"}), 400

        dup = db.query(Purchase).filter(Purchase.invoice_number == invoice_number).first()
        if dup:
            return jsonify({"error": "Invoice number already exists"}), 400

        total = sum(float(it.get("purchase_price", 0)) * int(it.get("quantity", 0)) for it in items)
        pd = date.fromisoformat(purchase_date_str) if purchase_date_str else _today()

        purchase = Purchase(
            supplier_id=supplier_id,
            invoice_number=invoice_number,
            purchase_date=pd,
            total_amount=total,
            notes=notes,
        )
        db.add(purchase)
        db.flush()

        for it in items:
            batch = Batch(
                medicine_id=int(it["medicine_id"]),
                batch_number=it.get("batch_number", ""),
                expiry_date=date.fromisoformat(it["expiry_date"]),
                purchase_price=float(it["purchase_price"]),
                selling_price=float(it.get("selling_price", it["purchase_price"])),
                quantity=int(it.get("quantity", 0)),
            )
            db.add(batch)
            db.flush()
            db.add(PurchaseItem(
                purchase_id=purchase.id,
                batch_id=batch.id,
                quantity=int(it["quantity"]),
                purchase_price=float(it["purchase_price"]),
            ))

        supplier = db.get(Supplier, supplier_id)
        if supplier:
            supplier.last_purchase_date = pd
            supplier.total_purchases = (supplier.total_purchases or 0) + total

        db.commit()
        return jsonify({"purchase_id": purchase.id, "message": "Created"})
    finally:
        db.close()


@app.route("/api/purchases/<int:purchase_id>")
def api_purchase_detail(purchase_id):
    db = get_db()
    try:
        p = db.query(Purchase).options(
            joinedload(Purchase.supplier),
            joinedload(Purchase.items).joinedload(PurchaseItem.batch).joinedload(Batch.medicine),
        ).get(purchase_id)
        if not p:
            return jsonify({"error": "Not found"}), 404
        items = []
        for pi in p.items:
            items.append({
                "medicine_name": pi.batch.medicine.medicine_name if pi.batch and pi.batch.medicine else "N/A",
                "batch_number": pi.batch.batch_number if pi.batch else "N/A",
                "quantity": pi.quantity,
                "purchase_price": pi.purchase_price,
            })
        return jsonify({
            "invoice_number": p.invoice_number,
            "supplier_name": p.supplier.supplier_name if p.supplier else "N/A",
            "purchase_date": p.purchase_date.isoformat() if p.purchase_date else "",
            "total_amount": p.total_amount,
            "notes": p.notes or "",
            "items": items,
        })
    finally:
        db.close()


# ─── Suppliers ──────────────────────────────────────────────
@app.route("/suppliers")
def suppliers():
    db = get_db()
    try:
        q = request.args.get("q", "").strip()
        status_filter = request.args.get("status", "").strip()
        query = db.query(Supplier)
        if q:
            pattern = f"%{q}%"
            query = query.filter(
                or_(
                    Supplier.supplier_name.ilike(pattern),
                    Supplier.contact_person.ilike(pattern),
                    Supplier.phone.ilike(pattern),
                    Supplier.email.ilike(pattern),
                    Supplier.pan_number.ilike(pattern),
                )
            )
        if status_filter:
            query = query.filter(Supplier.status == status_filter)
        suppliers_list = query.order_by(Supplier.supplier_name).all()
        return render_template("suppliers.html", suppliers=suppliers_list, q=q, status_filter=status_filter, active_page="Suppliers")
    finally:
        db.close()


@app.route("/api/suppliers", methods=["POST"])
def api_supplier_create():
    db = get_db()
    try:
        data = request.json
        name = data.get("supplier_name", "").strip()
        if not name:
            return jsonify({"error": "Name is required"}), 400
        dup = db.query(Supplier).filter(func.lower(Supplier.supplier_name) == name.lower()).first()
        if dup:
            return jsonify({"error": "Supplier already exists"}), 400
        s = Supplier(
            supplier_name=name,
            contact_person=data.get("contact_person", ""),
            phone=data.get("phone", ""),
            email=data.get("email", ""),
            address=data.get("address", ""),
            pan_number=data.get("pan_number", ""),
            registration_number=data.get("registration_number", ""),
            status=data.get("status", "Active"),
        )
        db.add(s)
        db.commit()
        db.refresh(s)
        return jsonify({"id": s.id, "message": "Created"})
    finally:
        db.close()


@app.route("/api/suppliers/<int:sup_id>", methods=["PUT"])
def api_supplier_update(sup_id):
    db = get_db()
    try:
        s = db.get(Supplier, sup_id)
        if not s:
            return jsonify({"error": "Not found"}), 404
        data = request.json
        if "supplier_name" in data:
            s.supplier_name = data["supplier_name"]
        if "contact_person" in data:
            s.contact_person = data["contact_person"]
        if "phone" in data:
            s.phone = data["phone"]
        if "email" in data:
            s.email = data["email"]
        if "address" in data:
            s.address = data["address"]
        if "pan_number" in data:
            s.pan_number = data["pan_number"]
        if "registration_number" in data:
            s.registration_number = data["registration_number"]
        if "status" in data:
            s.status = data["status"]
        db.commit()
        return jsonify({"message": "Updated"})
    finally:
        db.close()


@app.route("/api/suppliers/<int:sup_id>", methods=["DELETE"])
def api_supplier_delete(sup_id):
    db = get_db()
    try:
        s = db.get(Supplier, sup_id)
        if not s:
            return jsonify({"error": "Not found"}), 404
        if s.purchases:
            # Supplier has purchase history — mark as Inactive instead of deleting
            s.status = "Inactive"
            db.commit()
            return jsonify({"message": "Supplier set to Inactive (has purchase history). Use Edit to reactivate."})
        db.delete(s)
        db.commit()
        return jsonify({"message": "Deleted"})
    finally:
        db.close()


@app.route("/suppliers/<int:sup_id>")
def supplier_detail(sup_id):
    db = get_db()
    try:
        s = db.get(Supplier, sup_id)
        if not s:
            flash("Supplier not found", "error")
            return redirect(url_for("suppliers"))
        purchases = db.query(Purchase).filter(Purchase.supplier_id == sup_id).order_by(Purchase.purchase_date.desc()).all()
        return render_template("supplier_detail.html", supplier=s, purchases=purchases, active_page="Suppliers")
    finally:
        db.close()


# ─── Expiry ─────────────────────────────────────────────────
@app.route("/expiry")
def expiry():
    db = get_db()
    try:
        today = _today()
        threshold = today + timedelta(days=90)
        batches = (
            db.query(Batch)
            .join(Medicine)
            .filter(Batch.expiry_date <= threshold, Batch.quantity > 0)
            .options(joinedload(Batch.medicine))
            .order_by(Batch.expiry_date)
            .all()
        )
        for b in batches:
            days_left = (b.expiry_date - today).days
            if days_left < 0:
                b._status = "Expired"
                b._color = "danger"
            elif days_left <= 30:
                b._status = "Critical"
                b._color = "danger"
            elif days_left <= 60:
                b._status = "Warning"
                b._color = "warning"
            else:
                b._status = "Caution"
                b._color = "info"
            b._days_left = days_left
        categories = db.query(Medicine.category).filter(Medicine.category.isnot(None), Medicine.category != "", Medicine.is_active == 1).distinct().all()
        companies = db.query(Medicine.company).filter(Medicine.company.isnot(None), Medicine.company != "", Medicine.is_active == 1).distinct().all()
        return render_template("expiry.html",
                               batches=batches,
                               categories=[c[0] for c in categories],
                               companies=[c[0] for c in companies],
                               active_page="Expiry")
    finally:
        db.close()


# ─── Low Stock ──────────────────────────────────────────────
@app.route("/low-stock")
def low_stock():
    db = get_db()
    try:
        medicines = _filter_active(db.query(Medicine)).options(joinedload(Medicine.batches)).all()
        low_items = []
        for m in medicines:
            stock = sum(b.quantity for b in m.batches)
            if stock <= m.minimum_stock:
                m._current_stock = stock
                low_items.append(m)
        return render_template("low_stock.html", items=low_items, active_page="Low Stock")
    finally:
        db.close()


# ─── AI Invoice Import (placeholder) ────────────────────────
@app.route("/ocr-import")
def ocr_import():
    return render_template("ocr_import.html", active_page="AI Invoice Import")


# ─── Backup ─────────────────────────────────────────────────
@app.route("/backup")
def backup():
    db = get_db()
    try:
        settings = get_settings(db)
        backup_dir = ROOT / settings.backup_folder
        backups = []
        if backup_dir.exists():
            for f in sorted(backup_dir.glob("*.zip"), reverse=True):
                stat = f.stat()
                backups.append({
                    "name": f.name,
                    "path": str(f),
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "date": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                })
        return render_template("backup.html", backups=backups, active_page="Backup")
    finally:
        db.close()


@app.route("/api/backup/create", methods=["POST"])
def api_backup_create():
    db = get_db()
    try:
        settings = get_settings(db)
        backup_dir = ROOT / settings.backup_folder
        backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        src = ROOT / "data" / "pharmacy.db"
        dest = backup_dir / f"backup_{ts}.db"
        shutil.copy2(src, dest)
        return jsonify({"message": "Backup created", "file": dest.name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@app.route("/api/backup/download/<path:filename>")
def api_backup_download(filename):
    backup_dir = ROOT / "backups"
    fpath = backup_dir / filename
    if fpath.exists():
        return send_file(fpath, as_attachment=True)
    return jsonify({"error": "Not found"}), 404


@app.route("/api/backup/delete", methods=["POST"])
def api_backup_delete():
    data = request.json
    fpath = Path(data.get("path", ""))
    if fpath.exists() and "backups" in str(fpath):
        fpath.unlink()
        return jsonify({"message": "Deleted"})
    return jsonify({"error": "Not found"}), 404


@app.route("/api/backup/restore", methods=["POST"])
def api_backup_restore():
    data = request.json
    fpath = Path(data.get("path", ""))
    if not fpath.exists():
        return jsonify({"error": "Backup file not found"}), 404
    dest = ROOT / "data" / "pharmacy.db"
    shutil.copy2(fpath, dest)
    return jsonify({"message": "Database restored. Please restart the app."})


@app.route("/api/import-json", methods=["POST"])
def api_import_json():
    """Import medicines + batches from JSON payload (strict validation)."""
    from datetime import datetime as dt
    data = request.json
    if not data or "items" not in data:
        return jsonify({"error": "JSON must have an 'items' array."}), 400

    items = data["items"]
    if not isinstance(items, list) or len(items) == 0:
        return jsonify({"error": "'items' must be a non-empty array."}), 400

    REQUIRED = ["item_description", "batch", "expiry_date", "qty", "rate", "mrp"]
    NUMERIC = {"qty": int, "rate": float, "mrp": float, "amount": float}

    errors = []
    for i, item in enumerate(items):
        for field in REQUIRED:
            val = item.get(field)
            if val is None or (isinstance(val, str) and val.strip() == ""):
                errors.append(f"Item {i+1} ({item.get('item_description', '?')}): '{field}' is missing or empty.")
                continue
        if "expiry_date" in item and isinstance(item["expiry_date"], str):
            try:
                dt.strptime(item["expiry_date"], "%Y-%m-%d")
            except ValueError:
                errors.append(f"Item {i+1} ({item.get('item_description', '?')}): expiry_date must be YYYY-MM-DD, got '{item['expiry_date']}'.")
        for field, typ in NUMERIC.items():
            if field in item:
                try:
                    typ(item[field])
                except (ValueError, TypeError):
                    errors.append(f"Item {i+1} ({item.get('item_description', '?')}): '{field}' must be {typ.__name__}, got '{item[field]}'.")

    if errors:
        return jsonify({"error": "Validation failed.", "details": errors}), 400

    def guess_form(desc):
        d = desc.lower()
        if "syrup" in d or "ml" in d:
            return "Syrup"
        if "sachet" in d or "ors" in d:
            return "Other"
        if "cream" in d or "ointment" in d:
            return "Ointment"
        if "drops" in d:
            return "Drops"
        if "injection" in d or "inject" in d:
            return "Injection"
        if "capsule" in d:
            return "Capsule"
        return "Tablet"

    def parse_name(desc):
        parts = desc.split()
        generic, strength = [], ""
        for p in parts:
            if any(c.isdigit() for c in p) and ("mg" in p.lower() or "ml" in p.lower()):
                strength = p
            else:
                generic.append(p)
        return " ".join(generic), strength

    db = get_db()
    try:
        imported = 0
        skipped = 0
        for item in items:
            desc = item["item_description"].strip()
            batch_num = item["batch"].strip()
            exp_str = item["expiry_date"].strip()
            qty = int(item["qty"])
            rate = float(item["rate"])
            mrp = float(item["mrp"])

            generic, strength = parse_name(desc)
            form = guess_form(desc)

            med = db.query(Medicine).filter(
                func.lower(Medicine.medicine_name) == desc.lower(),
                Medicine.is_active == 1,
            ).first()

            if not med:
                med = Medicine(
                    medicine_name=desc,
                    generic_name=generic,
                    med_form=form,
                    category=form,
                )
                db.add(med)
                db.flush()

            existing_batch = db.query(Batch).filter(
                Batch.medicine_id == med.id,
                Batch.batch_number == batch_num,
            ).first()

            if existing_batch:
                existing_batch.quantity += qty
                existing_batch.purchase_rate = rate
                existing_batch.selling_price = mrp
                imported += 1
            else:
                batch = Batch(
                    medicine_id=med.id,
                    batch_number=batch_num,
                    expiry_date=dt.strptime(exp_str, "%Y-%m-%d").date(),
                    purchase_price=rate,
                    selling_price=mrp,
                    quantity=qty,
                )
                db.add(batch)
                imported += 1

        db.commit()
        return jsonify({"message": f"Imported {imported} items successfully.", "imported": imported, "skipped": skipped})
    except Exception as e:
        db.rollback()
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    finally:
        db.close()


# ─── Settings ───────────────────────────────────────────────
@app.route("/settings", methods=["GET", "POST"])
def settings():
    db = get_db()
    try:
        s = get_settings(db)
        if request.method == "POST":
            s.pharmacy_name = request.form.get("pharmacy_name", s.pharmacy_name)
            s.address = request.form.get("address", s.address)
            s.phone = request.form.get("phone", s.phone)
            s.email = request.form.get("email", s.email)
            s.pan_number = request.form.get("pan_number", s.pan_number)
            s.registration_number = request.form.get("registration_number", s.registration_number)
            s.default_vat = float(request.form.get("default_vat", s.default_vat))
            s.currency_symbol = request.form.get("currency_symbol", s.currency_symbol)
            s.receipt_footer = request.form.get("receipt_footer", s.receipt_footer)
            s.default_theme = request.form.get("default_theme", s.default_theme)
            s.expiry_warning_days = int(request.form.get("expiry_warning_days", s.expiry_warning_days))
            s.backup_folder = request.form.get("backup_folder", s.backup_folder)
            s.max_backups = int(request.form.get("max_backups", s.max_backups))
            s.openrouter_api_key = request.form.get("openrouter_api_key", s.openrouter_api_key or "")
            db.commit()
            flash("Settings saved", "success")
            return redirect(url_for("settings"))
        return render_template("settings.html", settings=s, active_page="Settings")
    finally:
        db.close()


@app.route("/api/settings/theme", methods=["POST"])
def api_settings_theme():
    db = get_db()
    try:
        data = request.json
        theme = data.get("theme", "dark")
        s = get_settings(db)
        s.default_theme = theme
        db.commit()
        return jsonify({"theme": theme})
    finally:
        db.close()


# ─── Run ────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, port=5000, host="127.0.0.1")
