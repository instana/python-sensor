import os
import sys
import nose
from distutils.version import LooseVersion

os.environ['INSTANA_TEST'] = "true"
command_line = [__file__, '--verbose']

# Cassandra and gevent tests are run in dedicated jobs on CircleCI and will
# be run explicitly.  (So always exclude them here)
command_line.extend(['-e', 'cassandra', '-e', 'gevent'])

if LooseVersion(sys.version) < LooseVersion('3.5.3'):
    command_line.extend(['-e', 'asynqp', '-e', 'aiohttp',
                         '-e', 'async', '-e', 'tornado',
                         '-e', 'grpcio'])

if LooseVersion(sys.version) >= LooseVersion('3.7.0'):
    command_line.extend(['-e', 'sudsjurko'])

command_line.extend(sys.argv[1:])

print("Nose arguments: %s" % command_line)
result = nose.main(argv=command_line)

exit(result)
