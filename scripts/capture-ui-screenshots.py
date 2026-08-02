#!/usr/bin/env python3
"""Capture v0.2.0-alpha UAT UI screenshots for user guide Ch.2.

Requires: pip install playwright && playwright install chromium
Server:   make serve (port 8001)
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

BASE = "http://127.0.0.1:8001"
OUT = Path(__file__).resolve().parents[1] / "docs/user-guide/images/v0.2.0-alpha"
O2C = "JRN-F5F81F203D"
SUPPLY = "JRN-4323664EC6"


def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def shot(
    page: Page,
    name: str,
    url: str,
    *,
    click_role: tuple[str, str] | None = None,
    wait_ms: int = 2000,
    load_ms: int = 2000,
) -> None:
    page.goto(url, wait_until="networkidle")
    page.wait_for_timeout(load_ms)
    if click_role:
        role, label = click_role
        page.get_by_role(role, name=label).first.click(timeout=15000)
        page.wait_for_timeout(wait_ms)
    page.screenshot(path=str(OUT / name), full_page=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        viewport = {"width": 1400, "height": 900}

        shot(
            browser.new_page(viewport=viewport),
            "alpha-U1-journeys-grid.png",
            f"{BASE}/ui#/",
            load_ms=3000,
        )
        shot(
            browser.new_page(viewport=viewport),
            "alpha-U2-o2c-detail.png",
            f"{BASE}/ui#/journey/{O2C}",
            load_ms=3000,
        )
        shot(
            browser.new_page(viewport=viewport),
            "alpha-U3-start-processing.png",
            f"{BASE}/ui#/journey/{O2C}",
            click_role=("button", "Start Processing"),
            load_ms=3000,
            wait_ms=3000,
        )
        shot(
            browser.new_page(viewport=viewport),
            "alpha-U4-job-history.png",
            f"{BASE}/ui#/journey/{O2C}/jobs",
            load_ms=4000,
        )
        shot(
            browser.new_page(viewport=viewport),
            "alpha-U5-logs-drawer.png",
            f"{BASE}/ui#/journey/{SUPPLY}/jobs",
            click_role=("button", "Logs"),
            load_ms=5000,
            wait_ms=4000,
        )

        browser.close()


if __name__ == "__main__":
    main()
