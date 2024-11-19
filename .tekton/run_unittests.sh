#!/usr/bin/env bash
set -e

if [[ -z "${TEST_CONFIGURATION}" ]]; then
  echo "The TEST_CONFIGURATION environment variable is missing." >&2
  echo "This should have been provided by the Tekton Task or the developer" >&2
  exit 1
fi

if [[ -z "${PYTHON_VERSION}" ]]; then
  echo "The PYTHON_VERSION environment variable is missing." >&2
  echo "This is a built-in variable in the official python container images" >&2
  exit 2
fi

PYTHON_MINOR_VERSION="$(echo "${PYTHON_VERSION}" | cut -d'.' -f 2)"

case "${TEST_CONFIGURATION}" in
default)
  export REQUIREMENTS='requirements.txt'
  export TESTS=('tests') ;;
cassandra)
  export REQUIREMENTS='requirements-cassandra.txt'
  export TESTS=('tests/clients/test_cassandra-driver.py')
  export CASSANDRA_TEST='true' ;;
gevent_starlette)
  export REQUIREMENTS='requirements-gevent-starlette.txt'
  # TODO: uncomment once gevent instrumentation is done
  # export TESTS=('tests/frameworks/test_gevent.py' 'tests/frameworks/test_starlette.py')
  # export GEVENT_STARLETTE_TEST='true' ;;
  export TESTS=('tests/frameworks/test_starlette.py');;
aws)
  export REQUIREMENTS='requirements.txt'
  export TESTS=('tests_aws') ;;
*)
  echo "ERROR \$TEST_CONFIGURATION='${TEST_CONFIGURATION}' is unsupported " \
       "not in (default|cassandra|gevent_starlette)" >&2
  exit 3 ;;
esac

echo -n "Configuration is '${TEST_CONFIGURATION}' on ${PYTHON_VERSION} "
echo    "with dependencies in '${REQUIREMENTS}'"
ls -lah .

python -m venv /tmp/venv
# shellcheck disable=SC1091
source /tmp/venv/bin/activate
pip install --upgrade pip
pip install -e .
pip install -r "tests/${REQUIREMENTS}"

coverage run \
  --source=instana \
  --data-file=".coverage-${PYTHON_VERSION}-${TEST_CONFIGURATION}" \
  --module \
  pytest \
    --verbose --junitxml=test-results "${TESTS[@]}" # pytest options (not coverage options anymore)
