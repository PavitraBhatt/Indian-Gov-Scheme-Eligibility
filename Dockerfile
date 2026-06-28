FROM python:3.12-slim

# Don't write .pyc files; flush logs straight to the console.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app and install the package.
COPY . .
RUN pip install --no-cache-dir -e .

# Pre-build the SQLite store from the JSON source so the first request is fast.
RUN python -c "from scheme_checker.db import build_db; build_db(force=True)"

EXPOSE 8000

# Platforms (Render/Railway/Fly) inject $PORT; default to 8000 locally.
CMD ["sh", "-c", "uvicorn scheme_checker.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
