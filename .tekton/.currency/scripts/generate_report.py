# Standard Libraries
import re
import json
from datetime import date

# Third Party
import requests
import pandas as pd
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
    """get the latest version available upstream"""
    if dependency in SPEC_MAP:
        # webscrape info from official website
        pattern = "(\d+\.\d+\.?\d*)"

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
    """get up-to-date supported version"""
    pattern = r"-([^\s]+)"

    if dependency == "Psycopg2":
        dependency = "psycopg2-binary"

    last_supported_version = re.search(
        dependency + pattern, tekton_ci_output, flags=re.I | re.M
    )

    return last_supported_version[1]


def isUptodate(last_supported_version, latest_version):
    if last_supported_version == latest_version:
        up_to_date = "Yes"
    else:
        up_to_date = "No"

    return up_to_date


def get_tekton_ci_output():
    # config.load_kube_config()
    config.load_incluster_config()

    group = "tekton.dev"
    version = "v1"
    namespace = "default"
    plural = "taskruns"

    # access the custom resource from tekton
    tektonV1 = client.CustomObjectsApi()
    taskruns = tektonV1.list_namespaced_custom_object(
        group,
        version,
        namespace,
        plural,
        label_selector=f"{group}/task=python-tracer-unittest-default-task",
    )["items"]

    taskruns.sort(key=lambda tr: tr["metadata"]["creationTimestamp"], reverse=True)

    coreV1 = client.CoreV1Api()
    tekton_ci_output = ""
    for tr in taskruns:
        if (
            re.match("python-trace\w+-unittest-default-3", tr["metadata"]["name"])
            and tr["status"]["conditions"][0]["type"] == "Succeeded"
        ):
            pod = tr["status"]["podName"]
            logs = coreV1.read_namespaced_pod_log(
                pod, namespace, container="step-unittest"
            )
            if "Successfully installed" in logs:
                for line in logs.splitlines():
                    if "Successfully installed" in line:
                        tekton_ci_output += line
                break
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

    # Rename Columns
    df.columns = [
        "Package name",
        "Support Policy",
        "Beta version",
        "Last Supported Version",
        "Latest version",
        "Up-to-date",
        "Cloud Native",
    ]

    # Convert dataframe to markdown
    markdown_table = df.to_markdown(index=False)

    current_date = date.today().strftime("%b %d, %Y")

    disclaimer = f"##### This page is auto-generated. Any change will be overwritten after the next sync. Please apply changes directly to the files in the [python tracer](https://github.com/instana/python-sensor) repo. Last updated on **{current_date}**."
    title = "## Python supported packages and versions"

    # Combine disclaimer, title, and markdown table with line breaks
    final_markdown = disclaimer + "\n" + title + "\n" + markdown_table

    with open(REPORT_FILE, "w") as file:
        file.write(final_markdown)


if __name__ == "__main__":
    main()
