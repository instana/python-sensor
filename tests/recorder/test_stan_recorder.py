import sys
from multiprocessing import Queue
from unittest import TestCase
from unittest.mock import NonCallableMagicMock, PropertyMock

import pytest

from instana.recorder import StanRecorder
from instana.util.runtime import get_runtime_env_info


@pytest.mark.skipif(
    sys.platform == "darwin" or get_runtime_env_info()[0] == "s390x",
    reason="Avoiding NotImplementedError when calling multiprocessing.Queue.qsize()",
)
class TestStanRecorderTC(TestCase):
    def setUp(self):
        mock_agent = NonCallableMagicMock()
        mock_collector = NonCallableMagicMock(span_queue=Queue())
        mock_agent.collector = mock_collector
        self.recorder = StanRecorder(agent=mock_agent)
        self.mock_suppressed_span = NonCallableMagicMock()
        self.mock_suppressed_span.context = NonCallableMagicMock()
        self.mock_suppressed_property = PropertyMock(return_value=True)
        type(
            self.mock_suppressed_span.context
        ).suppression = self.mock_suppressed_property

    def test_record_span_with_suppression(self):
        # Ensure that the queue is empty
        self.assertEqual(self.recorder.queue_size(), 0)
        self.recorder.record_span(self.mock_suppressed_span)
        # Ensure that even after adding a suppressed span
        # the queue remains empty
        self.assertEqual(self.recorder.queue_size(), 0)
        # Ensure that the no recorded spans can be retrieved
        self.assertEqual(self.recorder.queued_spans(), [])

        # Make sure that the success so far has indeed resulted after a getitem
        # call to the 'suppression' property of the mock span context
        self.mock_suppressed_property.assert_called_once_with()
