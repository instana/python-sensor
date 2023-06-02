#!/usr/bin/env python3

import json
import logging
import os
import requests
import sys

from github import Github


def ensure_environment_variables_are_present():
    required_env_vars = ('GITHUB_RELEASE_TAG', 'GITHUB_TOKEN',
                         'SLACK_BOT_TOKEN', 'SLACK_CHANNEL_ID_RELEASES')

    for v in required_env_vars:
        if not os.environ.get(v):
            logging.fatal("A required environment variable is missing: %s", v)
            sys.exit(1)


def get_gh_release_info_text_with_token(release_tag, access_token):
    g = Github(access_token)
    repo_name = "instana/python-sensor"
    repo = g.get_repo(repo_name)
    release = repo.get_release(release_tag)

    logging.info("GH Release fetched successfully %s", release)

    msg = (
        f":mega: :package: A new version is released in {repo_name}\n"
        f"Name: {release.title}\n"
        f"Tag: {release.tag_name}\n"
        f"Created at: {release.created_at}\n"
        f"Published at: {release.published_at}\n"
        f"{release.body}\n")

    logging.info(msg)
    return msg


def post_on_slack_channel(slack_token, slack_channel_id, message_text):
    api_url = "https://slack.com/api/chat.postMessage"

    headers = {"Authorization": f"Bearer {slack_token}",
               "Content-Type": "application/json"}
    body = {"channel": slack_channel_id, "text": message_text}

    response = requests.post(api_url, headers=headers, data=json.dumps(body))
    response_data = json.loads(response.text)

    if response_data["ok"]:
        logging.info("Message sent successfully!")
    else:
        logging.fatal("Error sending message: %s", response_data['error'])


def main():
    # Setting this globally to DEBUG will also debug PyGithub,
    # which will produce even more log output
    logging.basicConfig(level=logging.INFO)
    ensure_environment_variables_are_present()

    msg = get_gh_release_info_text_with_token(os.environ['GITHUB_RELEASE_TAG'],
                                              os.environ['GITHUB_TOKEN'])

    post_on_slack_channel(os.environ['SLACK_BOT_TOKEN'],
                          os.environ['SLACK_CHANNEL_ID_RELEASES'],
                          msg)


if __name__ == "__main__":
    main()
