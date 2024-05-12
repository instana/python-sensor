# Standard Libraries
import re
import json
from os import system
from datetime import date

# Third Party
import requests
import pandas as pd
from bs4 import BeautifulSoup


JSON_FILE = "resources/table.json"
REPORT_FILE = "docs/report.md"
TEKTON_CI_OUT_FILE = "utils/tekton-ci-output.txt"
TEKTON_CI_OUT_SCRIPT = "scripts/get-tekton-ci-output.sh"
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


## Get the tekton ci output of the installed python dependencies
system("bash " + TEKTON_CI_OUT_SCRIPT)

with open(TEKTON_CI_OUT_FILE) as file:
    content = file.read()


def get_last_supported_version(dependency):
    """get up-to-date supported version"""
    pattern = r"-([^\s]+)"

    if dependency == "Psycopg2":
        dependency = "psycopg2-binary"

    last_supported_version = re.search(dependency + pattern, content, flags=re.I | re.M)

    return last_supported_version[1]


def isUptodate(last_supported_version, latest_version):
    if last_supported_version == latest_version:
        up_to_date = "Yes"
    else:
        up_to_date = "No"

    return up_to_date


# Read the JSON file
with open(JSON_FILE) as file:
    data = json.load(file)


items = data["table"]

for index in range(len(items)):
    item = items[index]
    package = item["package_name"]

    if "last_supported_version" not in item:
        last_supported_version = get_last_supported_version(package)
        item.update({"last_supported_version": last_supported_version})
    else:
        last_supported_version = item["last_supported_version"]

    latest_version = get_upstream_version(package)
    item.update({"latest_version": latest_version})

    up_to_date = isUptodate(last_supported_version, latest_version)

    item.update({"up_to_date": up_to_date})


# Create a DataFrame from the list of dictionaries
df = pd.DataFrame(items)
df.insert(len(df.columns) - 1, "cloud_native", df.pop("cloud_native"))

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

disclaimer = f"<sup>This page is auto-generated. Any change will be overwritten after the next sync. Please apply changes directly to the files in the [python tracer](https://github.com/instana/python-sensor) repo. Last updated on **{current_date}**.</sup>"
title = "## Python supported packages and versions"

# Combine disclaimer, title, and markdown table with line breaks
final_markdown = disclaimer + "\n" + title + "\n" + markdown_table

with open(REPORT_FILE, "w") as file:
    file.write(final_markdown)
