# Tekton CI for Instana Python Tracer

## Basic Tekton setup

### Get a cluster

What you will need:
* Full administrator access
* Enough RAM and CPU on a cluster node to run all the pods of a single Pipelinerun on a single node.
  Multiple nodes increase the number of parallel `PipelineRun` instances.
  Currently one `PipelineRun` instance is capable of saturating a 8vCPU - 16GB RAM worker node.

### Setup Tekton on your cluster

1. Install latest stable Tekton Pipeline release
```bash
   kubectl apply --filename https://storage.googleapis.com/tekton-releases/pipeline/latest/release.yaml
```

2. Install Tekton Dashboard Full (the normal is read only, and doesn't allow for example to re-run).

````bash
   kubectl apply --filename https://storage.googleapis.com/tekton-releases/dashboard/latest/release-full.yaml
````

3. Access the dashboard

```bash
kubectl proxy
```

Once the proxy is active, navigate your browser to the [dashboard url](
http://localhost:8001/api/v1/namespaces/tekton-pipelines/services/tekton-dashboard:http/proxy/)

### Setup the python-tracer-ci-pipeline

````bash
   kubectl apply --filename task.yaml && kubectl apply --filename pipeline.yaml
````

### Run the pipeline manually

#### From the Dashboard
Navigate your browser to the [pipelineruns section of the dashboard](
http://localhost:8001/api/v1/namespaces/tekton-pipelines/services/tekton-dashboard:http/proxy/#/pipelineruns)

1. Click `Create`
2. Select the `Namespace` (where the `Pipeline` resource is created by default it is `default`)
3. Select the `Pipeline` created in the `pipeline.yaml` right now it is `python-tracer-ci-pipeline`
4. Fill in `Params`. The `revision` should be `main` for the `main` branch
4. Select the `ServiceAccount` set to `default`
5. Optionally, enter a `PipelineRun name` for example `my-main-test-pipeline`,
   but if you don't then the Dashboard will generate a unique one for you.
6. As long as [the known issue with Tekton Dashboard Workspace binding](
   https://github.com/tektoncd/dashboard/issues/1283), is not resolved.
   You have to go to `YAML Mode` and insert the workspace definition at the end of the file,
   with the exact same indentation:

````yaml
  workspaces:
  - name: python-tracer-ci-pipeline-pvc-$(params.revision)
    volumeClaimTemplate:
      spec:
        accessModes:
          - ReadWriteOnce
        resources:
          requests:
            storage: 100Mi

````
7. Click `Create` at the bottom of the page


#### From kubectl CLI
As an alternative to using the Dashboard, you can manually edit `pipelinerun.yaml` and create it with:
````bash
   kubectl apply --filename pipelinerun.yaml
````

### Clanup PipelineRun and associated PV resources

`PipelineRuns` and workspace `PersistentVolume` resources by default are kept indefinitely,
and repeated runs might exhaust the available resources, therefore they need to be cleaned up either
automatically or manually.

#### Manully from the Dashboard

Navigate to `PipelineRuns` and check the checkbox next to the pipelinerun
and then click `Delete` in the upper right corner.

#### Manually from the CLI

You can use either `kubectl`
````bash
kubectl get pipelinerun
kubectl delete pipelinerun <selected-pipelinerun-here>
````

or `tkn` cli
````bash
tkn pipelinerun list
tkn pipelinerun delete <selected-pipelinerun-here>
````

#### Automatic cleanup with a cronjob

Install and configure resources from https://github.com/3scale-ops/tekton-pipelinerun-cleaner

#### Preventing image pull failures with a prepuller

Maintain, and install the list of used images in the `python-tracer-prepuller.yaml`:
````bash
   kubectl apply --filename python-tracer-prepuller.yaml
````

## Integrate with GitHub

### GitHub PR Trigger & PR Check API integration

The GitHub integration requires further Tekton Triggers and Interceptors to be installed
````bash
kubectl apply --filename \
https://storage.googleapis.com/tekton-releases/triggers/latest/release.yaml
kubectl apply --filename \
https://storage.googleapis.com/tekton-releases/triggers/latest/interceptors.yaml
````
#### Create a ServiceAccount

Our future GitHub PR Event listener needs a service account,
`tekton-triggers-eventlistener-serviceaccount` which authorizes it to
perform operations specified in eventlistener `Role` and `ClusteRole`.
Create the service account with the needed role bindings:

````bash
   kubectl apply --filename tekton-triggers-eventlistener-serviceaccount.yaml
````

#### Create the Secret for the GitHub repository webhook

In order to authorize the incoming webhooks into our cluster, we need to share
a secret between our webhook listener, and the GitHub repo.
This resource can be shared across multiple tekton Tri
Generate a long, strong and random generated token, put it into `github-interceptor-secret.yaml`.
Create the secret resource:
````bash
   kubectl apply --filename github-interceptor-secret.yaml
````

#### Create the Task and token to report PR Check status to GitHub

The GitHub PR specific Tekton pipeline will want to send data to report the `PR Check Status`.
That [GitHub API](https://docs.github.com/en/rest/commits/statuses?apiVersion=2022-11-28#create-a-commit-status
) requires authentication, and therefore we need a token.
The user which generates the token has to have `Write` access in the target repo,
as part of the organisation. Check the repo access for this repo under
https://github.com/instana/python-sensor/settings/access.

With the proper user:
1. Navigate to https://github.com/settings/tokens
2. Click on `Generate new token` dropdown `Generate new token (classic)`.
3. Fill in `Note` with for example `Tekton commit status`,
4. Make sure if you set an expiration, than you remember to renew the token after expiry.
5. Under `Select scopes` find `repo` and below that only select the checkbox next to `repo:status` - `Access commit status`.
 click `Generate token`
6. Create the kubernetes secret with the token:

````bash
   kubectl create secret generic githubtoken --from-literal token="MY_TOKEN"
````

And we also make an HTTP POST with the status update data to GitHub.
This is done in a `Task` called `github-set-status`, create it as such:
````bash
   kubectl apply -f github-set-status-task.yaml
````

#### Create the GitHub PR pipeline

Create the new pipeline, which executes the previously created `python-tracer-ci-pipeline`,
wrapped around with GitHub Check status reporting tasks. As long as [Pipelines in Pipelines](
https://tekton.dev/docs/pipelines/pipelines-in-pipelines/), remains an
unimplemented `alpha` feature in Tekton,
we will need the [yq](https://github.com/mikefarah/yq) (at least `4.0`)
to pull the tasks from our previous `python-tracer-ci-pipeline` into the
new pipeline `github-pr-python-tracer-ci-pipeline`.

````bash
   (cat github-pr-pipeline.yaml.part && yq '{"a": {"b": .spec.tasks}}' pipeline.yaml| tail --lines=+3) | kubectl apply -f -
````

#### Create the GitHub PR Event Listener, TriggerTemplate and TriggerBinding

Once the new GitHub specific pipeline is created, we need a listener which starts
a new `PipelineRun` based on GitHub events.

````bash
   kubectl apply --filename github-pr-eventlistener.yaml
````

After this ensure that there is a pod and a service created:

````bash
   kubectl get pod | grep -i el-github-pr-python-eventlistener
   kubectl get svc | grep -i el-github-pr-python-eventlistener
````

Do not continue if any of these missing.

#### Create the Ingress for the GitHub Webhook to come through

You will need an ingress controller for this.
On IKS you might want to read these resources:
* [managed ingress](https://cloud.ibm.com/docs/containers?topic=containers-managed-ingress-about)
* Or unmanaged [ingress controller howto](
https://github.com/IBM-Cloud/iks-ingress-controller/blob/master/docs/installation.md
).

1. Check the available `ingressclass` resources on your cluster

````bash
   kubectl get ingressclass
````

* On `IKS` it will be `public-iks-k8s-nginx`.
* On `EKS` with the `ALB` ingress controller, it might be just `alb`
* On self hosted [nginx controller](https://kubernetes.github.io/ingress-nginx/deploy/)
  this might just be `nginx`.

Edit and save the value of `ingressClassName:` in `github-webhook-ingress.yaml`.

2. Find out your Ingress domain or subdomain name.

* On `IKS`, go to `Clusters` select your cluster and then click `Overview`.
  The domain name is listed under `Ingress subdomain`.

and create the resource:

````bash
   kubectl apply --filename github-webhook-ingress.yaml
````

Make sure that you can use the ingress with the `/hooks` path via `https`:
````bash
   curl https://<INGRESS_DOMAIN_NAME>/hooks
````

At this point this should respond this:
```json
  {
   "eventListener":"github-pr-eventlistener",
   "namespace":"default",
   "eventListenerUID":"",
   "errorMessage":"Invalid event body format : unexpected end of JSON input"
   }
```

#### Setup the webhook on GitHub

In the GitHub repo go to `Settings` -> `Webhooks` and click `Add Webhook`.
The fields we need to set are:
* `Payload URL`: `https://<INGRESS_DOMAIN_NAME>/hooks`
* `Content type`: application/json
* `Secret`: XXXXXXX (the secret token from github-interceptor-secret.yaml)

Under `SSL verification` select the radio button for `Enable SSL verification`.
Under `Which events would you like to trigger this webhook?` select
the radio button for `Let me select individual events.` and thick the checkbox next to
`Pull requests` and ensure that the rest are unthicked.

Click `Add webhook`.

If the webhook has been set up correctly, then GitHub sends a ping message.
Ensure that the ping is received from GitHub, and that it is filtered out so
a simple ping event does not trigger any `PipelineRun` unnecessarily.

````bash
eventlistener_pod=$(kubectl get pods -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' | grep el-github-pr-python-eventlistener-)
kubectl logs -f "${eventlistener_pod}" | grep 'event type ping is not allowed'
````

## Setup Scheduled PipelineRuns

PipelineRuns can be scheduled with a Kubernetes `CronJob` resource,
which calls a Tekton `EventListener`, that triggers
an appropriate PipelineRun. The needed resources can be created
with the following command:

````bash
   kubectl apply --filename scheduled-eventlistener.yaml
````

The current schedule is `"5 0 * * Mon-Fri`,
whic means every weekday 00:05 in the pod's timezone.
This can be adjusted by editing the `schedule` attribute.
Currently this triggers the `github-pr-python-tracer-ci-pipeline`
on the head of the `main` branch.
These can also be changed on demand.
