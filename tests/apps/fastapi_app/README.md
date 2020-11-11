To launch manually from an iPython console:

```python
from tests.apps.fastapi_app import launch_fastapi
launch_fastapi()
```

or

```
ipython -c 'from tests.apps.fastapi_app import launch_fastapi; launch_fastapi()'
```

Then you can launch requests:

```bash
curl -i localhost:10816/
```
