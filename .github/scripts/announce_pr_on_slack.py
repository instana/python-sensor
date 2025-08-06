#!/usr/bin/env python3
"""
GitHub Actions script to send Slack notifications for new pull requests.
"""

import os
import sys
from typing import Tuple

import httpx


def send_slack_message(
    slack_team: str, slack_service: str, slack_token: str, message: str
) -> bool:
    """Send a message to Slack channel."""

    url = (
        f"https://hooks.slack.com/services/T{slack_team}/B{slack_service}/{slack_token}"
    )

    headers = {
        "Content-Type": "application/json",
    }

    data = {"text": message}

    try:
        with httpx.Client() as client:
            response = client.post(url, headers=headers, json=data)
            response.raise_for_status()

            result = response.text
            if "ok" in result:
                print("✅ Slack message sent successfully")
                return True
            else:
                print(f"❌ Slack API error: {result}")
                return False

    except httpx.HTTPError as e:
        print(f"❌ Request error: {e}")
        return False


def ensure_environment_variables_are_present() -> (
    Tuple[str, str, str, str, str, str, str, str]
):
    """
    Ensures that all necessary environment variables are present for the application to run.

    This function checks for the presence of required environment variables related to Slack bot token,
    Pull Request (PR) details, and repository name. It also validates that the Slack channel is set.

    Raises:
        SystemExit: If any of the required environment variables are missing.

    Returns:
        A tuple containing the values of the following environment variables:
        - SLACK_TOKEN: The token for the Slack bot.
        - SLACK_TEAM: The ID of the Slack team.
        - SLACK_SERVICE: The ID of the Slack service.
        - PR_NUMBER: The number of the Pull Request.
        - PR_TITLE: The title of the Pull Request.
        - PR_URL: The URL of the Pull Request.
        - PR_AUTHOR: The author of the Pull Request.
        - REPO_NAME: The name of the repository.
    """
    # Get environment variables
    slack_token = os.getenv("SLACK_TOKEN")
    slack_team = os.getenv("SLACK_TEAM")
    slack_service = os.getenv("SLACK_SERVICE")
    pr_number = os.getenv("PR_NUMBER")
    pr_title = os.getenv("PR_TITLE")
    pr_url = os.getenv("PR_URL")
    pr_author = os.getenv("PR_AUTHOR")
    repo_name = os.getenv("REPO_NAME")

    # Validate required environment variables
    if not slack_token:
        print("❌ SLACK_TOKEN environment variable is required")
        sys.exit(1)

    if not slack_team:
        print("❌ SLACK_TEAM environment variable is required")
        sys.exit(1)

    if not slack_service:
        print("❌ SLACK_SERVICE environment variable is required")
        sys.exit(1)

    if not all([pr_number, pr_title, pr_url, pr_author, repo_name]):
        print(
            "❌ Missing required PR information (PR_NUMBER, PR_TITLE, PR_URL, PR_AUTHOR, REPO_NAME)"
        )
        sys.exit(1)

    # Since we're validating these variables, we can assert they're not None
    assert pr_number is not None
    assert pr_title is not None
    assert pr_url is not None
    assert pr_author is not None
    assert repo_name is not None

    return (
        slack_token,
        slack_team,
        slack_service,
        pr_number,
        pr_title,
        pr_url,
        pr_author,
        repo_name,
    )


def main() -> None:
    """Main function to process PR and send Slack notification."""

    (
        slack_token,
        slack_team,
        slack_service,
        pr_number,
        pr_title,
        pr_url,
        pr_author,
        repo_name,
    ) = ensure_environment_variables_are_present()

    print(f"Processing PR #{pr_number}")

    # Create Slack message
    message = (
        f":mega: Oyez! Oyez! Oyez!\n"
        f"Hello Team. Please, review the opened PR #{pr_number} in {repo_name}\n"
        f"*{pr_title}* by @{pr_author}\n"
        f":pull-request-opened: {pr_url}"
    )

    # Send to Slack
    success = send_slack_message(slack_service, slack_team, slack_token, message)

    if not success:
        sys.exit(1)

    print("✅ Process completed successfully")


if __name__ == "__main__":
    main()

# Made with Bob
