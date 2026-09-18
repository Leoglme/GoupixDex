FROM python:3.12-slim-bookworm

# Chromium + Xvfb : publication Vinted (nodriver) sans configuration manuelle dans le conteneur.
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    xvfb \
    xauth \
    fonts-liberation \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

ENV VINTED_CHROME_EXECUTABLE=/usr/bin/chromium

# Build context = repo root (see docker-compose.yml): the sibling cardmarket-api
# package must land next to /app so `-e ../cardmarket-api` in requirements resolves.
WORKDIR /app

COPY cardmarket-api /cardmarket-api
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -c "from supabase import create_client"

COPY api/ .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
