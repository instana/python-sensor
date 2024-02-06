# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import
from io import BytesIO
from zipfile import ZipFile
import unittest
import json

import boto3
import pytest

# TODO: Remove branching when we drop support for Python 3.7
import sys
if sys.version_info >= (3, 8):
  from moto import mock_aws
else:
  from moto import mock_lambda as mock_aws

from instana.singletons import tracer
from ...helpers import get_first_span_by_filter

class TestLambda(unittest.TestCase):
    def _get_role(self):
        iam = boto3.client("iam", region_name=self.lambda_region)
        return iam.create_role(
            RoleName="my-role",
            AssumeRolePolicyDocument="some policy"
        )["Role"]["Arn"]
        
    def _process_lambda(self, func_str):
        zip_output = BytesIO()
        with ZipFile(zip_output, "w") as zip_file:
            zip_file.writestr("lambda_function.py", func_str)
        return zip_output.getvalue()
    
    def _get_test_zip_file(self):
        pfunc = """
def lambda_handler(event, context):
    print("custom log event")
    return {"message": "success"}
"""
        return self._process_lambda(pfunc)

    def setUp(self):
        """ Clear all spans before a test run """
        self.recorder = tracer.recorder
        self.recorder.clear_spans()
        self.mock = mock_aws()
        self.mock.start()
        self.lambda_region = "us-east-1"
        self.aws_lambda = boto3.client('lambda', region_name=self.lambda_region)
        self.function_name = "myfunc"
        self.aws_lambda.create_function(
            FunctionName=self.function_name,
            Runtime="python3.9",
            Role=self._get_role(),
            Handler="lambda_function.lambda_handler",
            Code={"ZipFile": self._get_test_zip_file()}
        )

    def tearDown(self):
        # Stop Moto after each test
        self.mock.stop()


    @pytest.mark.skip("Lambda mocking requires docker")
    def test_lambda_invoke(self):
        with tracer.start_active_span('test'):
            result = self.aws_lambda.invoke(FunctionName=self.function_name)

        self.assertEqual(result["StatusCode"], 200)
        payload = json.loads(result["Payload"].read().decode("utf-8"))
        self.assertIn("message", payload)
        self.assertEqual("success", payload["message"])

        spans = tracer.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        filter = lambda span: span.n == "sdk"
        test_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(test_span)

        filter = lambda span: span.n == "boto3"
        boto_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(boto_span)

        self.assertEqual(boto_span.t, test_span.t)
        self.assertEqual(boto_span.p, test_span.s)

        self.assertIsNone(test_span.ec)
        self.assertIsNone(boto_span.ec)

        self.assertEqual(boto_span.data['boto3']['op'], 'Invoke')
        endpoint = f'https://lambda.{self.lambda_region}.amazonaws.com'
        self.assertEqual(boto_span.data['boto3']['ep'], endpoint)
        self.assertEqual(boto_span.data['boto3']['reg'], 'us-east-1')
        self.assertIn('FunctionName', boto_span.data['boto3']['payload'])
        self.assertEqual(boto_span.data['boto3']['payload']['FunctionName'], self.function_name)
        self.assertEqual(boto_span.data['http']['status'], 200)
        self.assertEqual(boto_span.data['http']['method'], 'POST')
        self.assertEqual(boto_span.data['http']['url'], f'{endpoint}:443/Invoke')
