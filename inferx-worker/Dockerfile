# Use a slim Python base image to minimize footprint
FROM python:3.10-slim

# Configure environment variables to prevent .pyc files and buffer issues
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Create a non-root user for security best practices
RUN useradd -m workeruser

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .

# Install dependencies efficiently without cache
RUN pip install --no-cache-dir -r requirements.txt

# Copy the worker source code
COPY main.py .

# Switch to the non-root user
USER workeruser

# Run the background daemon script
CMD ["python", "main.py"]
