import json
import threading
import time
import urllib.parse

import webview

from .webkit_js import eval_js
from .js_extractor import (
    JS_GET_JOB_LINKS, JS_GET_NEXT_PAGE,
    JS_GET_JOB_INFO, JS_GET_NEXT_JOB,
    JS_IS_CHALLENGE, JS_HAS_JOBS, JS_HAS_H1,
    JS_DEBUG_DUMP,
    parse_job_info,
)
from .csv_writer import CsvWriter

SEARCH_BASE = "https://www.upwork.com/nx/search/jobs/"

# Event fired by the loaded callback when a new page finishes loading
_page_loaded = threading.Event()


def _build_search_url(query: str, page: int = 1) -> str:
    params = {"q": query, "sort": "recency", "page": page}
    return f"{SEARCH_BASE}?{urllib.parse.urlencode(params)}"


def _navigate(window, url: str):
    _page_loaded.clear()
    window.load_url(url)


def _wait_page_load(timeout: float = 30.0) -> bool:
    """Block until the loaded event fires or timeout."""
    return _page_loaded.wait(timeout=timeout)


def _is_challenge(window) -> bool:
    result = eval_js(window, JS_IS_CHALLENGE)
    return result == "true"


def _wait_past_challenge(window, poll: float = 2.0):
    """Block until the user has solved any challenge page."""
    while True:
        if _is_challenge(window):
            print("[scraper] Challenge detected — solve it in the browser window ...", flush=True)
            time.sleep(poll)
        else:
            return


_FALSY = {"false", "null", "undefined", "0", "none", ""}


def _poll_until(window, js_condition: str, timeout: float = 20.0) -> bool:
    """Poll until js_condition is truthy or timeout. Accepts bool and string results."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _is_challenge(window):
            _wait_past_challenge(window)
            deadline = time.time() + timeout
        result = eval_js(window, js_condition)
        if result is not None and str(result).lower().strip() not in _FALSY:
            return True
        time.sleep(1.5)
    return False


def _scrape(window, query: str, output_path: str, max_jobs: int, debug: bool = False):
    print("[scraper] Waiting for initial page load ...", flush=True)
    _wait_page_load(timeout=15)

    # Start on the search page
    search_url = _build_search_url(query, 1)
    print(f"[scraper] Navigating to search: {search_url}", flush=True)
    _navigate(window, search_url)
    _wait_page_load(timeout=30)
    _wait_past_challenge(window)

    # Wait for job tiles to render (React can be slow); proceed anyway after timeout
    if not _poll_until(window, JS_HAS_JOBS, timeout=60):
        print("[scraper] Jobs not visible yet — trying anyway …", flush=True)
    time.sleep(2)

    scraped = 0
    search_page_num = 1

    with CsvWriter(output_path) as writer:
        while scraped < max_jobs and search_url:
            print(f"\n[scraper] ── Search page {search_page_num} ──", flush=True)

            if search_page_num > 1:
                _navigate(window, search_url)
                _wait_page_load(timeout=30)
                _wait_past_challenge(window)
                if not _poll_until(window, JS_HAS_JOBS, timeout=60):
                    print("[scraper] Jobs not visible yet — trying anyway …", flush=True)
                time.sleep(2)

            raw = eval_js(window, JS_GET_JOB_LINKS)
            try:
                job_urls = json.loads(raw) if raw else []
                if not isinstance(job_urls, list):
                    job_urls = []
            except Exception as e:
                print(f"[scraper] Could not parse job links (raw={raw!r}): {e}", flush=True)
                job_urls = []
            raw_next = eval_js(window, JS_GET_NEXT_PAGE)
            next_search_url = raw_next if raw_next and raw_next != "null" else None

            if not job_urls:
                print("[scraper] No job links found on this page — moving on.", flush=True)
                search_url = next_search_url
                search_page_num += 1
                continue

            print(f"[scraper] Found {len(job_urls)} jobs.", flush=True)

            for job_url in job_urls:
                if scraped >= max_jobs:
                    break

                print(f"[scraper] ({scraped + 1}/{max_jobs}) {job_url}", flush=True)

                _navigate(window, job_url)
                _wait_page_load(timeout=30)
                _wait_past_challenge(window)

                if not _poll_until(window, JS_HAS_H1, timeout=20):
                    print("[scraper]   h1 not found yet — waiting a bit more …", flush=True)
                time.sleep(2)  # let React finish rendering

                if debug and scraped == 0:
                    raw_dump = eval_js(window, JS_DEBUG_DUMP)
                    if raw_dump:
                        dump_path = output_path.replace("jobs.csv", "debug_dump.json")
                        import pathlib, os
                        dump_path = os.path.join(os.path.dirname(output_path), "debug_dump.json")
                        pathlib.Path(dump_path).write_text(raw_dump, encoding="utf-8")
                        print(f"[scraper]   Debug dump saved to {dump_path!r}", flush=True)

                raw_info = eval_js(window, JS_GET_JOB_INFO)
                info = parse_job_info(raw_info, job_url)

                raw_next_job = eval_js(window, JS_GET_NEXT_JOB)
                next_job = raw_next_job if raw_next_job and raw_next_job != "null" else None

                writer.write(info, next_job)
                scraped += 1
                print(f"[scraper]   Saved: {info.get('title', '(no title)')!r}", flush=True)

                time.sleep(1.5)

            search_url = next_search_url
            search_page_num += 1

    print(f"\n[scraper] Done — {scraped} jobs saved to {output_path!r}", flush=True)


def run(query: str, output_path: str, max_jobs: int = 100, debug: bool = False, **_kwargs):
    window = webview.create_window(
        title="Upwork Scraper — solve any verification here",
        url=_build_search_url(query, 1),
        width=1280,
        height=900,
    )

    def on_loaded():
        _page_loaded.set()

    window.events.loaded += on_loaded

    thread = threading.Thread(
        target=_scrape,
        args=(window, query, output_path, max_jobs, debug),
        daemon=True,
    )
    thread.start()

    webview.start()
    thread.join(timeout=5)
