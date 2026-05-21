"""Flask web UI for the Upwork scraper + LinkedIn poster finder."""
import csv
import json
import os
import subprocess
import threading
import time

from flask import Flask, Response, jsonify, request, send_file, send_from_directory

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_PYTHON = os.path.join(ROOT, ".venv", "bin", "python")

app = Flask(__name__, static_folder="static")

# One scrape at a time
_state = {
    "process": None,
    "logs": [],
    "done": True,
    "output_path": os.path.join(ROOT, "data", "jobs.csv"),
}
_lock = threading.Lock()


# ── static pages ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/finder")
def finder():
    return send_from_directory("static", "finder.html")


# ── scraper API ───────────────────────────────────────────────────────────────

@app.route("/api/status")
def status():
    with _lock:
        proc = _state["process"]
        running = proc is not None and proc.poll() is None
        return jsonify({"running": running, "log_count": len(_state["logs"]), "done": _state["done"]})


@app.route("/api/scrape", methods=["POST"])
def start_scrape():
    with _lock:
        proc = _state["process"]
        if proc is not None and proc.poll() is None:
            return jsonify({"error": "Already running"}), 400

        data = request.get_json(force=True) or {}
        keywords = (data.get("keywords") or "").strip()
        if not keywords:
            return jsonify({"error": "Keywords are required"}), 400

        max_jobs = max(1, int(data.get("max_jobs") or 50))
        debug = bool(data.get("debug"))
        rel = (data.get("output") or "data/jobs.csv").lstrip("/")
        output_path = os.path.join(ROOT, rel)

        _state["logs"] = []
        _state["done"] = False
        _state["output_path"] = output_path

        cmd = [VENV_PYTHON, "-m", "scraper"] + keywords.split()
        cmd += ["--output", output_path, "--max-jobs", str(max_jobs)]
        if debug:
            cmd.append("--debug")

        env = {**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":0")}
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, cwd=ROOT, env=env,
        )
        _state["process"] = proc

    def _read():
        for line in proc.stdout:
            with _lock:
                _state["logs"].append(line.rstrip("\n"))
        with _lock:
            _state["done"] = True

    threading.Thread(target=_read, daemon=True).start()
    return jsonify({"status": "started"})


@app.route("/api/logs")
def stream_logs():
    since = int(request.args.get("since", 0))

    def generate():
        pos = since
        while True:
            with _lock:
                batch = _state["logs"][pos:]
                total = len(_state["logs"])
                done = _state["done"]

            for line in batch:
                yield f"data: {json.dumps(line)}\n\n"
            pos += len(batch)

            if done and pos >= total:
                yield 'data: {"__done__":true}\n\n'
                break
            time.sleep(0.3)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/stop", methods=["POST"])
def stop_scrape():
    with _lock:
        proc = _state.get("process")
    if proc and proc.poll() is None:
        proc.terminate()
    return jsonify({"status": "stopped"})


@app.route("/api/jobs")
def get_jobs():
    with _lock:
        path = _state["output_path"]
    try:
        rows = []
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rows.append(dict(row))
        return jsonify(rows)
    except FileNotFoundError:
        return jsonify([])


@app.route("/api/download")
def download():
    with _lock:
        path = _state["output_path"]
    return send_file(path, as_attachment=True, download_name="jobs.csv")


# ── LinkedIn finder API ───────────────────────────────────────────────────────

_SEARCH_TOOL = [{
    "name": "search_web",
    "description": (
        "Search the web and LinkedIn for real people. "
        "Good queries: 'site:linkedin.com/in [company name] founder', "
        "'[company] CEO linkedin', 'site:linkedin.com [technology] [city] [role]'. "
        "Use multiple targeted searches to narrow down the actual person."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Web search query"}
        },
        "required": ["query"],
    },
}]


def _search_web(query: str) -> list[dict]:
    try:
        from duckduckgo_search import DDGS
        results = DDGS().text(query, max_results=6) or []
        return [
            {
                "title":   r.get("title", ""),
                "url":     r.get("href", ""),
                "snippet": r.get("body", "")[:400],
            }
            for r in results
        ]
    except Exception as e:
        return [{"error": f"Search failed: {e}"}]


