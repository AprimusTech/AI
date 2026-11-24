import json
import tempfile
import unittest
from pathlib import Path
from monitor_helpers import load_allowed_contacts, message_fingerprint

class MonitorHelperTests(unittest.TestCase):
    def test_whitelist_only_enabled_named_contacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "contacts.json"
            p.write_text(json.dumps({
                "911": {"name": "Alpha", "enabled": True},
                "922": {"name": "Beta", "enabled": False},
                "933": {"name": "", "enabled": True},
            }), encoding="utf-8")
            self.assertEqual(load_allowed_contacts(p), {"alpha": "911"})

    def test_fingerprint_same_for_same_contact_and_text(self):
        self.assertEqual(message_fingerprint("Alpha", "Hi"), message_fingerprint("Alpha", "Hi"))

    def test_fingerprint_changes_for_other_contact_or_text(self):
        base = message_fingerprint("Alpha", "Hi")
        self.assertNotEqual(base, message_fingerprint("Beta", "Hi"))
        self.assertNotEqual(base, message_fingerprint("Alpha", "Hello"))

if __name__ == "__main__":
    unittest.main()
