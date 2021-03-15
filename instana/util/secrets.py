# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import re
import re
import sys

try:
    from urllib import parse
except ImportError:
    import urlparse as parse
    import urllib

from ..util import PY2, PY3
from ..log import logger


def contains_secret(candidate, matcher, kwlist):
    """
    This function will indicate whether <candidate> contains a secret as described here:
    https://www.instana.com/docs/setup_and_manage/host_agent/configuration/#secrets

    :param candidate: string to check
    :param matcher: the matcher to use
    :param kwlist: the list of keywords to match
    :return: boolean
    """
    try:
        if candidate is None or candidate == "INSTANA_AGENT_KEY":
            return False

        if not isinstance(kwlist, list):
            logger.debug("contains_secret: bad keyword list")
            return False

        if matcher == 'equals-ignore-case':
            for keyword in kwlist:
                if candidate.lower() == keyword.lower():
                    return True
        elif matcher == 'equals':
            for keyword in kwlist:
                if candidate == keyword:
                    return True
        elif matcher == 'contains-ignore-case':
            for keyword in kwlist:
                if keyword.lower() in candidate:
                    return True
        elif matcher == 'contains':
            for keyword in kwlist:
                if keyword in candidate:
                    return True
        elif matcher == 'regex':
            for regexp in kwlist:
                if re.match(regexp, candidate):
                    return True
        else:
            logger.debug("contains_secret: unknown matcher")
            return False

    except Exception:
        logger.debug("contains_secret", exc_info=True)


def strip_secrets_from_query(qp, matcher, kwlist):
    """
    This function will scrub the secrets from a query param string based on the passed in matcher and kwlist.

    blah=1&secret=password&valid=true will result in blah=1&secret=<redacted>&valid=true

    You can even pass in path query combinations:

    /signup?blah=1&secret=password&valid=true will result in /signup?blah=1&secret=<redacted>&valid=true

    :param qp: a string representing the query params in URL form (unencoded)
    :param matcher: the matcher to use
    :param kwlist: the list of keywords to match
    :return: a scrubbed query param string
    """
    path = None

    try:
        if qp is None:
            return ''

        if not isinstance(kwlist, list):
            logger.debug("strip_secrets_from_query: bad keyword list")
            return qp

        # If there are no key=values, then just return
        if not '=' in qp:
            return qp

        if '?' in qp:
            path, query = qp.split('?')
        else:
            query = qp

        params = parse.parse_qsl(query, keep_blank_values=True)
        redacted = ['<redacted>']

        if matcher == 'equals-ignore-case':
            for keyword in kwlist:
                for index, kv in enumerate(params):
                    if kv[0].lower() == keyword.lower():
                        params[index] = (kv[0], redacted)
        elif matcher == 'equals':
            for keyword in kwlist:
                for index, kv in enumerate(params):
                    if kv[0] == keyword:
                        params[index] = (kv[0], redacted)
        elif matcher == 'contains-ignore-case':
            for keyword in kwlist:
                for index, kv in enumerate(params):
                    if keyword.lower() in kv[0].lower():
                        params[index] = (kv[0], redacted)
        elif matcher == 'contains':
            for keyword in kwlist:
                for index, kv in enumerate(params):
                    if keyword in kv[0]:
                        params[index] = (kv[0], redacted)
        elif matcher == 'regex':
            for regexp in kwlist:
                for index, kv in enumerate(params):
                    if re.match(regexp, kv[0]):
                        params[index] = (kv[0], redacted)
        else:
            logger.debug("strip_secrets_from_query: unknown matcher")
            return qp

        if PY2:
            result = urllib.urlencode(params, doseq=True)
        else:
            result = parse.urlencode(params, doseq=True)
        query = parse.unquote(result)

        if path:
            query = path + '?' + query

        return query
    except Exception:
        logger.debug("strip_secrets_from_query", exc_info=True)
