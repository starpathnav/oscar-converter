FROM condaforge/mambaforge:latest

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements_deploy.txt .

# Install packages using conda (handles eccodes properly)
RUN mamba install -y -c conda-forge \
    python=3.11 \
    flask=3.0.0 \
    gunicorn=21.2.0 \
    xarray=2024.1.0 \
    netcdf4=1.6.5 \
    eccodes \
    cfgrib=0.9.12.0 \
    numpy=1.26.3 \
    && mamba clean -afy

# Copy application
COPY oscar_web_simple.py .

# Expose port
EXPOSE 10000

# Run application
CMD ["sh", "-c", "gunicorn -w 2 --timeout 120 -b 0.0.0.0:$PORT oscar_web_simple:app"]
