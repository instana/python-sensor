#!/usr/bin/env python3

import json
import logging
import os
import sys

import requests
from github import Github


def ensure_environment_variables_are_present() -> None:
    required_env_vars = (
        "GITHUB_RELEASE_TAG",
        "GITHUB_TOKEN",
        "SLACK_BOT_SERVICE_ID",
        "SLACK_BOT_TOKEN",
        "SLACK_CHANNEL_ID_RELEASES",
    )

    for env_var in required_env_vars:
        if env_var not in os.environ:
            logging.fatal(f"A required environment variable is missing: {env_var}")
            sys.exit(1)


def get_gh_release_info_text_with_token(release_tag: str, access_token: str) -> str:
    gh = Github(access_token)
    repo_name = "instana/python-sensor"
    repo = gh.get_repo(repo_name)
    release = repo.get_release(release_tag)

    logging.info("GH Release fetched successfully %s", release)

    msg = (
        f":mega: Oyez! Oyez! Oyez!\n"
        f":package: A new version of the Python Tracer has been released.\n"
        f"Name: Instana Python Tracer {release.title}\n"
        f"Tag: {release.tag_name}\n"
        f"Created at: {release.created_at}\n"
        f"Published at: {release.published_at}\n"
        f"{release.body}\n"
    )

    logging.info(msg)
    return msg


def post_on_slack_channel(
    slack_webhook_service_id: str,
    slack_token: str,
    slack_channel_id: str,
    message_text: str,
) -> None:
    api_url = f"https://hooks.slack.com/services/T{slack_channel_id}/B{slack_webhook_service_id}/{slack_token}"

    headers = {
        "Content-Type": "application/json",
    }
    body = {"text": message_text}

    response = requests.post(api_url, headers=headers, data=json.dumps(body))
    response_data = json.loads(response.text)

    if response_data["ok"]:
        logging.info("Message sent successfully!")
    else:
        logging.fatal("Error sending message: %s", response_data["error"])


def main() -> None:
    # Setting this globally to DEBUG will also debug PyGithub,
    # which will produce even more log output
    logging.basicConfig(level=logging.INFO)
    ensure_environment_variables_are_present()

    msg = get_gh_release_info_text_with_token(
        os.environ["GITHUB_RELEASE_TAG"], os.environ["GITHUB_TOKEN"]
    )

    post_on_slack_channel(
        os.environ["SLACK_BOT_SERVICE_ID"],
        os.environ["SLACK_BOT_TOKEN"],
        os.environ["SLACK_CHANNEL_ID_RELEASES"],
        msg,
    )


if __name__ == "__main__":
    main()
