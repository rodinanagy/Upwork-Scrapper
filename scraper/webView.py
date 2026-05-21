#!/usr/bin/env python3
"""
PyBrowser — powered by pywebview (native OS browser engine)
Install: pip install pywebview
On Linux you also need: pip install pywebview[gtk]
  and: sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.0
"""

import webview
import threading

HOME = "https://www.google.com"

HTML_CHROME = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: #313244;
    font-family: Consolas, monospace;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    height: 44px;
    overflow: hidden;
  }
  button {
    background: #45475a;
    color: #cdd6f4;
    border: none;
    border-radius: 4px;
    font-size: 15px;
    width: 32px; height: 32px;
    cursor: pointer;
    flex-shrink: 0;
  }
  button:hover { background: #585b70; }
  button:disabled { opacity: 0.35; cursor: default; }
  #url {
    flex: 1;
    background: #1e1e2e;
    color: #cdd6f4;
    border: none;
    border-radius: 4px;
    font-size: 13px;
    font-family: Consolas, monospace;
    padding: 0 10px;
    height: 32px;
    outline: none;
  }
  #url:focus { box-shadow: 0 0 0 2px #89b4fa; }
  #go {
    width: auto;
    padding: 0 14px;
    font-size: 12px;
  }
</style>
</head>
<body>
  <button id="back"    onclick="nav('back')"    title="Back">◀</button>
  <button id="fwd"     onclick="nav('fwd')"     title="Forward">▶</button>
  <button             onclick="nav('reload')"  title="Reload">↺</button>
  <button             onclick="nav('home')"    title="Home">⌂</button>
  <input  id="url" type="text" placeholder="Enter URL or search…"
          onkeydown="if(event.key==='Enter') nav('go')"
          onfocus="this.select()"/>
  <button id="go" onclick="nav('go')">Go</button>

  <script>
    function nav(action) {
      const url = document.getElementById('url').value.trim();
      pywebview.api.navigate(action, url);
    }
    function setUrl(u) {
      document.getElementById('url').value = u;
    }
    function setButtons(canBack, canFwd) {
      document.getElementById('back').disabled = !canBack;
      document.getElementById('fwd').disabled  = !canFwd;
    }
  </script>
</body>
</html>
"""


class BrowserAPI:
    """Exposed to the toolbar JS via pywebview.api.*"""

    def __init__(self, content_window):
        self.win = content_window
        self.history = []
        self.forward_stack = []

    def navigate(self, action: str, url: str = ""):
        if action == "back":
            self._go_back()
        elif action == "fwd":
            self._go_forward()
        elif action == "reload":
            self.win.reload()
        elif action == "home":
            self._load(HOME)
        elif action == "go":
            self._load(self._normalise(url))

    def _normalise(self, url: str) -> str:
        url = url.strip()
        if not url:
            return HOME
        if not url.startswith(("http://", "https://")):
            if "." not in url.split("/")[0]:
                return f"https://www.google.com/search?q={url.replace(' ', '+')}"
            return "https://" + url
        return url

    def _load(self, url: str):
        self.forward_stack.clear()
        self.history.append(url)
        self.win.load_url(url)
        self._sync_toolbar(url)

    def _go_back(self):
        if len(self.history) > 1:
            self.forward_stack.append(self.history.pop())
            url = self.history[-1]
            self.win.load_url(url)
            self._sync_toolbar(url)

    def _go_forward(self):
        if self.forward_stack:
            url = self.forward_stack.pop()
            self.history.append(url)
            self.win.load_url(url)
            self._sync_toolbar(url)

    def _sync_toolbar(self, url: str):
        # Update URL bar and button states in the toolbar window
        safe = url.replace("'", "\\'")
        toolbar_win.evaluate_js(f"setUrl('{safe}')")
        toolbar_win.evaluate_js(
            f"setButtons({str(len(self.history) > 1).lower()}, "
            f"{str(bool(self.forward_stack)).lower()})"
        )


def on_content_loaded(win, api):
    """Called when the content window finishes loading a page."""
    def handler():
        url = win.get_current_url() or ""
        api.history.append(url)
        safe = url.replace("'", "\\'")
        toolbar_win.evaluate_js(f"setUrl('{safe}')")
        toolbar_win.evaluate_js(
            f"setButtons({str(len(api.history) > 1).lower()}, "
            f"{str(bool(api.forward_stack)).lower()})"
        )
        # Mirror page title
        toolbar_win.title = win.title or "PyBrowser"
    # small delay so win.get_current_url() is populated
    threading.Timer(0.3, handler).start()


if __name__ == "__main__":
    # Content window (full browser engine)
    content_win = webview.create_window(
        "PyBrowser",
        url=HOME,
        width=1200,
        height=756,
        min_size=(400, 300),
    )

    # Toolbar window (thin chrome bar, no native controls)
    toolbar_win = webview.create_window(
        "PyBrowser — toolbar",
        html=HTML_CHROME,
        width=1200,
        height=44,
        resizable=False,
        frameless=False,
    )

    api = BrowserAPI(content_win)
    toolbar_win.expose(api.navigate)   # pywebview.api.navigate in JS

    # Sync URL bar whenever content window navigates
    content_win.events.loaded += lambda: on_content_loaded(content_win, api)

    webview.start(debug=False)
