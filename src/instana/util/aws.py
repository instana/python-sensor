# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from ..log import logger

def normalize_aws_lambda_arn(context):
    """
    Parse the AWS Lambda context object for a fully qualified AWS Lambda function ARN.

    This method will ensure that the returned value matches the following ARN pattern:
      arn:aws:lambda:${region}:${account-id}:function:${name}:${version}

    @param context:  AWS Lambda context object
    @return:
    """
    try:
        arn = context.invoked_function_arn
        parts = arn.split(':')

        count = len(parts)
        if count == 7:
            # need to append version
            arn = arn + ':' + context.function_version
        elif count != 8:
            logger.debug("Unexpected ARN parse issue: %s", arn)

        return arn
    except Exception:
        logger.debug("normalize_arn: ", exc_info=True)
