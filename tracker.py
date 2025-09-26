#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, re, os, hashlib
from datetime import datetime, timezone
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from dateutil import tz

CODES_FILE = "codes.json"
SOURCES_FILE = "sources.json"
TZ = tz.gettz("Europe/Berlin")
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
    return code.upper().replace("–", "-")

def fetch_text(url: str) -> str:
    headers = {"User-Agent": "BL4-Shift-Tracker/1.0 (+github)"}
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    if "html" in (r.headers.get("Content-Type","")).lower():
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script","style","noscript"]):
            tag.decompose()
        return " ".join(soup.get_text(separator=" ").split())
    return r.text

def post_to_discord(webhook_url: str, new_items: list):
    if not webhook_url or not new_items:
        return
    from datetime import datetime
    from dateutil import tz
    lines = ["**Neue Borderlands 4 SHiFT-Codes** _({})_".format(
        datetime.now(tz.gettz("Europe/Berlin")).strftime("%Y-%m-%d %H:%M"))]
    for it in new_items:
        lines.append(f"- `{it['code']}` — Quelle: {it.get('source_host','')}")
    try:
        requests.post(webhook_url, json={"content":"\n".join(lines)}, timeout=15).raise_for_status()
    except Exception as e:
        print(f"[WARN] Discord Post fehlgeschlagen: {e}")

def main():
    sources = load_sources()
    existing = load_codes()
    known = {x["code"] for x in existing}
    newly = []
    for url in sources:
        try:
            text = fetch_text(url)
        except Exception as e:
            print(f"[WARN] Quelle nicht erreichbar: {url} ({e})")
            continue
        for m in CODE_RE.finditer(text):
            code = normalize_code(m.group(0))
            if code not in known:
                newly.append({
                    "code": code,
                    "first_seen": datetime.now(timezone.utc).isoformat(),
                    "source": url,
                    "source_host": urlparse(url).netloc
                })
                known.add(code)
    if newly:
        save_codes(newly + existing)
        print(f"[INFO] Neue Codes: {len(newly)}")
        post_to_discord(os.getenv("DISCORD_WEBHOOK_URL",""), newly)
    else:
        print("[INFO] Keine neuen Codes gefunden.")

if __name__ == "__main__":
    main()
