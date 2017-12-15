call PyGILState_Ensure()
call PyRun_SimpleString("import sys; sys.path.insert(0, '/tmp/instana/python');")
call PyRun_SimpleString("exec(open(\"/tmp/instana/python/python-sensor/instana/probe.py\").read())")
call PyGILState_Release($1)
