#!/usr/bin/env bash
set -x

POSITIONAL_ARGS=()
TESTS=("tests")

while [[ $# -gt 0 ]]; do
  case $1 in
    --aws)
      TESTS=("tests_aws")
      shift # past argument
      shift # past value
      ;;
    --default)
      TESTS=("tests")
      shift # past argument
      shift # past value
      ;;
    --all)
      TESTS=("tests tests_aws")
      shift # past argument
      shift # past value
      ;;
    --cov)
      COVERAGE=True
      shift # past argument
      shift # past value
      ;;
    -*|--*)
      echo "Unknown option 1" # save positional arg
      shift # past argument
      ;;
  esac
done

set -- "${POSITIONAL_ARGS[@]}" # restore positional parameters

if [ -z ${COVERAGE} ]; then
  pytest -vv "${TESTS[@]}"
else
  coverage run \
    --source=instana \
    --module pytest \
    --verbose \
    --junitxml=test-results \
    "${TESTS[@]}" # pytest options (not coverage options anymore)

  coverage report -m
  coverage html
fi