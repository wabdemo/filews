FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y nginx && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create uploads directory
RUN mkdir -p /app/uploads

# Copy all project files
COPY . .

EXPOSE 8080
EXPOSE 4873
EXPOSE 80 443

# Install Nginx

# Copy Nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Expose HTTP and HTTPS ports

# Start Nginx and your application
CMD service nginx start && python server.py
