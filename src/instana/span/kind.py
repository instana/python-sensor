# (c) Copyright IBM Corp. 2024

from opentelemetry.trace import SpanKind

ENTRY_KIND = ("entry", "server", "consumer", SpanKind.SERVER, SpanKind.CONSUMER)

EXIT_KIND = ("exit", "client", "producer", SpanKind.CLIENT, SpanKind.PRODUCER)

LOCAL_SPANS = ("asyncio", "render", SpanKind.INTERNAL)

HTTP_SPANS = (
    "aiohttp-client",
    "aiohttp-server",
    "django",
    "http",
    "tornado-client",
    "tornado-server",
    "urllib3",
    "wsgi",
    "asgi",
)

ENTRY_SPANS = (
    "aiohttp-server",
    "aws.lambda.entry",
    "celery-worker",
    "django",
    "wsgi",
    "rabbitmq",
    "rpc-server",
    "tornado-server",
    "gcps-consumer",
    "asgi",
)

EXIT_SPANS = (
    "aiohttp-client",
    "boto3",
    "cassandra",
    "celery-client",
    "couchbase",
    "log",
    "memcache",
    "mongo",
    "mysql",
    "postgres",
    "rabbitmq",
    "redis",
    "rpc-client",
    "sqlalchemy",
    "tornado-client",
    "urllib3",
    "pymongo",
    "gcs",
    "gcps-producer",
)

REGISTERED_SPANS = LOCAL_SPANS + ENTRY_SPANS + EXIT_SPANS
