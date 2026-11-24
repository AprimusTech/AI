"""Day 4.1: experimental WhatsApp read-only monitor that generates local AI drafts.

No WhatsApp message sending is implemented. Chat matching is by display name only,
not verified phone identity; inspect matches manually before trusting the drafts.
"""
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright
from config import DATA_DIR
from database import initialize_database, log_message, queue_draft
from ai_engine import generate_reply
from monitor_helpers import load_allowed_contacts, message_fingerprint

BASE = Path(__file__).resolve().parent
PROFILE = DATA_DIR / "whatsapp_browser_profile"
CONTACTS_FILE = BASE / "contacts.json"
POLL_SECONDS = 5


async def monitor():
    initialize_database()
    allowed = load_allowed_contacts(CONTACTS_FILE)
    if not allowed:
        print("No enabled named contacts found in contacts.json. Enable/name contacts first.")
        return
    PROFILE.mkdir(parents=True, exist_ok=True)
    print("Starting read-only WhatsApp draft monitor.")
    print("Uses your existing Day 4 browser profile; close the other WhatsApp browser first.")
    print("No messages are sent. Stop with Ctrl+C.")
    print("WARNING: Experimental name-based chat matching; verify every draft manually.")
    seen = set()
    baseline_mode = True
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(str(PROFILE), headless=False)
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://web.whatsapp.com", wait_until="domcontentloaded")
        try:
            await page.wait_for_selector("div[role='grid'], canvas[aria-label*='Scan']", timeout=120000)
        except Exception:
            print("Timed out waiting for WhatsApp. Check browser login and retry.")
            await context.close()
            return
        print("WhatsApp Web is ready. Monitoring enabled contacts...")
        try:
            while True:
                rows = await page.locator("[role='listitem'], [role='row']").all()
                matched = []
                for row in rows:
                    try:
                        aria = (await row.get_attribute("aria-label") or "").strip()
                        titleloc = row.locator("[title]")
                        title = await titleloc.first.get_attribute("title") if await titleloc.count() else ""
                        name = (title or aria).strip()
                        if name.casefold() in allowed:
                            matched.append((row, name))
                    except Exception:
                        continue
                for row, name in matched:
                    try:
                        await row.click(timeout=2500)
                        await page.wait_for_timeout(500)
                        incoming = page.locator(".message-in .selectable-text")
                        count = await incoming.count()
                        if not count:
                            continue
                        text = (await incoming.nth(count - 1).inner_text()).strip()
                        phone = allowed[name.casefold()]
                        fp = message_fingerprint(name, text)
                        if not text or fp in seen:
                            continue
                        seen.add(fp)
                        if baseline_mode:
                            continue
                        incoming_id = log_message(phone, "incoming", text, status="monitor_detected")
                        print(f"\n[INCOMING DETECTED: {name} | {phone}]\n{text}")
                        try:
                            draft = generate_reply(phone, text)
                            draft_id = log_message(phone, "draft", draft, status="generated_from_monitor")
                            queue_draft(phone, incoming_id, draft)
                            print(f"[AI DRAFT #{draft_id} — NOT SENT]\n{draft}\n")
                        except Exception as exc:
                            print(f"[DRAFT ERROR — message was logged, nothing sent] {exc}")
                    except Exception:
                        continue
                if baseline_mode:
                    baseline_mode = False
                    print("Baseline scan complete. Waiting for new incoming messages; older last messages will not be drafted.")
                await asyncio.sleep(POLL_SECONDS)
        except KeyboardInterrupt:
            print("Monitor stopped by user.")
        finally:
            await context.close()


if __name__ == "__main__":
    asyncio.run(monitor())
