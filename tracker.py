#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json, re, os, hashlib
from datetime import datetime, timezone
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from dateutil import tz

# ---- Einstellungen ----
CODES_FILE = "codes.json"
SOURCES_FILE = "sources.json"
TZ = tz.gettz("Europe/Berlin")

# Regex: 5 Gruppen à 4–5 Zeichen (alphanum), getrennt durch - oder Gedankenstrich
CODE_RE = re.compile(r"\b[A-Z0-9]{4,5}(?:[–-][A-Z0-9]{4,5}){4}\b", re.IGNORECASE)


def load_sources():
    with open(SOURCES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["sources"]


def load_codes():
    if not os.path.exists(CODES_FILE):
        return []
    with open(CODES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_codes(codes):
    with open(CODES_FILE, "w", encoding="utf-8") as f:
        json.dump(codes, f, ensure_ascii=False, indent=2)


def normalize_code(code: str) -> str:
    # Gedankenstrich in normalen Bindestrich umwandeln
    return code.upper().replace("–", "-")


def fetch_text(url: str) -> str:
    headers = {
        "User-Agent": "BL4-Shift-Tracker/1.0 (+github)"
    }
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    if "html" in (r.headers.get("Content-Type", "")).lower():
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return " ".join(soup.get_text(separator=" ").split())
    return r.text


def post_to_discord(webhook_url: str, new_items: list):
    """
    Sendet nur die Codes (ohne Quellenangabe) an Discord.
    """
    if not webhook_url or not new_items:
        return

    # Überschrift + Zeit
    lines = [
        "**Neue Borderlands 4 SHiFT-Codes** _({})_".format(
            datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
        )
    ]
    # Nur die Codes selbst, ohne 'Quelle'
    for item in new_items:
        lines.append(f"- `{item['code']}`")

    payload = {"content": "\n".join(lines)}
    try:
        r = requests.post(webhook_url, json=payload, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"[WARN] Discord Post fehlgeschlagen: {e}")


def main():
    sources = load_sources()
    existing = load_codes()
    known = {x["code"] for x in existing}

    newly_found = []
    for url in sources:
        try:
            text = fetch_text(url)
        except Exception as e:
            print(f"[WARN] Quelle nicht erreichbar: {url} ({e})")
            continue

        for m in CODE_RE.finditer(text):
            code = normalize_code(m.group(0))
            if code not in known:
                entry = {
                    "code": code,
                    "first_seen": datetime.now(timezone.utc).isoformat(),
                    "source": url,
                    "source_host": urlparse(url).netloc
                }
                newly_found.append(entry)
                known.add(code)

    if newly_found:
        save_codes(newly_found + existing)
        print(f"[INFO] Neue Codes: {len(newly_found)}")
        webhook = os.getenv("DISCORD_WEBHOOK_URL", "")
        if webhook:
            post_to_discord(webhook, newly_found)
    else:
        print("[INFO] Keine neuen Codes gefunden.")


if __name__ == "__main__":
    main()
