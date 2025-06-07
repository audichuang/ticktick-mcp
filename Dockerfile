# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY ticktick_mcp/ ./ticktick_mcp/
COPY setup.py .

# Install the package
RUN pip install -e .

# Expose the port
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Set working directory for runtime
WORKDIR /app

# Direct Python execution without shell script
CMD ["python", "-m", "ticktick_mcp.src.remote_server"]