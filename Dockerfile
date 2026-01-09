FROM python:3.11-slim

# Install system dependencies for eccodes
RUN apt-get update && apt-get install -y \
    libeccodes-dev \
    libeccodes0 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python packages
COPY requirements_deploy.txt .
RUN pip install --no-cache-dir -r requirements_deploy.txt

# Copy application code
COPY oscar_web_production.py .

# Expose port (Render sets PORT env variable)
EXPOSE 10000

# Run the application - Render provides $PORT
CMD ["sh", "-c", "gunicorn -w 2 -b 0.0.0.0:$PORT oscar_web_production:app"]
