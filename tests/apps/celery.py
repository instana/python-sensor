import atexit
import subprocess

process = None


def start():
    # Background Celery application
    # celery -A tests.data.celery.tasks worker --loglevel=info
    global process

    print("Starting background celery workers...")
    process = subprocess.Popen(["celery", "-A", "tests.data.celery.tasks", "worker", "--loglevel=info"],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    atexit.register(stop)


def stop():
    global process
    if process is not None:
        process.terminate()
