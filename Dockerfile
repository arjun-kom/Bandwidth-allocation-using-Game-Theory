# --- stage 1: build the React dashboard ---------------------------------
FROM node:22-alpine AS web
WORKDIR /web
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY dashboard/ ./
RUN npm run build

# --- stage 2: Python API + simulator, serving the built dashboard --------
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg \
    BWA_DB=/app/data/runs.db
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY core ./core
COPY sim ./sim
COPY experiments ./experiments
COPY api ./api
COPY tests ./tests
COPY pytest.ini ./
# Run the tests and pre-compute the experiment results so the Experiments tab is ready at once.
RUN python -m pytest -q && python -m experiments.run_all --out results
COPY --from=web /web/dist ./dashboard/dist
RUN mkdir -p /app/data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
