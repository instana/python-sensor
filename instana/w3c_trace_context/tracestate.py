# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021


class Tracestate:
    MAX_NUMBER_OF_LIST_MEMBERS = 32
    REMOVE_ENTRIES_LARGER_THAN = 128

    def __init__(self):
        self.tracestate = None

    @property
    def tracestate(self):
        return self._tracestate

    @tracestate.setter
    def tracestate(self, value):
        self._tracestate = value

    def extract_tracestate(self, headers):
        self.tracestate = headers.get('tracestate', None)
        if self.tracestate is None:
            return None

        return self.tracestate

    def update_tracestate(self, in_trace_id, in_span_id):
        """
        Method to update the tracestate property with the instana trace_id and span_id

        :param in_trace_id: instana trace_id
        :param in_span_id: instana parent_id
        :return:
        """

        span_id = in_span_id.zfill(16)  # if span_id is shorter than 16 characters we prepend zeros
        instana_tracestate = "in={};{}".format(in_trace_id, span_id)
        # tracestate can contain a max of 32 list members, if it contains up to 31
        # we can safely add the instana one without the need to truncate anything
        if len(self.tracestate.split(",")) <= self.MAX_NUMBER_OF_LIST_MEMBERS - 1:
            self.tracestate = "{},{}".format(instana_tracestate, self.tracestate)
        else:
            list_members = self.tracestate.split(",")
            list_members_to_remove = len(list_members) - self.MAX_NUMBER_OF_LIST_MEMBERS + 1
            # Number 1 priority members to be removed are the ones larger than 128 characters
            for i, m in reversed(list(enumerate(list_members))):
                if len(m) > self.REMOVE_ENTRIES_LARGER_THAN:
                    list_members.pop(i)
                    list_members_to_remove -= 1
                if list_members_to_remove == 0:
                    break
            # if there are still more than 31 list members remaining, we remove as many members
            # from the end as necessary to remain just 31 list members
            while list_members_to_remove > 0:
                list_members.pop()
                list_members_to_remove -= 1
            # update the tracestate containing just 31 list members
            self.tracestate = ",".join(list_members)
            # adding instana as first list member, total of 32 list members
            self.tracestate = "{},{}".format(instana_tracestate, self.tracestate)
