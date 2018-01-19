# encoding=utf-8
import opentracing
import instana
import time

# Loop continuously with a 2 second sleep to generate traces
while True:
    entry_span = opentracing.tracer.start_span('universe')

    entry_span.set_tag('http.method', 'GET')
    entry_span.set_tag('http.url', '/users')
    entry_span.set_tag('span.kind', 'entry')

    intermediate_span = opentracing.tracer.start_span('nebula', child_of=entry_span)
    intermediate_span.finish()

    db_span = opentracing.tracer.start_span('black-hole', child_of=entry_span)
    db_span.set_tag('db.instance', 'users')
    db_span.set_tag('db.statement', 'SELECT * FROM user_table')
    db_span.set_tag('db.type', 'mysql')
    db_span.set_tag('db.user', 'mysql_login')
    db_span.set_tag('span.kind', 'exit')
    db_span.finish()

    intermediate_span = opentracing.tracer.start_span('space-dust', child_of=entry_span)
    intermediate_span.log_kv({'message': 'All seems ok'})
    intermediate_span.finish()

    entry_span.set_tag('http.status_code', 200)
    entry_span.finish()
    time.sleep(2)
