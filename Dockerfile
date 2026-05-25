# AutoApply AI — Production Docker image
# Python 3.11 slim for small image size
FROM python:3.11-slim

WORKDIR /app

# System dependencies for Playwright + ChromaDB
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (optional — comment out to reduce image size)
RUN playwright install --with-deps chromium || echo "Playwright skipped"

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p data/cvs chroma_db

# Streamlit configuration
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Hugging Face Spaces requires port 7860
ENV PORT=7860
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:7860/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0"]