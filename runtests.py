import sys
import nose
from distutils.version import LooseVersion

command_line = ['-v']

if (LooseVersion(sys.version) < LooseVersion('3.4')):
    command_line.extend(['-e', 'asynqp'])

print("Nose arguments: %s" % command_line)
result = nose.run(argv=command_line)

if result is True:
    exit(0)
else:
    exit(-1)