"""Visit the deployed Streamlit app and click through the sleep screen if present.

A plain HTTP GET isn't enough to keep a Streamlit Community Cloud app awake or to
wake a sleeping one — the app only counts a real browser session (over websocket)
as traffic, and waking it requires clicking the "Yes, get this app back up" button
on the hibernation screen. Playwright drives an actual headless browser to do both.
"""

import os
import sys

from playwright.sync_api import sync_playwright

APP_URL = os.environ["APP_URL"]
WAKE_BUTTON_TEXT = "Yes, get this app back up"


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(APP_URL, wait_until="networkidle", timeout=60_000)

        wake_button = page.get_by_role("button", name=WAKE_BUTTON_TEXT)
        try:
            wake_button.wait_for(state="visible", timeout=15_000)
        except Exception:
            print("App is already awake.")
            browser.close()
            return

        print("App is asleep, clicking wake button...")
        wake_button.click()

        try:
            wake_button.wait_for(state="hidden", timeout=60_000)
            print("App woke up successfully.")
        except Exception:
            print("Clicked wake button but app did not confirm wake-up in time.")
            sys.exit(1)

        browser.close()


if __name__ == "__main__":
    main()
