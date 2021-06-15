parent_span = None


def get_parent_span():
    """
    Retrieve the globally configured parent_span
    @return: parent_span
    """
    global parent_span
    return parent_span


def set_parent_span(new_parent_span):
    """
    Set the global parent_span for the Instana package.
    @param new_parent_span: The new parent_span to replace the singleton
    @return: None
    """
    global parent_span
    parent_span = new_parent_span
