# (c) Copyright IBM Corp. 2024

import time


def timing_tween_factory(handler, registry):
    def timing_tween(request):
        start = time.time()
        try:
            response = handler(request)
        finally:
            end = time.time()
            print(f"The request took {end - start} seconds")
        return response

    return timing_tween
