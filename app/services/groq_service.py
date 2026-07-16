from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# ── .env loading ────────────────────────────────────────────────

_ENV_LOADED = False


def _load_env() -> None:
    """Load .env file from project root (once)."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    try:
        from dotenv import load_dotenv

        env_path = Path(__file__).resolve().parent.parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            logger.info("Loaded .env from %s", env_path)
        else:
            logger.debug("No .env file found at %s", env_path)
    except ImportError:
        logger.debug("python-dotenv not installed; skipping .env load.")


def _get_api_key() -> str:
    _load_env()
    return os.environ.get("GROQ_API_KEY", "").strip()


def _get_model() -> str:
    _load_env()
    return os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile").strip()


def _get_vision_model() -> str:
    _load_env()
    return os.environ.get(
        "GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"
    ).strip()


# ── Data classes ────────────────────────────────────────────────


@dataclass
class InvoiceItem:
    """A single item extracted from an invoice."""

    medicine_name: str = ""
    generic_name: str = ""
    company: str = ""
    batch_number: str = ""
    expiry_date: str = ""
    quantity: int = 0
    purchase_price: float = 0.0
    selling_price: float = 0.0
    name_confidence: float = 0.0
    match_status: str = ""
    matched_medicine_id: int | None = None
    matched_medicine_name: str = ""


@dataclass
class InvoiceData:
    """Structured invoice data extracted by AI."""

    supplier_name: str = ""
    invoice_number: str = ""
    invoice_date: str = ""
    grand_total: float = 0.0
    items: list[InvoiceItem] = field(default_factory=list)
    extraction_method: str = ""

    @property
    def item_count(self) -> int:
        return len(self.items)

    @property
    def total_quantity(self) -> int:
        return sum(item.quantity for item in self.items)

    @property
    def computed_total(self) -> float:
        return sum(
            item.purchase_price * item.quantity for item in self.items
        )


# ── Errors ──────────────────────────────────────────────────────


class GroqError(Exception):
    """Base Groq service error."""


class GroqConfigError(GroqError):
    """Configuration error (missing API key, etc.)."""


class GroqAPIError(GroqError):
    """API call failed (auth, rate limit, network, etc.)."""


class GroqParseError(GroqError):
    """Failed to parse AI response as valid JSON."""


# ── Prompts ─────────────────────────────────────────────────────

_TEXT_SYSTEM_PROMPT = """You are an expert pharmacy invoice parser for a retail pharmacy in Nepal.

CRITICAL RULES:
- Read the OCR text VERY carefully. OCR often garbles medicine names.
- Use context clues (company names, generic names, dosage forms) to CORRECT garbled text.
- For example: "Amlodinone-Finger" is clearly "Amlodipine" from Pfizer. Correct such errors.
- "Paracitamol" → "Paracetamol". "Amoxicilin" → "Amoxicillin". Fix common OCR misspellings.
- Nepali invoice numbers and dates may use non-standard formats — interpret them sensibly.
- Prices are in Nepali Rupees (Rs./NPR). Extract the numeric value only.
- Quantity is always a whole number (integer).
- Expiry dates: convert to YYYY-MM-DD when possible. If only MM/YYYY is given, use last day of month.
- Batch numbers are alphanumeric strings (e.g., "AB1234", "ND-2025-001").
- If you cannot confidently read a field, set it to empty string (text) or 0 (numbers).
- DO NOT guess or invent data. Only extract what you can actually see in the text.

Return ONLY valid JSON. No markdown, no code fences, no explanations.

