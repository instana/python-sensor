import os

testenv = {}

"""
MySQL Environment
"""
if 'MYSQL_HOST' in os.environ:
    testenv['mysql_host']= os.environ['MYSQL_HOST']
elif 'TRAVIS_MYSQL_HOST' in os.environ:
    testenv['mysql_host'] = os.environ['TRAVIS_MYSQL_HOST']
else:
    testenv['mysql_host'] = '127.0.0.1'

testenv['mysql_port'] = int(os.environ.get('MYSQL_PORT', '3306'))
testenv['mysql_db']   = os.environ.get('MYSQL_DB', 'circle_test')
testenv['mysql_user'] = os.environ.get('MYSQL_USER', 'root')
testenv['mysql_pw'] = os.environ.get('MYSQL_PW', '')


"""
PostgreSQL Environment
"""
testenv['postgresql_host'] = os.environ.get('POSTGRESQL_HOST', '127.0.0.1')
testenv['postgresql_port'] = int(os.environ.get('POSTGRESQL_PORT', '5432'))
testenv['postgresql_db']   = os.environ.get('POSTGRESQL_DB', 'circle_test')
testenv['postgresql_user'] = os.environ.get('POSTGRESQL_USER', 'root')
testenv['postgresql_pw'] = os.environ.get('POSTGRESQL_PW', '')


"""
Redis Environment
"""
if 'REDIS' in os.environ:
    testenv['redis_url']= os.environ['REDIS']
else:
    testenv['redis_url'] = '127.0.0.1:6379'


def get_first_span_by_name(spans, name):
    for span in spans:
        if span.n == name:
            return span
    return None


def get_span_by_filter(spans, filter):
    for span in spans:
        if filter(span) is True:
            return span
    return None
