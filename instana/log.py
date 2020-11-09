from __future__ import print_function
import os
import logging

logger = None


def get_standard_logger():
    """
    Retrieves and configures a standard logger for the Instana package

    @return: Logger
    """
    standard_logger = logging.getLogger("instana")

    ch = logging.StreamHandler()
    f = logging.Formatter('%(asctime)s: %(process)d %(levelname)s %(name)s: %(message)s')
    ch.setFormatter(f)
    standard_logger.addHandler(ch)
    standard_logger.setLevel(logging.DEBUG)
    return standard_logger


def get_aws_lambda_logger():
    """
    Retrieves the preferred logger for AWS Lambda

    @return: Logger
    """
    aws_lambda_logger = logging.getLogger()
    aws_lambda_logger.setLevel(logging.INFO)
    return aws_lambda_logger

def glogging_available():
    package_check = False

    # Is the glogging package available?
    try:
        from gunicorn import glogging
    except ImportError:
        pass
    else:
        package_check = True
    
    return package_check

def gunicorn_logging_available():
    from .util import running_in_gunicorn
    return running_in_gunicorn() and glogging_available()

aws_env = os.environ.get("AWS_EXECUTION_ENV", "")
env_is_aws_lambda = "AWS_Lambda_" in aws_env

if gunicorn_logging_available():
    logger = logging.getLogger("gunicorn.error")
elif env_is_aws_lambda is True:
    logger = get_aws_lambda_logger()
else:
    logger = get_standard_logger()