def _build_prompt(job: dict) -> str:
    skills_raw = job.get("skills", "")
    try:
        skills = ", ".join(json.loads(skills_raw))
    except Exception:
        skills = skills_raw

    fields = [
        ("Job Title",                    job.get("title")),
        ("Category",                     job.get("category")),
        ("Budget",                       job.get("budget")),
        ("Job Type",                     job.get("job_type")),
        ("Skills Required",              skills),
        ("Experience Level",             job.get("experience_level")),
        ("Client Country",               job.get("client_country")),
        ("Client Total Spent on Upwork", job.get("client_total_spent")),
        ("Client Hires",                 job.get("client_hires")),
        ("Client Member Since",          job.get("client_member_since")),
        ("Description",                  job.get("description")),
    ]
    details = "\n".join(f"- **{k}:** {v}" for k, v in fields if v)

    return f"""You are an investigator helping find the person who posted this Upwork job so we can reach them on LinkedIn.

Job posting:
{details}

## Step 1 — Analyze the job
Read the description carefully. Extract every clue: company name, product name, website, technology stack, industry, location, writing style, budget level. Think about what kind of person hires for this (founder, CTO, product manager, recruiter?).

## Step 2 — Search
Use the search_web tool 3-5 times with different queries to find real people:
- If a company name is mentioned: "site:linkedin.com/in [company] [role]", "[company] founder linkedin", "[company] CEO"
- If no company name: "site:linkedin.com [tech stack] [country] startup [role]", "[industry] [city] founder linkedin"
- Also try searching the job description phrases in quotes — sometimes the same text appears on their website or social media

## Step 3 — Always give candidates
You MUST always return 3-5 candidates. Never say you cannot find the poster.
- If you found real people via search: list them with their actual LinkedIn URLs
- If search gave no direct match: reason from the job details to identify the most likely type of person, then suggest the closest real profiles you did find, or construct the most likely LinkedIn search that would find them

## Output format (for each candidate):

**[Full Name or "Likely: [Role Title]"]** — [Title] at [Company]
LinkedIn: [URL if found, or best LinkedIn search URL]
Confidence: High / Medium / Low
Why: [what specifically from this job matches this person]

Most likely candidate first. Always give something useful — a reasoned guess with a search link is better than nothing."""


@app.route("/api/find-poster", methods=["POST"])
def find_poster():
    data = request.get_json(force=True) or {}
    job = data.get("job", {})
    api_key = data.get("api_key") or os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_key:
        return jsonify({"error": "No API key provided. Enter it in the UI or set ANTHROPIC_API_KEY."}), 400

    prompt = _build_prompt(job)

    def generate():
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            messages = [{"role": "user", "content": prompt}]

            for _ in range(8):  # max 8 search rounds
                response = client.messages.create(
                    model="claude-opus-4-7",
                    max_tokens=2000,
                    tools=_SEARCH_TOOL,
                    messages=messages,
                )

                if response.stop_reason == "tool_use":
                    tool_results = []
                    for block in response.content:
                        if block.type == "tool_use" and block.name == "search_web":
                            query = block.input.get("query", "")
                            yield f"data: {json.dumps({'type': 'search', 'query': query})}\n\n"

                            hits = _search_web(query)
                            count = sum(1 for h in hits if "error" not in h)
                            yield f"data: {json.dumps({'type': 'result', 'count': count})}\n\n"

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(hits, ensure_ascii=False),
                            })

                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({"role": "user", "content": tool_results})

                else:
                    # Final answer — fake-stream it in chunks so the UI feels live
                    final = "".join(
                        block.text for block in response.content if hasattr(block, "text")
                    )
                    for i in range(0, len(final), 25):
                        yield f"data: {json.dumps({'type': 'text', 'text': final[i:i+25]})}\n\n"
                        time.sleep(0.012)
                    break

            yield 'data: {"type":"done"}\n\n'

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            yield 'data: {"type":"done"}\n\n'

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


if __name__ == "__main__":
    print("Open http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
