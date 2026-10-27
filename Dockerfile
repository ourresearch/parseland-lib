FROM --platform=linux/amd64 python:3.12-slim

RUN apt-get update && apt-get install -y \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# --timeout 25: just under the 30 s its callers wait (walden scraping/parseland.ipynb). At 10 s, 2-7 MB open-access
# ScienceDirect pages never finished (oxjob #1794: ~70% of 47K Elsevier DOIs whose every parse errored).
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "8", "--timeout", "25", "app:app"]