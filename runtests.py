import sys
import nose
from distutils.version import LooseVersion

args = ['nosetests', '-v']

if (LooseVersion(sys.version) <= LooseVersion('3.5')):
    args.extend(['-e', 'asynqp'])

result = nose.run(argv=args)
