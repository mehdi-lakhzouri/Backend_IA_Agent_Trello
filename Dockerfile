FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FLASK_APP=run.py \
    PORT=5000

WORKDIR /app

# System deps (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy project
COPY . .

# Create runtime dirs (persisted via volumes when using compose)
RUN mkdir -p instance/chromadb logs

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost:${PORT}/api/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
