FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip && pip install --no-cache-dir .

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/reports \
    && chown -R appuser:appuser /app
USER appuser

# config.yaml is intentionally NOT baked into the image — mount it at runtime:
#   docker run -v "$PWD/config.yaml:/app/config.yaml" -v "$PWD/.env:/app/.env" researchhq
CMD ["researchhq", "status"]
