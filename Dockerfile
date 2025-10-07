# Development Container
FROM public.ecr.aws/docker/library/python:3.14-slim

RUN apt-get -y -qq update && \
    apt-get -y -qq upgrade && \
    apt-get -y -qq install --no-install-recommends git && \
    apt-get -y -qq clean

WORKDIR /python-tracer
COPY . ./

RUN pip install --upgrade pip && \
    pip install -e .

ENV INSTANA_DEBUG=true
ENV PYTHONPATH=/python-tracer
ENV AUTOWRAPT_BOOTSTRAP=instana
