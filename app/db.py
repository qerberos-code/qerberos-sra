import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str = "security-review/db.sqlite") -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS scans (
                id              INTEGER PRIMARY KEY,
                repo_path       TEXT NOT NULL,
                timestamp       TEXT NOT NULL,
                model           TEXT,
                scanner_status  TEXT
            );

            CREATE TABLE IF NOT EXISTS findings (
                id          INTEGER PRIMARY KEY,
                scan_id     INTEGER REFERENCES scans(id),
                tool        TEXT,
                title       TEXT,
                severity    TEXT,
                file        TEXT,
                line        INTEGER,
                owasp       TEXT,
                description TEXT,
                evidence    TEXT,
                patch_hint  TEXT,
                status      TEXT DEFAULT 'open'
            );

            CREATE TABLE IF NOT EXISTS remediations (
                id          INTEGER PRIMARY KEY,
                finding_id  INTEGER REFERENCES findings(id),
                branch      TEXT,
                commit_sha  TEXT,
                pr_url      TEXT,
                merged_at   TEXT
            );

            CREATE TABLE IF NOT EXISTS aivbm_assessments (
                id              INTEGER PRIMARY KEY,
                scan_id         INTEGER REFERENCES scans(id),
                tier            TEXT,
                architecture    TEXT,
                ivp_rb          REAL, ivp_fr REAL, ivp_tr REAL,
                ivp_pv          REAL, ivp_cn REAL,
                orp_aa          REAL, orp_as REAL, orp_cp REAL, orp_rf REAL,
                crm             REAL,
                aci_pc          REAL, aci_ec REAL, aci_tf REAL,
                aci_composite   REAL,
                ers             REAL,
                mvt_result      TEXT,
                timestamp       TEXT
            );

            CREATE TABLE IF NOT EXISTS bbd_readings (
                id              INTEGER PRIMARY KEY,
                assessment_id   INTEGER REFERENCES aivbm_assessments(id),
                timestamp       TEXT,
                bbd_score       REAL,
                classification  TEXT
            );
        """)


def insert_scan(
    repo_path: str,
    model: str,
    scanner_status: dict,
    db_path: str = "security-review/db.sqlite",
) -> int:
    ts = datetime.now(timezone.utc).isoformat()
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO scans (repo_path, timestamp, model, scanner_status) VALUES (?,?,?,?)",
            (repo_path, ts, model, json.dumps(scanner_status)),
        )
        return cur.lastrowid


def insert_findings(scan_id: int, findings: list[dict], db_path: str = "security-review/db.sqlite") -> None:
    rows = [
        (
            scan_id,
            f.get("tool"), f.get("title"), f.get("severity"),
            f.get("file"), f.get("line"), f.get("owasp"),
            f.get("description"), f.get("evidence"), f.get("patch_hint"),
            f.get("status", "open"),
        )
        for f in findings
    ]
    with _connect(db_path) as conn:
        conn.executemany(
            """INSERT INTO findings
               (scan_id, tool, title, severity, file, line, owasp,
                description, evidence, patch_hint, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            rows,
        )


def insert_remediation(finding_id: int, branch: str, db_path: str = "security-review/db.sqlite") -> int:
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO remediations (finding_id, branch) VALUES (?,?)",
            (finding_id, branch),
        )
        return cur.lastrowid


def update_remediation_pr(remediation_id: int, commit_sha: str, pr_url: str, db_path: str = "security-review/db.sqlite") -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE remediations SET commit_sha=?, pr_url=? WHERE id=?",
            (commit_sha, pr_url, remediation_id),
        )
