# Production Dockerfile for Vamsi Vegi Market
FROM python:3.13-slim

WORKDIR /app

# Prevent Python from writing .pyc and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=5000

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Expose standard port
EXPOSE 5000

# Run with Gunicorn WSGI production server
CMD ["gunicorn", "wsgi:app", "--workers", "3", "--timeout", "120", "--bind", "0.0.0.0:5000"]
