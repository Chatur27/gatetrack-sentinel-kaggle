FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GTS_API_HOST=0.0.0.0 \
    GTS_API_PORT=8080 \
    GTS_DB_PATH=/app/runtime/gatetrack_sentinel.db \
    GTS_MODEL_MODE=adk

WORKDIR /app
COPY requirements.txt requirements-adk.txt ./
RUN pip install --no-cache-dir -r requirements-adk.txt
COPY backend ./backend
COPY data ./data
COPY mcp_server ./mcp_server
COPY adk_agents ./adk_agents
RUN mkdir -p /app/runtime

EXPOSE 8080
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
