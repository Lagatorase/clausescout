# ClauseScout app image: the API plus the built frontend, on CPU.
# The default method is the keyword baseline, so the image runs without model weights.

# Stage 1: build the React frontend.
FROM node:20.18-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# Stage 2: the Python API, serving the built frontend from web/dist.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements-app.txt ./
RUN pip install --no-cache-dir -r requirements-app.txt
COPY pyproject.toml ./
COPY clausescout/ clausescout/
COPY api/ api/
COPY config/ config/
COPY --from=web /web/dist web/dist
# I run as a normal user, not root.
RUN useradd --create-home app && mkdir -p runs && chown app runs
USER app
EXPOSE 8000
# Inside the container the server must listen on all interfaces; docker-compose only publishes
# it on the host's 127.0.0.1, so it stays local to this machine.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
