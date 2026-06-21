import asyncio
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from .main import review_repo

app = FastAPI(title="SecureReview")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

DB_PATH = os.getenv("SECUREREVIEW_DB", "security-review/db.sqlite")
OUTPUT_DIR = os.getenv("SECUREREVIEW_OUTPUT", "security-review")

# In-memory scan state: scan_id -> {status, messages, result}
_scans: dict[str, dict] = {}
_scans_lock = threading.Lock()

SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
SEVERITY_COLORS = {
    "CRITICAL": "#ef4444",
    "HIGH":     "#f97316",
    "MEDIUM":   "#eab308",
    "LOW":      "#3b82f6",
    "INFO":     "#6b7280",
}


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _severity_counts() -> dict:
    try:
        with _db() as conn:
            rows = conn.execute(
                "SELECT severity, COUNT(*) as n FROM findings GROUP BY severity"
            ).fetchall()
        return {r["severity"]: r["n"] for r in rows}
    except Exception:
        return {}


def _trend_data(days: int = 30) -> list[dict]:
    try:
        with _db() as conn:
            rows = conn.execute("""
                SELECT DATE(s.timestamp) as day, f.severity, COUNT(*) as n
                FROM findings f JOIN scans s ON f.scan_id = s.id
                WHERE s.timestamp >= DATE('now', ?)
                GROUP BY day, f.severity
                ORDER BY day
            """, (f"-{days} days",)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _owasp_counts() -> list[dict]:
    try:
        with _db() as conn:
            rows = conn.execute("""
                SELECT owasp, COUNT(*) as n FROM findings
                WHERE owasp IS NOT NULL AND owasp != ''
                GROUP BY owasp ORDER BY n DESC LIMIT 10
            """).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _close_rate() -> float:
    try:
        with _db() as conn:
            total = conn.execute("SELECT COUNT(*) FROM remediations").fetchone()[0]
            merged = conn.execute(
                "SELECT COUNT(*) FROM remediations WHERE merged_at IS NOT NULL"
            ).fetchone()[0]
        return round(merged / total * 100, 1) if total else 0.0
    except Exception:
        return 0.0


def _get_findings(severity=None, owasp=None, status=None, limit=100) -> list[dict]:
    try:
        where, params = [], []
        if severity:
            where.append("f.severity = ?"); params.append(severity)
        if owasp:
            where.append("f.owasp = ?"); params.append(owasp)
        if status:
            where.append("f.status = ?"); params.append(status)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        with _db() as conn:
            rows = conn.execute(f"""
                SELECT f.*, s.repo_path, s.timestamp as scan_time
                FROM findings f JOIN scans s ON f.scan_id = s.id
                {clause}
                ORDER BY CASE f.severity
                    WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2
                    WHEN 'MEDIUM' THEN 3 WHEN 'LOW' THEN 4 ELSE 5 END,
                    f.id DESC
                LIMIT ?
            """, (*params, limit)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _get_finding(finding_id: int) -> dict | None:
    try:
        with _db() as conn:
            row = conn.execute(
                "SELECT f.*, s.repo_path FROM findings f JOIN scans s ON f.scan_id=s.id WHERE f.id=?",
                (finding_id,)
            ).fetchone()
        return dict(row) if row else None
    except Exception:
        return None


# ── Background scan runner ─────────────────────────────────────────────────────

def _scan_thread(scan_id: str, repo_path: str, output_dir: str, prompt: str | None, remediate: bool):
    def log(msg: str):
        with _scans_lock:
            _scans[scan_id]["messages"].append(msg)

    log(f"Starting scan of {repo_path}…")
    try:
        result = review_repo(
            repo_path=repo_path,
            output_dir=output_dir,
            prompt=prompt,
            remediate=remediate,
            db_path=f"{output_dir}/db.sqlite",
        )
        with _scans_lock:
            _scans[scan_id]["status"] = "done"
            _scans[scan_id]["result"] = result
        log("Scan complete.")
    except Exception as exc:
        with _scans_lock:
            _scans[scan_id]["status"] = "error"
            _scans[scan_id]["result"] = str(exc)
        log(f"Error: {exc}")


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    counts = _severity_counts()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "counts": counts,
        "close_rate": _close_rate(),
        "severity_colors": SEVERITY_COLORS,
        "severity_order": SEVERITY_ORDER,
    })


@app.get("/findings", response_class=HTMLResponse)
async def findings_page(
    request: Request,
    severity: str = "",
    owasp: str = "",
    status: str = "",
):
    findings = _get_findings(
        severity=severity or None,
        owasp=owasp or None,
        status=status or None,
    )
    owasp_options = [r["owasp"] for r in _owasp_counts()]
    return templates.TemplateResponse("findings.html", {
        "request": request,
        "findings": findings,
        "severity_order": SEVERITY_ORDER,
        "severity_colors": SEVERITY_COLORS,
        "owasp_options": owasp_options,
        "filter_severity": severity,
        "filter_owasp": owasp,
        "filter_status": status,
    })


@app.get("/findings/{finding_id}", response_class=HTMLResponse)
async def finding_detail(request: Request, finding_id: int):
    finding = _get_finding(finding_id)
    if not finding:
        return HTMLResponse("<p>Finding not found.</p>", status_code=404)
    return templates.TemplateResponse("finding.html", {
        "request": request,
        "finding": finding,
        "severity_colors": SEVERITY_COLORS,
    })


@app.get("/scan", response_class=HTMLResponse)
async def scan_page(request: Request):
    return templates.TemplateResponse("scan.html", {"request": request})


@app.post("/scan")
async def start_scan(
    repo_path: str = Form(...),
    output_dir: str = Form(OUTPUT_DIR),
    prompt: str = Form(""),
    remediate: bool = Form(False),
):
    scan_id = str(uuid.uuid4())
    with _scans_lock:
        _scans[scan_id] = {"status": "running", "messages": [], "result": None}
    threading.Thread(
        target=_scan_thread,
        args=(scan_id, repo_path, output_dir, prompt or None, remediate),
        daemon=True,
    ).start()
    return JSONResponse({"scan_id": scan_id})


@app.get("/scan/events/{scan_id}")
async def scan_events(scan_id: str):
    """Server-Sent Events stream for live scan progress."""
    async def generate():
        sent = 0
        while True:
            with _scans_lock:
                state = _scans.get(scan_id, {})
                messages = state.get("messages", [])
                status = state.get("status", "unknown")

            # Stream any new messages
            while sent < len(messages):
                msg = messages[sent].replace("\n", " ")
                yield f"data: {msg}\n\n"
                sent += 1

            if status in ("done", "error"):
                result = state.get("result", "")
                yield f"event: complete\ndata: {json.dumps({'status': status, 'result': result[:500]})}\n\n"
                break

            await asyncio.sleep(1)

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── Chart data API ─────────────────────────────────────────────────────────────

@app.get("/api/severity")
async def api_severity():
    counts = _severity_counts()
    ordered = [{"label": s, "value": counts.get(s, 0), "color": SEVERITY_COLORS[s]}
               for s in SEVERITY_ORDER]
    return JSONResponse(ordered)


@app.get("/api/trend")
async def api_trend(days: int = 30):
    return JSONResponse(_trend_data(days))


@app.get("/api/owasp")
async def api_owasp():
    return JSONResponse(_owasp_counts())


@app.get("/api/closerate")
async def api_closerate():
    return JSONResponse({"close_rate": _close_rate()})
