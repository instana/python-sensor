from basictracer.span import BasicSpan


class InstanaSpan(BasicSpan):
    stack = None

    def finish(self, finish_time=None):
        super(InstanaSpan, self).finish(finish_time)

    def log_exception(self, e):
        if hasattr(e, '__str__'):
            self.log_kv({'message': str(e)})
        elif hasattr(e, 'message') and e.message is not None:
            self.log_kv({'message': e.message})

        self.set_tag("error", True)
        ec = self.tags.get('ec', 0)
        self.set_tag("ec", ec+1)
