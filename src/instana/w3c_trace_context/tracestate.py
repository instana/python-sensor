# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from ..log import logger


class InstanaAncestor:
    def __init__(self, trace_id, parent_id):
        self.t = trace_id
        self.p = parent_id


class Tracestate:
    MAX_NUMBER_OF_LIST_MEMBERS = 32
    REMOVE_ENTRIES_LARGER_THAN = 128

    @staticmethod
    def get_instana_ancestor(tracestate):
        """
        Constructs the instana ancestor object and returns it
        :param tracestate: the original tracestate value
        :return: instana ancestor instance
        """
        try:
            in_list_member = tracestate.strip().split("in=")[1].split(",")[0]

            ia = InstanaAncestor(trace_id=in_list_member.split(";")[0],
                                 parent_id=in_list_member.split(";")[1])
            return ia

        except Exception:
            logger.debug("extract instana ancestor error:", exc_info=True)
        return None

    def update_tracestate(self, tracestate, in_trace_id, in_span_id):
        """
        Method to update the tracestate property with the instana trace_id and span_id

        :param tracestate: original tracestate header
        :param in_trace_id: instana trace_id
        :param in_span_id: instana parent_id
        :return: tracestate updated
        """
        try:
            span_id = in_span_id.zfill(16)  # if span_id is shorter than 16 characters we prepend zeros
            instana_tracestate = "in={};{}".format(in_trace_id, span_id)
            if tracestate is None or tracestate == "":
                tracestate = instana_tracestate
            else:
                # remove the existing in= entry
                if "in=" in tracestate:
                    splitted = tracestate.split("in=")
                    before_in = splitted[0]
                    after_in = splitted[1].split(",")[1:]
                    tracestate = '{}{}'.format(before_in, ",".join(after_in))
                # tracestate can contain a max of 32 list members, if it contains up to 31
                # we can safely add the instana one without the need to truncate anything
                if len(tracestate.split(",")) <= self.MAX_NUMBER_OF_LIST_MEMBERS - 1:
                    tracestate = "{},{}".format(instana_tracestate, tracestate)
                else:
                    list_members = tracestate.split(",")
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
                    tracestate = ",".join(list_members)
                    # adding instana as first list member, total of 32 list members
                    tracestate = "{},{}".format(instana_tracestate, tracestate)
        except Exception:
            logger.debug("Something went wrong while updating tracestate: {}:".format(tracestate), exc_info=True)

        return tracestate
