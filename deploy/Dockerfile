# Analizator CFD: praca ciagla w kontenerze. Budowanie z katalogu glownego repo:
#   docker compose -f deploy/docker-compose.yml up -d --build
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 TZ=UTC
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install .

# config/, data/, reports/ i .env sa montowane z hosta (patrz docker-compose.yml)
RUN useradd --create-home --uid 1000 cfd && mkdir -p /app/data /app/reports && chown -R cfd /app
USER cfd

HEALTHCHECK --interval=5m --timeout=20s --start-period=2m \
  CMD python -c "import os,sys,time; p='/app/reports/panel.html'; sys.exit(0 if os.path.exists(p) and time.time()-os.path.getmtime(p) < 1800 else 1)"

CMD ["cfd", "-v", "run"]
