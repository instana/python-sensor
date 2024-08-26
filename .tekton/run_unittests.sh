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
  case "${PYTHON_MINOR_VERSION}" in
    10 | 11)
      export REQUIREMENTS='requirements-310.txt' ;;
    12)
      export REQUIREMENTS='requirements-312.txt' ;;
    13)
      export REQUIREMENTS='requirements-313.txt' ;;
    *)
      export REQUIREMENTS='requirements.txt' ;;
  esac
  export TESTS=('tests') ;;
cassandra)
  export REQUIREMENTS='requirements-cassandra.txt'
  export TESTS=('tests/clients/test_cassandra-driver.py')
  export CASSANDRA_TEST='true' ;;
couchbase)
  export REQUIREMENTS='requirements-couchbase.txt'
  export TESTS=('tests/clients/test_couchbase.py')
  export COUCHBASE_TEST='true' ;;
gevent_starlette)
  export REQUIREMENTS='requirements-gevent-starlette.txt'
  export TESTS=('tests/frameworks/test_gevent.py' 'tests/frameworks/test_starlette.py')
  export GEVENT_STARLETTE_TEST='true' ;;
googlecloud)
  export REQUIREMENTS='requirements-googlecloud.txt'
  export TESTS=('tests/clients/test_google-cloud-storage.py' 'tests/clients/test_google-cloud-pubsub.py')
  export GOOGLE_CLOUD_TEST='true' ;;  
*)
  echo "ERROR \$TEST_CONFIGURATION='${TEST_CONFIGURATION}' is unsupported " \
       "not in (default|cassandra|couchbase|gevent_starlette|googlecloud)" >&2
  exit 3 ;;
esac

echo -n "Configuration is '${TEST_CONFIGURATION}' on ${PYTHON_VERSION} "
echo    "with dependencies in '${REQUIREMENTS}'"
export INSTANA_TEST='true'
ls -lah .
if [[ -n "${COUCHBASE_TEST}" ]]; then
  echo "Install Couchbase Dependencies"
  # Even if we use bookworm for running this, we need to add the bionic repo
  # See: https://forums.couchbase.com/
  # t/installing-libcouchbase-dev-on-ubuntu-20-focal-fossa/25955/3
  wget -O - http://packages.couchbase.com/ubuntu/couchbase.key | apt-key add -
  echo "deb http://packages.couchbase.com/ubuntu bionic bionic/main" \
       > /etc/apt/sources.list.d/couchbase.list
  apt update
  apt install libcouchbase-dev -y
fi

python -m venv /tmp/venv
# shellcheck disable=SC1091
source /tmp/venv/bin/activate
pip install --upgrade pip "$([[ -n ${COUCHBASE_TEST} ]] && echo wheel || echo pip)"
pip install -e .
pip install -r "tests/${REQUIREMENTS}"

coverage run \
  --source=instana \
  --data-file=".coverage-${PYTHON_VERSION}-${TEST_CONFIGURATION}" \
  --module \
  pytest \
    --verbose --junitxml=test-results "${TESTS[@]}" # pytest options (not coverage options anymore)
