FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (layer cache optimization)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/ ./src/
COPY pyproject.toml . 2>/dev/null || true

# Named volume mount target
VOLUME /data

ENV PYTHONPATH=/app
ENV DATA_PATH=/data
ENV STORAGE_MODE=local

EXPOSE 8000

# Run via uvicorn directly — no PID 1 init system needed for thin server
CMD ["uvicorn", "dnd_play.main:app", "--host", "0.0.0.0", "--port", "8000"]