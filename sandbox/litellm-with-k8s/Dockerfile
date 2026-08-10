FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Flask dev server — single process, import errors surface immediately.
# Instana autotrace webhook injects the sensor via PYTHONPATH — no manual import.
EXPOSE 8080
ENV FLASK_APP=app.py
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=8080"]
