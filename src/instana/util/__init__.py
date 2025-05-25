# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import importlib.metadata
import json
from collections import defaultdict
from typing import Any, DefaultDict
from urllib import parse

from instana.log import logger


def nested_dictionary() -> DefaultDict[str, Any]:
    return defaultdict(DictionaryOfStan)


# Simple implementation of a nested dictionary.
DictionaryOfStan: DefaultDict[str, Any] = nested_dictionary


# Assisted by watsonx Code Assistant
def to_json(obj: Any) -> bytes:
    """
    Convert the given object to a JSON binary string.

    This function is primarily used to serialize objects from `json_span.py`
    until a switch to nested dictionaries (or a better solution) is made.

    :param obj: The object to serialize to JSON.
    :return: The JSON string encoded as bytes.
    """
    try:

        def extractor(o: Any) -> dict:
            """
            Extract dictionary-like attributes from an object.

            :param o: The object to extract attributes from.
            :return: A dictionary containing the object's attributes.
            """
            if not hasattr(o, "__dict__"):
                logger.debug(f"Couldn't serialize non dict type: {type(o)}")
                return {}
            else:
                return {k.lower(): v for k, v in o.__dict__.items() if v is not None}

        return json.dumps(
            obj, default=extractor, sort_keys=False, separators=(",", ":")
        ).encode()
    except Exception:
        logger.debug("to_json non-fatal encoding issue: ", exc_info=True)


# Assisted by watsonx Code Assistant
def to_pretty_json(obj: Any) -> str:
    """
    Convert an object to a pretty-printed JSON string.

    This function is primarily used for logging and debugging purposes.

    :param obj: the object to serialize to json
    :return:  json string
    """
    try:

        def extractor(o):
            if not hasattr(o, "__dict__"):
                logger.debug("Couldn't serialize non dict type: %s", type(o))
                return {}
            else:
                return {k.lower(): v for k, v in o.__dict__.items() if v is not None}

        return json.dumps(
            obj, default=extractor, sort_keys=True, indent=4, separators=(",", ":")
        )
    except Exception:
        logger.debug("to_pretty_json non-fatal encoding issue: ", exc_info=True)


# Assisted by watsonx Code Assistant
def package_version() -> str:
    """
    Determine the version of the 'instana' package.

    This function uses the `importlib.metadata` module to fetch the version of
    the 'instana' package.
    If the package is not found, it returns 'unknown'.

    :return: A string representing the version of the 'instana' package.
    """
    try:
        version = importlib.metadata.version("instana")
    except importlib.metadata.PackageNotFoundError:
        logger.debug("Not able to identify the Instana package version.")
        version = "unknown"

    return version


# Assisted by watsonx Code Assistant
def get_default_gateway() -> str:
    """
    Attempts to read /proc/self/net/route to determine the default gateway in use.

    This function reads the /proc/self/net/route file, which contains network
    routing information for the current process.
    It specifically looks for the line where the Destination is 00000000,
    indicating the default route.
    The Gateway IP is encoded backwards in hex, which this function decodes and
    converts to a standard IP address format.

    :return: String -   the ip address of the default gateway or None if not
                        found/possible/non-existant
    """
    try:
        hip = None
        # The first line is the header line
        # We look for the line where the Destination is 00000000 - that is the default route
        # The Gateway IP is encoded backwards in hex.
        with open("/proc/self/net/route") as routes:
            for line in routes:
                parts = line.split("\t")
                if parts[1] == "00000000":
                    hip = parts[2]

        if hip is not None and len(hip) == 8:
            # Reverse order, convert hex to int
            return f"{int(hip[6:8], 16)}.{int(hip[4:6], 16)}.{int(hip[2:4], 16)}.{int(hip[0:2], 16)}"

    except Exception:
        logger.warning("get_default_gateway: ", exc_info=True)


# Assisted by watsonx Code Assistant
def validate_url(url: str) -> bool:
    """
    Validate if the provided <url> is a valid URL.

    This function checks if the given string is a valid URL by attempting to
    parse it using the `urlparse` function from the `urllib.parse` module.
    A URL is considered valid if it has both a scheme (like 'http' or 'https')
    and a network location (netloc).

    Examples:
    - "http://localhost:5000" - valid
    - "http://localhost:5000/path" - valid
    - "sandwich" - invalid

    @param url: A string representing the URL to validate.
    @return: A boolean value. Returns `True` if the URL is valid, otherwise `False`.
    """
    try:
        result = parse.urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        pass

    return False
