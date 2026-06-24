# Document Intelligence API
# Build context is the repo root so we can also copy the shared core:
#   docker build -f projects/01-document-intelligence/api/Dockerfile -t doc-intel .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install the shared core, then the API deps.
COPY shared /app/shared
RUN pip install -e /app/shared

COPY projects/01-document-intelligence/api/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY projects/01-document-intelligence/api/app /app/app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
