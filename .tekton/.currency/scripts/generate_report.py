# Standard Libraries
import json
import re

import pandas as pd

# Third Party
import requests
from bs4 import BeautifulSoup
from kubernetes import client, config

JSON_FILE = "resources/table.json"
REPORT_FILE = "docs/report.md"
PIP_INDEX_URL = "https://pypi.org/pypi"

SPEC_MAP = {
    "ASGI": "https://asgi.readthedocs.io/en/latest/specs/main.html",
    "WSGI": "https://peps.python.org/",
}


def get_upstream_version(dependency):
    """Get the latest version available upstream"""
    if dependency in SPEC_MAP:
        # webscrape info from official website
        pattern = r"(\d+\.\d+\.?\d*)"

        url = SPEC_MAP[dependency]
        page = requests.get(url)
        soup = BeautifulSoup(page.text, "html.parser")
        # ASGI
        if "asgi" in url:
            text = (
                soup.find(id="version-history")
                .findChild("li", string=re.compile(pattern))
                .text
            )
        # WSGI
        else:
            tag = soup.find(id="numerical-index").find_all(
                "a", string=re.compile("Web Server Gateway Interface")
            )[-1]
            text = tag.text
        res = re.search(pattern, text)
        return res[1]

    else:
        # get info using PYPI API
        response = requests.get(f"{PIP_INDEX_URL}/{dependency}/json")
        response_json = response.json()
        latest_version = response_json["info"]["version"]
        return latest_version


def get_last_supported_version(tekton_ci_output, dependency):
    """Get up-to-date supported version"""
    pattern = r"-([^\s]+)"

    if dependency == "Psycopg2":
        dependency = "psycopg2-binary"

    last_supported_version = re.search(
        dependency + pattern, tekton_ci_output, flags=re.I | re.M
    )

    return last_supported_version[1]


def isUptodate(last_supported_version, latest_version):
    """Check if the supported package is up-to-date"""
    if last_supported_version == latest_version:
        up_to_date = "Yes"
    else:
        up_to_date = "No"

    return up_to_date


def get_taskruns(namespace, task_name, taskrun_filter):
    """Get sorted taskruns filtered based on label_selector"""
    group = "tekton.dev"
    version = "v1"
    plural = "taskruns"

    # access the custom resource from tekton
    tektonV1 = client.CustomObjectsApi()
    taskruns = tektonV1.list_namespaced_custom_object(
        group,
        version,
        namespace,
        plural,
        label_selector=f"{group}/task={task_name}, triggers.tekton.dev/trigger=python-tracer-scheduled-pipeline-triggger",
    )["items"]

    filtered_taskruns = list(filter(taskrun_filter, taskruns))
    filtered_taskruns.sort(
        key=lambda tr: tr["metadata"]["creationTimestamp"], reverse=True
    )

    return filtered_taskruns


def process_taskrun_logs(
    taskruns, core_v1_client, namespace, task_name, tekton_ci_output
):
    """Process taskrun logs"""
    for tr in taskruns:
        pod_name = tr["status"]["podName"]
        taskrun_name = tr["metadata"]["name"]
        logs = core_v1_client.read_namespaced_pod_log(
            pod_name, namespace, container="step-unittest"
        )
        if "Successfully installed" in logs:
            print(
                f"Retrieving container logs from the successful taskrun pod {pod_name} of taskrun {taskrun_name}.."
            )
            if task_name == "python-tracer-unittest-gevent-starlette-task":
                match = re.search(r"Successfully installed .* (starlette-[^\s]+)", logs)
                tekton_ci_output += f"{match[1]}\n"
            elif task_name == "python-tracer-unittest-googlecloud-task":
                match = re.search("Successfully installed .* (google-cloud-storage-[^\s]+)", logs)
                tekton_ci_output += f"{match[1]}\n"
            elif task_name == "python-tracer-unittest-default-task":
                for line in logs.splitlines():
                    if "Successfully installed" in line:
                        tekton_ci_output += line
            break
        else:
            print(
                f"Unable to retrieve container logs from the successful taskrun pod {pod_name} of taskrun {taskrun_name}."
            )
    return tekton_ci_output


def get_tekton_ci_output():
    """Get the latest successful scheduled tekton pipeline output"""
    # config.load_kube_config()
    config.load_incluster_config()

    namespace = "default"
    core_v1_client = client.CoreV1Api()

    task_name = "python-tracer-unittest-gevent-starlette-task"
    taskrun_filter = lambda tr: tr["status"]["conditions"][0]["type"] == "Succeeded"
    starlette_taskruns = get_taskruns(namespace, task_name, taskrun_filter)

    tekton_ci_output = process_taskrun_logs(
        starlette_taskruns, core_v1_client, namespace, task_name, ""
    )

    task_name = "python-tracer-unittest-googlecloud-task"
    taskrun_filter = (
        lambda tr: tr["metadata"]["name"].endswith("unittest-googlecloud-0")
        and tr["status"]["conditions"][0]["type"] == "Succeeded"
    )
    googlecloud_taskruns = get_taskruns(namespace, task_name, taskrun_filter)

    tekton_ci_output = process_taskrun_logs(
        googlecloud_taskruns, core_v1_client, namespace, task_name, tekton_ci_output
    )

    task_name = "python-tracer-unittest-default-task"
    taskrun_filter = (
        lambda tr: tr["metadata"]["name"].endswith("unittest-default-3")
        and tr["status"]["conditions"][0]["type"] == "Succeeded"
    )
    default_taskruns = get_taskruns(namespace, task_name, taskrun_filter)

    tekton_ci_output = process_taskrun_logs(
        default_taskruns, core_v1_client, namespace, task_name, tekton_ci_output
    )

    return tekton_ci_output


def main():
    # Read the JSON file
    with open(JSON_FILE) as file:
        data = json.load(file)

    items = data["table"]
    tekton_ci_output = get_tekton_ci_output()

    for item in items:
        package = item["Package name"]

        if "Last Supported Version" not in item:
            last_supported_version = get_last_supported_version(
                tekton_ci_output, package
            )
            item.update({"Last Supported Version": last_supported_version})
        else:
            last_supported_version = item["Last Supported Version"]

        latest_version = get_upstream_version(package)

        up_to_date = isUptodate(last_supported_version, latest_version)

        item.update({"Latest version": latest_version, "Up-to-date": up_to_date})

    # Create a DataFrame from the list of dictionaries
    df = pd.DataFrame(items)
    df.insert(len(df.columns) - 1, "Cloud Native", df.pop("Cloud Native"))

    # Convert dataframe to markdown
    markdown_table = df.to_markdown(index=False)

    disclaimer = "##### This page is auto-generated. Any change will be overwritten after the next sync. Please apply changes directly to the files in the [python tracer](https://github.com/instana/python-sensor) repo."
    title = "## Python supported packages and versions"

    # Combine disclaimer, title, and markdown table with line breaks
    final_markdown = disclaimer + "\n" + title + "\n" + markdown_table

    with open(REPORT_FILE, "w") as file:
        file.write(final_markdown)


if __name__ == "__main__":
    main()
