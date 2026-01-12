FROM python:3.11-slim

# Nastavení pracovního adresáře
WORKDIR /app

# Instalace systémových závislostí
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Kopírování requirements.txt a instalace Python závislostí
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopírování aplikace
COPY . .

# Exponování portu
EXPOSE 8000

# Spuštění aplikace
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
