from __future__ import annotations

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


@dataclass
class InvoiceData:
    """Structured invoice data extracted by AI."""

    supplier_name: str = ""
    invoice_number: str = ""
    invoice_date: str = ""
    grand_total: float = 0.0
    items: list[InvoiceItem] = field(default_factory=list)

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


# ── Service ─────────────────────────────────────────────────────


_SYSTEM_PROMPT = """You are an expert pharmacy invoice parser. Your ONLY job is to extract structured data from OCR text of supplier invoices.

Rules:
- Return ONLY valid JSON. No markdown, no explanations, no code fences.
- If a field is not found, use an empty string for text fields, 0 for numbers.
- Ensure all JSON is properly escaped.
- Dates should be in YYYY-MM-DD format if possible.
- Prices should be numeric (no currency symbols).

Return EXACTLY this JSON structure:
{
  "supplier_name": "string",
  "invoice_number": "string",
  "invoice_date": "string",
  "grand_total": 0.0,
  "items": [
    {
      "medicine_name": "string",
      "generic_name": "string",
      "company": "string",
      "batch_number": "string",
      "expiry_date": "string",
      "quantity": 0,
      "purchase_price": 0.0,
      "selling_price": 0.0
    }
  ]
}"""


class GroqService:
    """Groq Cloud AI service for invoice text parsing."""

    @staticmethod
    def is_configured() -> bool:
        """Check if the Groq API key is set."""
        key = _get_api_key()
        return bool(key)

    @staticmethod
    def get_model() -> str:
        return _get_model()

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
        api_key = _get_api_key()
        if not api_key:
            raise GroqConfigError(
                "Groq API key is not configured.\n\n"
                "Create a .env file in the project root with:\n"
                "GROQ_API_KEY=your_api_key_here\n"
                "GROQ_MODEL=llama-3.3-70b-versatile"
            )

        model = _get_model()
        if not ocr_text or not ocr_text.strip():
            raise GroqParseError("No OCR text provided — nothing to analyze.")

        try:
            from groq import Groq
        except ImportError:
            raise GroqConfigError(
                "Groq SDK is not installed.\n"
                "Install with: pip install groq"
            )

        try:
            client = Groq(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            "Extract structured invoice data from the following OCR text. "
                            "Return ONLY valid JSON.\n\n"
                            f"{ocr_text}"
                        ),
                    },
                ],
                temperature=0.1,
                max_tokens=4096,
            )
        except ImportError:
            raise GroqConfigError(
                "Groq SDK is not installed.\n"
                "Install with: pip install groq"
            )
        except Exception as exc:
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

        # Parse response
        if not response.choices:
            raise GroqAPIError("Groq returned an empty response (no choices).")

        raw_content = response.choices[0].message.content
        if not raw_content:
            raise GroqAPIError("Groq returned an empty message content.")

        return GroqService._parse_json(raw_content)

    @staticmethod
    def _parse_json(raw: str) -> InvoiceData:
        """Parse the raw AI response into InvoiceData."""
        cleaned = raw.strip()

        # Strip markdown code fences if present
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first line (```json or ```) and last line (```)
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
                    items.append(InvoiceItem(
                        medicine_name=str(item.get("medicine_name", "")),
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
