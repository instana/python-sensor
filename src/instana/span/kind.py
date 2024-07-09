# (c) Copyright IBM Corp. 2024

ENTRY_KIND = ("entry", "server", "consumer")

EXIT_KIND = ("exit", "client", "producer")

LOCAL_SPANS = ("render",)

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
