# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import threading


def launch_background_thread(app, app_name, fun_args=(), fun_kwargs={}):
    print("Starting background %s app..." % app_name)
    app_thread = threading.Thread(target=app,
                                  name=app_name,
                                  args=fun_args,
                                  kwargs=fun_kwargs)
    app_thread.daemon = True
    app_thread.start()
    return app_thread