Return EXACTLY this JSON structure:
{
  "supplier_name": "string (company/person you're buying from)",
  "invoice_number": "string",
  "invoice_date": "YYYY-MM-DD or original format",
  "grand_total": 0.0,
  "items": [
    {
      "medicine_name": "corrected full medicine name with strength (e.g. 'Amlodipine 5mg')",
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

_VISION_SYSTEM_PROMPT = """You are an expert pharmacy invoice parser for a retail pharmacy in Nepal.

You are given an IMAGE of a supplier invoice. Read the image carefully and extract ALL line items.

CRITICAL RULES:
- Read each row of the invoice table carefully. These are medicine line items.
- Medicine names often include strength/dosage (e.g., "Amlodipine 5mg", "Paracetamol 500mg").
- Correct common OCR/image misreads using pharmaceutical knowledge:
  * "Amlodinone" → "Amlodipine", "Paracitamol" → "Paracetamol", "Amoxicilin" → "Amoxicillin"
  * Use company names and generic names as context to verify corrections.
- Batch numbers are alphanumeric (e.g., "AB1234", "ND-2025-001").
- Expiry dates: convert to YYYY-MM-DD when possible. MM/YYYY → last day of month.
- Prices are in Nepali Rupees (Rs./NPR). Extract numeric values only.
- Quantity is always a whole integer.
- If you cannot read a field clearly, set it to empty/0. NEVER invent data.
- Look for the invoice header: supplier name, invoice number, date, and grand total.

Return ONLY valid JSON. No markdown, no code fences, no explanations.

Return EXACTLY this JSON structure:
{
  "supplier_name": "string",
  "invoice_number": "string",
  "invoice_date": "YYYY-MM-DD or original format",
  "grand_total": 0.0,
  "items": [
    {
      "medicine_name": "full medicine name with strength (e.g. 'Amlodipine 5mg')",
      "generic_name": "INN/generic name",
      "company": "manufacturer",
      "batch_number": "batch/lot number",
      "expiry_date": "YYYY-MM-DD or MM/YYYY",
      "quantity": 0,
      "purchase_price": 0.0,
      "selling_price": 0.0
    }
  ]
}"""


# ── Service ─────────────────────────────────────────────────────


class GroqService:
    """Groq Cloud AI service for invoice text and image parsing."""

    @staticmethod
    def is_configured() -> bool:
        """Check if the Groq API key is set."""
        key = _get_api_key()
        return bool(key)

    @staticmethod
    def get_model() -> str:
        return _get_model()

    @staticmethod
    def get_vision_model() -> str:
        return _get_vision_model()

    @staticmethod
    def _get_client():
        """Return a Groq client, raising config errors if needed."""
        api_key = _get_api_key()
        if not api_key:
            raise GroqConfigError(
                "Groq API key is not configured.\n\n"
                "Create a .env file in the project root with:\n"
                "GROQ_API_KEY=your_api_key_here\n"
                "GROQ_MODEL=llama-3.3-70b-versatile"
            )
        try:
            from groq import Groq
        except ImportError:
            raise GroqConfigError(
                "Groq SDK is not installed.\n"
                "Install with: pip install groq"
            )
        return Groq(api_key=api_key)

    @staticmethod
    def _handle_api_error(exc: Exception) -> None:
        """Classify and re-raise API errors."""
        exc_str = str(exc).lower()
        if "invalid" in exc_str and "api" in exc_str:
            raise GroqAPIError(
                "Invalid API key. Check your GROQ_API_KEY in the .env file."
            )
        if "rate" in exc_str or "limit" in exc_str:
            raise GroqAPIError(
                "Rate limit exceeded. Please wait a moment and try again."
            )
        if "connection" in exc_str or "network" in exc_str or "timeout" in exc_str:
            raise GroqAPIError(
                "Network error — cannot reach Groq API.\n"
                "Check your internet connection."
            )
        if "unavailable" in exc_str or "503" in exc_str:
            raise GroqAPIError(
                "Groq API is temporarily unavailable. Please try again later."
            )
        raise GroqAPIError(f"Groq API error: {exc}")

    @staticmethod
    def parse_invoice_from_image(image_path: str | Path) -> InvoiceData:
        """Send an image directly to a vision-capable Groq model.

        This bypasses OCR entirely — the vision model reads the invoice
        image directly, which is far more accurate than OCR → text parsing.

        Args:
            image_path: Path to an invoice image file.

        Returns:
            InvoiceData with parsed invoice information.

        Raises:
            GroqConfigError: API key not configured.
            GroqAPIError: API call failed.
            GroqParseError: Response could not be parsed.
        """
        path = Path(image_path)
        if not path.exists():
            raise GroqParseError(f"Image file not found: {path}")

        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
        }
        mime_type = mime_map.get(path.suffix.lower(), "image/png")
        image_bytes = path.read_bytes()
        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        client = GroqService._get_client()
        vision_model = _get_vision_model()

        try:
            response = client.chat.completions.create(
                model=vision_model,
                messages=[
                    {"role": "system", "content": _VISION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "Read this pharmacy invoice image carefully. "
                                    "Extract ALL line items with medicine names, "
                                    "batch numbers, expiry dates, quantities, and prices. "
                                    "Return ONLY valid JSON."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{b64_image}",
                                },
                            },
                        ],
                    },
                ],
                temperature=0.1,
                max_tokens=4096,
            )
        except Exception as exc:
            GroqService._handle_api_error(exc)

        if not response.choices:
            raise GroqAPIError("Groq returned an empty response (no choices).")

        raw_content = response.choices[0].message.content
        if not raw_content:
            raise GroqAPIError("Groq returned an empty message content.")

        result = GroqService._parse_json(raw_content)
        result.extraction_method = f"Vision ({vision_model})"
        return result

    @staticmethod
    def parse_invoice(ocr_text: str) -> InvoiceData:
        """Send OCR text to Groq and parse the structured response.

        Args:
            ocr_text: Raw text extracted from OCR.

        Returns:
            InvoiceData with parsed invoice information.

        Raises:
            GroqConfigError: API key not configured.
            GroqAPIError: API call failed.
            GroqParseError: Response could not be parsed as valid JSON.
        """
        if not ocr_text or not ocr_text.strip():
            raise GroqParseError("No OCR text provided — nothing to analyze.")

        client = GroqService._get_client()
        model = _get_model()

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _TEXT_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            "Extract structured invoice data from the following OCR text. "
                            "Read carefully and correct any OCR garbling. "
                            "Return ONLY valid JSON.\n\n"
                            f"{ocr_text}"
                        ),
                    },
                ],
                temperature=0.1,
                max_tokens=4096,
            )
        except Exception as exc:
            GroqService._handle_api_error(exc)

        if not response.choices:
            raise GroqAPIError("Groq returned an empty response (no choices).")

        raw_content = response.choices[0].message.content
        if not raw_content:
            raise GroqAPIError("Groq returned an empty message content.")

        result = GroqService._parse_json(raw_content)
        result.extraction_method = f"OCR + Text ({model})"
        return result

    @staticmethod
    def _parse_json(raw: str) -> InvoiceData:
        """Parse the raw AI response into InvoiceData."""
        cleaned = raw.strip()

        # Strip markdown code fences if present
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.warning("JSON parse failed: %s\nRaw content: %s", exc, cleaned[:500])
            raise GroqParseError(
                f"AI returned invalid JSON.\n\n"
                f"Parse error: {exc}\n\n"
                f"Raw response (first 500 chars):\n{cleaned[:500]}"
            )

        if not isinstance(data, dict):
            raise GroqParseError("AI response is not a JSON object.")

        # Parse items
        items: list[InvoiceItem] = []
        raw_items = data.get("items", [])
        if isinstance(raw_items, list):
            for item in raw_items:
                if isinstance(item, dict):
                    name = str(item.get("medicine_name", ""))
                    items.append(InvoiceItem(
                        medicine_name=name,
                        generic_name=str(item.get("generic_name", "")),
                        company=str(item.get("company", "")),
                        batch_number=str(item.get("batch_number", "")),
                        expiry_date=str(item.get("expiry_date", "")),
                        quantity=int(item.get("quantity", 0) or 0),
                        purchase_price=float(item.get("purchase_price", 0) or 0),
                        selling_price=float(item.get("selling_price", 0) or 0),
                    ))

        return InvoiceData(
            supplier_name=str(data.get("supplier_name", "")),
            invoice_number=str(data.get("invoice_number", "")),
            invoice_date=str(data.get("invoice_date", "")),
            grand_total=float(data.get("grand_total", 0) or 0),
            items=items,
        )
