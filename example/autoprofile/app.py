import time
import threading
import random
import traceback
import sys
import os

sys.path.append('../..')
os.environ['INSTANA_DEBUG'] = 'yes'
os.environ['INSTANA_AUTOPROFILE'] = 'yes'
import instana

try:
    # python 2
    from urllib2 import urlopen
except ImportError:
    # python 3
    from urllib.request import urlopen


# Simulate CPU intensive work
def simulate_cpu():
    for i in range(5000000):
        text = "text1" + str(i)
        text = text + "text2"


# Simulate memory leak
def simulate_mem_leak():
    while True:
        mem1 = []

        for j in range(0, 1800):
            mem2 = []
            for i in range(0, 1000):
                obj1 = {'v': random.randint(0, 1000000)}
                mem1.append(obj1)

                obj2 = {'v': random.randint(0, 1000000)}
                mem2.append(obj2)

            time.sleep(1)

threading.Thread(target=simulate_mem_leak).start()


# Simulate lock
def simulate_lock():
    lock = threading.Lock()

    def lock_wait():
        lock.acquire()
        lock.release()

    while True:
        lock.acquire()
    
        threading.Thread(target=lock_wait).start()

        time.sleep(1)
        lock.release()
        time.sleep(1)

threading.Thread(target=simulate_lock).start()


while True:
    simulate_cpu()
    time.sleep(1)
