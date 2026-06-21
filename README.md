# qerberos-sra

**Multi-agent AI Security Review System** — powered by Claude, aligned to the AIVBM framework.

Runs 7 specialist AI agents in parallel against any code repository, consolidates findings, generates executive and technical reports, auto-remediates CRITICAL/HIGH vulnerabilities via pull requests, and surfaces everything in a mobile-friendly web dashboard.

---

## Architecture

```
review_repo()
      │
      ▼
ReviewManager
      │
      ├── SecretsAgent      (gitleaks)
      ├── DependencyAgent   (trivy · snyk · pip-audit · npm audit)
      ├── SASTAgent         (semgrep)
      ├── IaCAgent          (trivy config · checkov · Dockerfiles · k8s · Terraform)
      ├── AICodeAgent       (AI-generated code patterns · prompt injection)
      ├── ComplianceAgent   (OWASP Top 10 · PCI-DSS · SOC 2)
      └── AIVBMAgent        (AIVBM IVP · ORP · ACI · ERS scoring)
               │
        JSON findings
               │
        ReviewManager
     (deduplicate · prioritize)
               │
      ┌────────┼────────┐
      ▼        ▼        ▼
  executive findings remediation
  -summary   .md       .md
     .md
```

---

## Features

| Phase | What it does |
|-------|-------------|
| **Scan** | 7 agents run in parallel; each returns structured JSON findings |
| **Prioritize** | Manager deduplicates across agents, maps to OWASP Top 10, ranks by exploitability |
| **Report** | 3 Markdown reports: executive summary, technical findings, remediation guide |
| **Remediate** | Auto-applies CRITICAL/HIGH fixes, creates git branches, opens PRs via GitHub MCP |
| **Dashboard** | Mobile-first FastAPI + HTMX + Tailwind + Chart.js web UI; SQLite findings DB |
| **AIVBM** | Full IVP/ORP/ACI/ERS scoring per the AI Vulnerability Benchmarking & Maturity Framework |

---

## Quick start

### Docker (recommended)

```bash
cp .env.example .env          # add ANTHROPIC_API_KEY
docker compose up
```

Open `http://localhost:8000` — works on iPhone if on the same network.

### Local (uv)

```bash
cp .env.example .env
uv sync
uv run uvicorn app.server:app --reload --port 8000
```

### CLI scan

```bash
uv run python -m app.main /path/to/repo
uv run python -m app.main /path/to/repo --remediate    # auto-open PRs
uv run python -m app.main . -o reports -p "Focus on auth"
```

---

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | ✓ | — | Claude API key |
| `MODEL` | | `claude-opus-4-8` | Override Claude model |
| `MANAGER_MODEL` | | `$MODEL` | Model for ReviewManager |
| `SUBAGENT_MODEL` | | `$MODEL` | Model for sub-agents |
| `SECUREREVIEW_DB` | | `security-review/db.sqlite` | SQLite database path |
| `SECUREREVIEW_OUTPUT` | | `security-review` | Report output directory |

---

## Scanners

Installed automatically in Docker. For local use, install on `PATH`:

- [`gitleaks`](https://github.com/gitleaks/gitleaks) — secret detection
- [`semgrep`](https://semgrep.dev/) — SAST
- [`trivy`](https://trivy.dev/) — dependencies + IaC
- [`snyk`](https://snyk.io/) — dependency vulnerabilities
- `pip-audit` / `npm audit` — language-specific advisories

Missing tools are noted in `scanner_status` and skipped — never fatal.

---

## AIVBM

Implements the [AI Vulnerability Benchmarking & Maturity Framework](https://owasp.org) by Henry Hu (OWASP Taiwan / Auriga Security). The `AIVBMAgent` scores the target AI system across 20 sub-metrics and produces:

- **IVP** vector: Robustness · Fairness · Transparency · Privacy · Containment
- **ORP** vector: Autonomy · Attack Surface · Cascade Potential · Remediation Feasibility
- **ACI** composite: Provenance · Evaluation Coverage · Temporal Freshness
- **ERS**: Effective Risk Score (0–10)
- **MVT** result: PASS / FAIL-Critical / FAIL-Major / FAIL-Minor

---

## Deployment

Push to `master` → GitHub Actions builds Docker image → pushes to `ghcr.io` → Railway/Render redeploys automatically.

Set `RAILWAY_WEBHOOK_URL` (or `RENDER_DEPLOY_HOOK_URL`) as a GitHub Actions secret to enable auto-deploy.
