FROM python:3.12-slim

# System deps + security scanner binaries
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl git ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# gitleaks (pinned — avoids GitHub API rate-limit in CI)
ARG GITLEAKS_VERSION=8.21.2
RUN curl -sSfL \
      "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz" \
      | tar -xz -C /usr/local/bin gitleaks

# trivy
RUN curl -sSfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh \
        | sh -s -- -b /usr/local/bin

# semgrep (Python package — installed via pip before uv takes over)
RUN pip install --no-cache-dir semgrep

# uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml ./
# Install deps without the project itself first (better layer caching)
RUN uv sync --no-install-project

COPY . .
RUN uv sync

# Persist DB and reports on a volume
VOLUME ["/app/security-review"]

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000"]
