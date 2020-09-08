# Development Container
FROM python:3.8.5

RUN apt update -q
RUN apt install -qy vim 

WORKDIR /python-sensor

ENV INSTANA_DEBUG=true
ENV PYTHONPATH=/python-sensor
ENV AUTOWRAPT_BOOTSTRAP=instana

COPY . ./

RUN pip install -e .
