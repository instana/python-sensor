# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy the entire project to get access to src/instana
COPY . /app

# Set working directory to sandbox
WORKDIR /app/sandbox

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 5000
EXPOSE 5000

# Set environment variables
ENV PORT=5000
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV INSTANA_DEBUG=True

# Run the application with gunicorn
CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:app"]