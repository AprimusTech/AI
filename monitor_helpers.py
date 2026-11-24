"""Pure helpers for the experimental read-only WhatsApp monitor."""
import hashlib
import json
from pathlib import Path


def load_allowed_contacts(contacts_file: Path):
    if not contacts_file.exists():
        return {}
    raw = json.loads(contacts_file.read_text(encoding="utf-8"))
    return {
        str(settings.get("name", "")).strip().casefold(): phone
        for phone, settings in raw.items()
        if settings.get("enabled") and str(settings.get("name", "")).strip()
    }


def message_fingerprint(contact_name, message_text):
    normalized = f"{contact_name.casefold().strip()}\n{message_text.strip()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
