FROM public.ecr.aws/docker/library/python:3.11-trixie

WORKDIR /app
COPY . /app

# Install dependencies (Flask + Gunicorn + Requests)
RUN pip install --no-cache-dir flask gunicorn requests

EXPOSE 3000
ENV INSTANA_DEBUG=True

CMD ["gunicorn", "--workers", "12", "--bind", "0.0.0.0:3000", "--preload", "app:app"]
