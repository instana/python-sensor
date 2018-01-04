# Configuration

## Agent Communication

The sensor tries to communicate with the Instana agent via IP 127.0.0.1 and as a fallback via the host's default gateway for containerized environments. Should the agent not be available under either of these IPs, e.g. due to iptables or other networking tricks, you can use environment variables to configure where the Instana host agent lives.

To use these, these environment variables should be set in the environment of the running Python process.

```shell
export INSTANA_AGENT_IP = '127.0.0.1'
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

## Debugging & More Verbosity

Setting `INSTANA_DEV` to a non nil value will enable extra logging output generally useful
for development.

```Python
export INSTANA_DEV="true"
```

## Disabling Automatic instrumentation

You can disable automatic instrumentation (tracing) by setting the environment variable `INSTANA_DISABLE_AUTO_INSTR`.  This will suppress the loading of instrumentation built-into the sensor.
