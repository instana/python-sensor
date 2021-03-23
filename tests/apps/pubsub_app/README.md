## PubSub Local Testing

For Authentication to work properly, add the environment variable on your system: `GOOGLE_APPLICATION_CREDENTIALS`

Read: https://cloud.google.com/docs/authentication/getting-started#setting_the_environment_variable

```
export GOOGLE_APPLICATION_CREDENTIALS="/home/user/Downloads/my-key.json"
```

### Run the app locally

There are 2 ways to run the app

1. Using [Pub/Sub on Google Cloud Platform](https://console.cloud.google.com/cloudpubsub) - use the [credentials for your service account key](http://console.cloud.google.com/apis/credentials) from the console.
2. Using the [local emulator](https://cloud.google.com/pubsub/docs/emulator):
    * Make sure docker-compose is running locally
        * `docker-compose down -v && docker-compose up -d`
    * `export ["PUBSUB_EMULATOR_HOST"]="localhost:8432"` or uncomment the appropriate line in the file `pubsub.py`

#### Start the flask app
> python pubsub.py

Open two tabs on browser: one for publish and one for consume
```
1. localhost:10811/publish?message=test-message
2. localhost:10811/consume
```

As the consumer listens for the messages, you'll see the logs on the terminal.