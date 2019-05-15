FROM python:3

WORKDIR /usr/src/app

COPY . ./
RUN pip install --no-cache-dir -r requirements.txt
ENV PYTHONPATH /usr/src/app
ENV INSTANA_DEBUG true

CMD [ "python", "./example/simple.py" ]
