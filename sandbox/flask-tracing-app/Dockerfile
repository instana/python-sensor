# (c) Copyright IBM Corp. 2025
# Multi-stage build to keep the final image lean.
#
# Stage 1: install Python dependencies
FROM public.ecr.aws/docker/library/python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: runtime image
FROM public.ecr.aws/docker/library/python:3.11-slim
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY app.py .

# Non-root user for OpenShift / Kubernetes hardened namespaces
RUN addgroup --gid 1001 appgroup && \
    adduser  --uid 1001 --gid 1001 --no-create-home --disabled-password appuser
USER 1001

EXPOSE 5000

# AUTOWRAPT_BOOTSTRAP activates the instana package at Python startup
# without any explicit "import instana" in application code.
# Override in Deployment env vars — this is just the image default.
ENV AUTOWRAPT_BOOTSTRAP=instana \
    APP_HOST=0.0.0.0 \
    APP_PORT=5000

CMD ["python", "app.py"]
