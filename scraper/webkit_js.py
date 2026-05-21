"""
Evaluate JS by calling pywebview's own internal evaluate_js on the BrowserView,
bypassing the window-level wrapper that injects the pywebview bridge.
This avoids both the 'window.pywebview undefined' error and the world-boundary 601 error.
"""

import json
import threading
from webview.platforms.gtk import BrowserView


def eval_js(window, code: str, timeout: float = 15.0) -> str | None:
    """
    Run JS in the live page context and return a string result.

    pywebview 5.x auto-converts JS values to Python objects (list, dict, bool, …).
    We re-serialize non-strings with json.dumps so callers always get a consistent
    JSON-compatible string (e.g. 'true', '["url1",...]', '{"title":...}').

    Wraps bv.evaluate_js() in a daemon thread to enforce a real timeout —
    pywebview's internal semaphore has no timeout and can block forever.
    """
    bv = BrowserView.instances.get(window.uid)
    if bv is None:
        print(f"[webkit_js] BrowserView not found for uid={window.uid!r}", flush=True)
        return None

    result_box = [None]
    done = threading.Event()

    def _run():
        try:
            result = bv.evaluate_js(code)
            if result is None:
                pass  # leave result_box[0] as None
            elif isinstance(result, str):
                result_box[0] = result
            else:
                # bool, int, list, dict — re-serialize to valid JSON string
                result_box[0] = json.dumps(result)
        except Exception as e:
            print(f"[webkit_js] error: {e}", flush=True)
        finally:
            done.set()

    threading.Thread(target=_run, daemon=True).start()
    if not done.wait(timeout=timeout):
        print(f"[webkit_js] JS eval timed out after {timeout}s", flush=True)
    return result_box[0]
