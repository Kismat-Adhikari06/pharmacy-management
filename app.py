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
    ("SALES", ["Billing (POS)", "Sales History"]),
    ("INVENTORY", ["Inventory", "Suppliers"]),
    ("ALERTS", ["Expiry", "Low Stock"]),
    (None, ["Backup", "Settings"]),
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
        low_stock_count = sum(
            1 for m in low_stock_items
            if sum(b.quantity for b in m.batches) <= m.minimum_stock
        )

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
        dup = db.query(Medicine).filter(
            func.lower(Medicine.medicine_name) == name.lower(),
            Medicine.is_active == 1,
        ).first()
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
        if name and name.lower() != m.medicine_name.lower():
            dup = db.query(Medicine).filter(
                func.lower(Medicine.medicine_name) == name.lower(),
                Medicine.id != med_id,
                Medicine.is_active == 1,
            ).first()
            if dup:
                return jsonify({"error": "Name already exists"}), 400
            m.medicine_name = name
        if "generic_name" in data:
            m.generic_name = data["generic_name"]
        if "company" in data:
            m.company = data["company"]
        if "category" in data:
            m.category = data["category"]
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
        return jsonify({"message": "Medicine permanently deleted."})
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
    """Accept an uploaded image, stream extracted items via SSE as Groq responds.
    Each complete medicine object is sent as an 'item' event.
    """
    import json, httpx, tempfile, os

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
        api_key = settings.groq_api_key if settings else ""
    finally:
        _db.close()

    if not api_key:
        return jsonify({"error": "Groq API key not configured. Go to Settings to add it."}), 400

    # Read file bytes before the generator starts — avoid 'read of closed file'
    # since Flask closes the request file stream before the generator runs.
    file_bytes = f.read()

    def generate():
        import json, httpx, tempfile, os

        tmp_path = None
        try:
            from openai import OpenAI

            mime = "image/jpeg"
            if ext == "png":
                mime = "image/png"
            elif ext == "webp":
                mime = "image/webp"
            elif ext == "pdf":
                mime = "application/pdf"
            elif ext in ("bmp",):
                mime = "image/bmp"
            elif ext in ("tiff", "tif"):
                mime = "image/tiff"

            suffix = f".{ext}" if ext != "pdf" else ".pdf"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            with open(tmp_path, "rb") as img_file:
                upload_resp = httpx.post(
                    "https://catbox.moe/user/api.php",
                    data={"reqtype": "fileupload"},
                    files={"fileToUpload": (f.filename, img_file, mime)},
                    timeout=30,
                )

            if upload_resp.status_code != 200 or not upload_resp.text.startswith("http"):
                yield f"event: error\ndata: {json.dumps({'message': f'Image upload failed: {upload_resp.text}'})}\n\n"
                return

            image_url = upload_resp.text.strip()

            system_prompt = """You are an expert pharmacy invoice parser for a retail pharmacy in Nepal.

CRITICAL RULES:
- Read the image VERY carefully. OCR often garbles medicine names.
- Use context clues (company names, generic names, dosage forms) to CORRECT garbled text.
- For example: "Amlodinone-Finger" is clearly "Amlodipine" from Pfizer. Correct such errors.
- "Paracitamol" -> "Paracetamol". "Amoxicilin" -> "Amoxicillin". Fix common OCR misspellings.
- Prices are in Nepali Rupees (Rs./NPR). Extract the numeric value only.
- Quantity is always a whole number (integer).
- Expiry dates: convert to YYYY-MM-DD when possible. If only MM/YYYY is given, use last day of month.
- Batch numbers are alphanumeric strings (e.g., "AB1234", "ND-2025-001").
- If you cannot confidently read a field, set it to empty string (text) or 0 (numbers).
- DO NOT guess or invent data. Only extract what you can actually see.

Return ONLY valid JSON. No markdown, no code fences, no explanations.

Return EXACTLY this JSON structure:
{
  "supplier_name": "string",
  "invoice_number": "string",
  "items": [
    {
      "medicine_name": "corrected full medicine name with strength",
      "generic_name": "INN/generic name if visible",
      "company": "manufacturer/pharmaceutical company",
      "batch_number": "batch/lot number",
      "expiry_date": "YYYY-MM-DD or MM/YYYY",
      "quantity": 0,
      "purchase_price": 0.0,
      "selling_price": 0.0
    }
  ]
}"""

            VISION_MODELS = ["meta-llama/llama-4-scout-17b-16e-instruct", "meta-llama/llama-4-maverick-17b-128e-instruct"]
            model = settings.groq_model if settings and settings.groq_model else ""
            if model not in VISION_MODELS:
                model = "meta-llama/llama-4-scout-17b-16e-instruct"

            client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

            # ── Streaming request to Groq ──────────────────────────
            stream = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Read this pharmacy invoice image carefully. Extract ALL line items with medicine names, batch numbers, expiry dates, quantities, and prices. Return ONLY valid JSON."},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    },
                ],
                temperature=0.1,
                max_tokens=4096,
                stream=True,
            )

            # ── Accumulate tokens, parse complete items ────────────
            buffer = ""
            seen_count = 0
            stripping_fence = True

            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                buffer += delta

                # Strip leading markdown fence if present
                if stripping_fence:
                    stripped = buffer.lstrip()
                    if stripped.startswith("```"):
                        idx = stripped.find('\n')
                        if idx >= 0:
                            buffer = stripped[idx+1:]
                        else:
                            continue  # wait for more tokens to find the newline
                    stripping_fence = False

                # Strip trailing markdown fence
                clean = buffer.rstrip()
                if clean.endswith("```"):
                    clean = clean[:-3].rstrip()

                # Parse complete items from the buffer
                new_items = _stream_extract_items(clean, seen_count)
                for item in new_items:
                    seen_count += 1
                    yield f"event: item\ndata: {json.dumps(item)}\n\n"

            # Final parse on complete buffer
            clean = buffer.rstrip()
            if clean.endswith("```"):
                clean = clean[:-3].rstrip()
            final_items = _stream_extract_items(clean, seen_count)
            for item in final_items:
                seen_count += 1
                yield f"event: item\ndata: {json.dumps(item)}\n\n"

            yield f"event: done\ndata: {json.dumps({'count': seen_count})}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

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
            s.groq_api_key = request.form.get("groq_api_key", s.groq_api_key)
            s.groq_model = request.form.get("groq_model", s.groq_model)
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
