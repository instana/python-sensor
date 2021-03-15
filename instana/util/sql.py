# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import re

def sql_sanitizer(sql):
    """
    Removes values from valid SQL statements and returns a stripped version.

    :param sql: The SQL statement to be sanitized
    :return: String - A sanitized SQL statement without values.
    """
    return regexp_sql_values.sub('?', sql)


# Used by sql_sanitizer
regexp_sql_values = re.compile(r"('[\s\S][^']*'|\d*\.\d+|\d+|NULL)")