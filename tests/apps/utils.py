import threading


def launch_background_thread(app, name):
    app_thread = threading.Thread(target=app)
    app_thread.daemon = True
    app_thread.name = "Background %s app" % name
    print("Starting background %s app..." % name)
    app_thread.start()
    return app_thread
