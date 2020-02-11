import os

testenv = {}

"""
Cassandra Environment
"""
testenv['cassandra_host'] = os.environ.get('CASSANDRA_HOST', '127.0.0.1')
testenv['cassandra_username'] = os.environ.get('CASSANDRA_USERNAME', 'Administrator')
testenv['cassandra_password'] = os.environ.get('CASSANDRA_PASSWORD', 'password')

"""
CouchDB Environment
"""
testenv['couchdb_host'] = os.environ.get('COUCHDB_HOST', '127.0.0.1')
testenv['couchdb_username'] = os.environ.get('COUCHDB_USERNAME', 'Administrator')
testenv['couchdb_password'] = os.environ.get('COUCHDB_PASSWORD', 'password')

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
testenv['postgresql_host'] = os.environ.get('POSTGRES_HOST', '127.0.0.1')
testenv['postgresql_port'] = int(os.environ.get('POSTGRES_PORT', '5432'))
testenv['postgresql_db']   = os.environ.get('POSTGRES_DB', 'circle_test')
testenv['postgresql_user'] = os.environ.get('POSTGRES_USER', 'root')
testenv['postgresql_pw'] = os.environ.get('POSTGRES_PW', '')


"""
Redis Environment
"""
testenv['redis_host'] = os.environ.get('REDIS_HOST', '127.0.0.1')


"""
MongoDB Environment
"""
testenv['mongodb_host'] = os.environ.get('MONGO_HOST', '127.0.0.1')
testenv['mongodb_port'] = os.environ.get('MONGO_PORT', '27017')
testenv['mongodb_user'] = os.environ.get('MONGO_USER', None)
testenv['mongodb_pw'] = os.environ.get('MONGO_PW', None)

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
