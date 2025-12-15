# Standard Libraries
import json
import re
from datetime import datetime

import pandas as pd

# Third Party
import requests
from bs4 import BeautifulSoup
from kubernetes import client, config
from packaging.version import Version

JSON_FILE = "resources/table.json"
REPORT_FILE = "docs/report.md"
PIP_INDEX_URL = "https://pypi.org/pypi"
PEP_BASE_URL = "https://peps.python.org/"

SPEC_MAP = {
    "ASGI": "https://asgi.readthedocs.io/en/latest/specs/main.html",
    "WSGI": "https://peps.python.org/numerical",
}


def estimate_days_behind(release_date):
    return datetime.today() - datetime.strptime(release_date, "%Y-%m-%d")


def get_upstream_version(dependency, last_supported_version):
    """Get the latest version available upstream"""
    last_supported_version_release_date = "Not found"
    if dependency in SPEC_MAP:
        # webscrape info from official website
        version_pattern = r"(\d+\.\d+\.?\d*)"
        latest_version_release_date = ""

        url = SPEC_MAP[dependency]
        page = requests.get(url)
        soup = BeautifulSoup(page.text, "html.parser")
        # ASGI
        if "asgi" in url:
            all_versions = soup.find(id="version-history").find_all("li")
            pattern = re.compile(r"([\d.]+) \((\d{4}-\d{2}-\d{2})\)")
            latest_version, latest_version_release_date = pattern.search(
                all_versions[0].text
            ).groups()
            for li in all_versions:
                match = pattern.search(li.text)
                if match:
                    version, date = match.groups()
                    if version == last_supported_version:
                        last_supported_version_release_date = date
                        break
        # WSGI
        else:
            all_versions = soup.find(id="numerical-index").find_all(
                "a", string=re.compile("Web Server Gateway Interface")
            )
            latest_version = re.search(version_pattern, all_versions[-1].text).group()

            for a in all_versions:
                pep_link = PEP_BASE_URL + a.get("href").split("..")[1]
                response = requests.get(pep_link)
                soup = BeautifulSoup(response.text, "html.parser")
                version = re.search(version_pattern, a.text).group()
                pep_page_metadata = soup.find("dl")

                if pep_page_metadata and version in [
                    latest_version,
                    last_supported_version,
                ]:
                    metadata_fields = pep_page_metadata.find_all("dt")
                    metadata_values = pep_page_metadata.find_all("dd")

                    for dt, dd in zip(metadata_fields, metadata_values):
                        if "Created" in dt.text:
                            release_date = dd.text.strip()
                            release_date_as_datetime = datetime.strptime(
                                release_date, "%d-%b-%Y"
                            )
                            if version == latest_version:
                                latest_version_release_date = (
                                    release_date_as_datetime.strftime("%Y-%m-%d")
                                )
                            if version == last_supported_version:
                                last_supported_version_release_date = (
                                    release_date_as_datetime.strftime("%Y-%m-%d")
                                )
        return (
            latest_version,
            latest_version_release_date,
            last_supported_version_release_date,
        )

    else:
        # get info using PYPI API
        response = requests.get(f"{PIP_INDEX_URL}/{dependency}/json")
        response_json = response.json()

        latest_version = response_json["info"]["version"]
        release_info_latest = response_json["releases"][latest_version]
        release_time_latest = release_info_latest[-1]["upload_time_iso_8601"]
        release_date_latest = re.search(r"([\d-]+)T", release_time_latest)[1]

        release_info_last_supported = response_json["releases"][last_supported_version]
        release_time_last_supported = release_info_last_supported[-1]["upload_time_iso_8601"]
        release_date_last_supported = re.search(r"([\d-]+)T", release_time_last_supported)[1]

        return (
            latest_version,
            release_date_latest,
            release_date_last_supported,
        )


def get_last_supported_version(tekton_ci_output, dependency):
    """Get up-to-date supported version"""
    if dependency == "Psycopg2":
        dependency = "psycopg2-binary"
    
    # either start with a space or in a new line
    pattern = r"(?:^|\s)" + dependency + r"-([^\s]+)"

    last_supported_version = re.search(
        pattern, tekton_ci_output, flags=re.I | re.M
    )

    return last_supported_version[1]


