from basictracer.span import BasicSpan
from .log import logger


class InstanaSpan(BasicSpan):
    stack = None

    def finish(self, finish_time=None):
        super(InstanaSpan, self).finish(finish_time)

    def log_exception(self, e):
        try:
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

            self.log_kv({'message': message})

        except Exception:
            logger.debug("span.log_exception", exc_info=True)
            raise

