FROM python:3.9-slim

WORKDIR /app
COPY . /app
RUN pip install flask
EXPOSE 3000
ENV INSTANA_DEBUG True

CMD ["python", "app.py"]