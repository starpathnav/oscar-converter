FROM python:3.11-slim

# Install system dependencies including eccodes
RUN apt-get update && apt-get install -y \
    libeccodes-dev \
    libeccodes0 \
    libeccodes-tools \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Set library path so Python can find eccodes
ENV LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH
ENV ECCODES_DIR=/usr

# Set working directory
WORKDIR /app

# Copy requirements and install Python packages
COPY requirements_deploy.txt .
RUN pip install --no-cache-dir -r requirements_deploy.txt

# Copy application code
COPY oscar_web_simple.py .

# Expose port
EXPOSE 10000

# Run the application
CMD ["sh", "-c", "gunicorn -w 2 -b 0.0.0.0:$PORT oscar_web_simple:app"]
