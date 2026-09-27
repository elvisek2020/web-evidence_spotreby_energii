FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Prague

# Non-root uživatel (UID 1000); curl potřebuje healthcheck
RUN useradd -u 1000 -ms /bin/bash appuser && \
    apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        && rm -rf /var/lib/apt/lists/*

# Nastavení pracovního adresáře
WORKDIR /app

# Instalace Python závislostí
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopírování aplikace; --chown kvůli lokálním souborům s právy jen pro vlastníka (600)
COPY --chown=appuser:appuser app ./app

USER appuser

# Exponování portu
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Spuštění aplikace; za reverse proxy přebírá hlavičky X-Forwarded-*
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
