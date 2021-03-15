# encoding=utf-8

# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2018

import time

import opentracing

# Loop continuously with a 2 second sleep to generate traces
while True:
    with opentracing.tracer.start_active_span('universe') as escope:
        escope.span.set_tag('http.method', 'GET')
        escope.span.set_tag('http.url', '/users')
        escope.span.set_tag('span.kind', 'entry')

        with opentracing.tracer.start_active_span('black-hole', child_of=escope.span) as dbscope:
            dbscope.span.set_tag('db.instance', 'users')
            dbscope.span.set_tag('db.statement', 'SELECT * FROM user_table')
            time.sleep(.1)
            dbscope.span.set_tag('db.type', 'mysql')
            dbscope.span.set_tag('db.user', 'mysql_login')
            dbscope.span.set_tag('span.kind', 'exit')

        with opentracing.tracer.start_active_span('space-dust', child_of=escope.span) as iscope:
            iscope.span.log_kv({'message': 'All seems ok'})

        escope.span.set_tag('http.status_code', 200)
        time.sleep(.2)
