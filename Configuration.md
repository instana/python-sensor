# Configuration

## Agent Communication

The sensor tries to communicate with the Instana agent via IP 127.0.0.1 and as a fallback via the host's default gateway for containerized environments. Should the agent not be available under either of these IPs, e.g. due to iptables or other networking tricks, you can use environment variables to configure where the Instana host agent lives.

To use these, these environment variables should be set in the environment of the running Python process.

```shell
export INSTANA_AGENT_HOST = '127.0.0.1'
export INSTANA_AGENT_PORT = '42699'
```

## Setting the Service Name

If you'd like to assign a single service name for the entire application you can do so by setting an environment variable or via code:

```
export INSTANA_SERVICE_NAME=myservice
```

or

```Python
instana.service_name = "myservice"
```

## Package Configuration

The Instana package includes a runtime configuration module that manages the configuration of various components.

_Note: as the package evolves, more options will be added here_

```python
from instana.configurator import config

# To enable tracing context propagation across Asyncio ensure_future and create_task calls
# Default is false
config['asyncio_task_context_propagation']['enabled'] = True

```


## Debugging & More Verbosity

Setting `INSTANA_DEV` to a non nil value will enable extra logging output generally useful
for development.

```Python
export INSTANA_DEV="true"
```

## Disabling Automatic instrumentation

You can disable automatic instrumentation (tracing) by setting the environment variable `INSTANA_DISABLE_AUTO_INSTR`.  This will suppress the loading of instrumentation built-into the sensor.

## OpenShift

In certain scenarios, the Python sensor can't automatically locate the Instana host agent.  To resolve this, add the following to your Python app deployment descriptor:

```
- name: INSTANA_AGENT_HOST
valueFrom:
  fieldRef:
    fieldPath: status.hostIP
```

This will set the environment variable INSTANA_AGENT_HOST with the IP of the host so the Python sensor can properly locate the Host agent.