def is_up_to_date(
    last_supported_version, latest_version, last_supported_version_release_date
):
    """Check if the supported package is up-to-date"""
    if Version(last_supported_version) >= Version(latest_version):
        up_to_date = "Yes"
        days_behind = 0
    else:
        up_to_date = "No"
        days_behind = estimate_days_behind(last_supported_version_release_date)

    return up_to_date, days_behind

def taskrun_filter(taskrun):
    return any(
        condition["type"] == "Succeeded" and condition["status"] == "True"
        for condition in taskrun["status"]["conditions"]
    )
    
def get_taskruns(namespace, task_name):
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
                match = re.search(r"Successfully installed .*(gevent-[^\s]+) .* (starlette-[^\s]+)", logs)
                tekton_ci_output += f"{match[1]}\n{match[2]}\n"
            elif task_name == "python-tracer-unittest-kafka-task":
                match = re.search(r"Successfully installed .*(confluent-kafka-[^\s]+) .* (kafka-python-ng-[^\s]+)", logs)
                tekton_ci_output += f"{match[1]}\n{match[2]}\n"
            elif task_name == "python-tracer-unittest-cassandra-task":
                match = re.search(r"Successfully installed .*(cassandra-driver-[^\s]+)", logs)
                tekton_ci_output += f"{match[1]}\n"
            elif task_name == "python-tracer-unittest-default-task":
                lines = re.findall(r"^Successfully installed .*", logs, re.M)
                tekton_ci_output += "\n".join(lines)
            break
        else:
            print(
                f"Unable to retrieve container logs from the successful taskrun pod {pod_name} of taskrun {taskrun_name}."
            )
    return tekton_ci_output


def get_tekton_ci_output():
    """Get the latest successful scheduled tekton pipeline output"""
    try:
        config.load_incluster_config()
        print("Using in-cluster Kubernetes configuration...")
    except config.config_exception.ConfigException:
        # Fall back to local config if running locally and not inside cluster
        config.load_kube_config()
        print("Using local Kubernetes configuration...")

    namespace = "default"
    core_v1_client = client.CoreV1Api()

    tasks = [
        "python-tracer-unittest-gevent-starlette-task",
        "python-tracer-unittest-kafka-task",
        "python-tracer-unittest-cassandra-task",
        "python-tracer-unittest-default-task"
    ]

    tekton_ci_output = ""

    for task_name in tasks:
        try:
            taskruns = get_taskruns(namespace, task_name)
                
            tekton_ci_output = process_taskrun_logs(
                taskruns, core_v1_client, namespace, task_name, tekton_ci_output
            )
        except Exception as exc:
            print(f"Error processing task {task_name}: {str(exc)}")

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

        latest_version, release_date, last_supported_version_release_date = (
            get_upstream_version(package, last_supported_version)
        )

        up_to_date, days_behind = is_up_to_date(
            last_supported_version, latest_version, last_supported_version_release_date
        )

        item.update(
            {
                "Latest version": latest_version,
                "Up-to-date": up_to_date,
                "Release date": release_date,
                "Latest Version Published At": last_supported_version_release_date,
                "Days behind": f"{days_behind} day/s",
            }
        )

    # Create a DataFrame from the list of dictionaries
    df = pd.DataFrame(items)
    df.insert(len(df.columns) - 1, "Cloud Native", df.pop("Cloud Native"))

    # Convert dataframe to markdown
    markdown_table = df.to_markdown(index=False)

    disclaimer = "##### This page is auto-generated. Any change will be overwritten after the next sync. Please apply changes directly to the files in the [python tracer](https://github.com/instana/python-sensor) repo."
    title = "## Python supported packages and versions"

    # Combine disclaimer, title, and markdown table with line breaks
    final_markdown = f"{disclaimer}\n{title}\n{markdown_table}\n"

    with open(REPORT_FILE, "w") as file:
        file.write(final_markdown)


if __name__ == "__main__":
    main()
