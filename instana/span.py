from basictracer.span import BasicSpan
from .log import logger


class InstanaSpan(BasicSpan):
    stack = None

    def finish(self, finish_time=None):
        super(InstanaSpan, self).finish(finish_time)

    def log_exception(self, e):
        try:
            logger.debug("Logging error for span %s" % self.operation_name)
            message = ""

            self.set_tag("error", True)
            ec = self.tags.get('ec', 0)
            self.set_tag("ec", ec+1)

            if hasattr(e, '__str__'):
                message = str(e)
            elif hasattr(e, 'message') and e.message is not None:
                message = e.message

            if self.operation_name in ['rpc-server', 'rpc-client']:
                self.set_tag('rpc.error', message)
            elif self.operation_name == "postgres":
                self.set_tag('pg.error', message)
            elif self.operation_name == "mysql":
                self.set_tag('mysql.error', message)
            else:
                self.log_kv({'message': message})
        except Exception:
            logger.debug("span.log_exception", exc_info=True)
            raise

    def collect_logs(self):
        """
            Collect up log data and feed it to the Instana brain.

        :param span: The span to search for logs in
        :return: Logs ready for consumption by the Instana brain.
        """
        logs = {}
        for log in self.logs:
            ts = int(round(log.timestamp * 1000))
            if ts not in logs:
                logs[ts] = {}

            if 'message' in log.key_values:
                logs[ts]['message'] = log.key_values['message']
            if 'event' in log.key_values:
                logs[ts]['event'] = log.key_values['event']
            if 'parameters' in log.key_values:
                logs[ts]['parameters'] = log.key_values['parameters']

        return logs


