FROM python:3.13-slim

WORKDIR /app

# System deps for psycopg2 wheels + healthcheck curl
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=5011
ENV RELOAD=false
ENV LOG_LEVEL=INFO

EXPOSE 5011

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:5011/health || exit 1

CMD ["python", "web_app.py"]
