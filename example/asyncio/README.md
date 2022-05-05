# Asyncio Examples

This directory includes an example asyncio application and client with aiohttp and aio-pika used for testing.

# Requirements

* Python 3.7 or greater
* instana, aiohttp and aio-pika Python packages installed
* A RabbitMQ server with it's location specified in the `RABBITMQ_HOST` environment variable


# Run

* Make sure the Instana Python package is installed or you have this git repository checked out.

* Set the environment variable `AUTOWRAPT_BOOTSTRAP=instana` for immediate instrumentation.

* Boot the aiohttpserver.py file as follows.  It will launch an aiohttp server that listens on port localhost:5102.  See the source code for published endpoints.

```bash
python aiohttpserver.py
```

* Boot the `aiohttpclient.py` file to generate a request (every 1 second) to the aiohttp server.

```bash
python aiohttpclient.py
```

From here, you can modify the `aiohttpclient.py` file as needed to change requested paths and so on.

# Results

Some example traces from local tests.

aiohttp client calling aiohttp server:
![screen shot 2019-02-25 at 19 12 28](https://user-images.githubusercontent.com/395132/53401921-0f49cc00-39b1-11e9-8606-24844925a478.png)

aiohttp server making multiple aio-pika calls (publish & consume)
<!--
#TODO: Add new screenshot once we actually have the aio-pika support
-->
![screen shot 2019-02-26 at 10 21 50](https://user-images.githubusercontent.com/395132/53401997-2e485e00-39b1-11e9-97fd-460b136cf92a.png)
