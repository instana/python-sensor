# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019

"""
The uwsgi and uwsgidecorators packages are added automatically to the Python environment
when running under uWSGI.  Here we attempt to detect the presence of these packages and
then use the appropriate hooks.
"""

try:
    from instana.log import logger
    from instana.singletons import agent

    import uwsgi

    logger.debug(
        f"uWSGI options: {uwsgi.opt}",
    )

    opt_master = uwsgi.opt.get("master", False)
    opt_lazy_apps = uwsgi.opt.get("lazy-apps", False)

    if not uwsgi.opt.get("enable-threads", False) and not uwsgi.opt.get(
        "gevent", False
    ):
        logger.warning(
            "Required: Neither uWSGI threads or gevent is enabled. "
            + "Please enable by using the uWSGI --enable-threads or --gevent option."
        )

    if opt_master and not opt_lazy_apps:
        # --master is supplied in uWSGI options (otherwise uwsgidecorators package won't be available)
        # When --lazy-apps is True, this postfork hook isn't needed
        import uwsgidecorators

        @uwsgidecorators.postfork
        def uwsgi_handle_fork() -> None:
            """This is our uWSGI hook to detect and act when worker processes are forked off."""
            logger.debug("Handling uWSGI fork...")
            agent.handle_fork()

        logger.debug("Applied uWSGI hooks")
    else:
        logger.debug(
            f"uWSGI --master={opt_master} --lazy-apps={opt_lazy_apps}: postfork hooks not applied"
        )
except ImportError:
    logger.debug(
        "uwsgi hooks: decorators not available: likely not running under uWSGI"
    )
    pass
