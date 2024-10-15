# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019

try:
    from instana.log import logger
    from instana.singletons import agent

    import gunicorn
    from gunicorn.arbiter import Arbiter
    from gunicorn.config import Config
    from gunicorn.workers.sync import SyncWorker

    def pre_fork(config: Config, server: Arbiter, worker: SyncWorker) -> None:
        """This is our gunicorn hook to detect and act when worker processes are forked off."""
        logger.debug("Handling gunicorn fork...")
        agent.handle_fork()

    Config.pre_fork = pre_fork

    logger.debug("Gunicorn pre-fork hook applied")
except ImportError:
    logger.debug(
        "gunicorn hooks: decorators not available: likely not running under gunicorn"
    )
    pass
