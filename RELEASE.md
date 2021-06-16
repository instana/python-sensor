# Release Steps

## PyPI

> **NOTE**: _To release a new Instana package, you must be a project member of the [Instana package project on Pypi](https://pypi.org/project/instana/). Contact the relevant internal team to be added._

> _These scripts assumes that you have the AWS CLI and Github CLI installed and credentials already configured._


1. Before releasing, assure that [tests have passed](https://circleci.com/gh/instana/workflows/python-sensor) and that the package has also been manually validated in various stacks.
2. `git checkout master && git pull --rebase && pip install -U twine`
3. Bump the package version in `instana/version.py`. `git` commit & push the version change a new branch and get it merged to master
4. Create a [draft Release on Github](https://github.com/instana/python-sensor/releases) using [./bin/create_general_release.py <version>](https://github.com/instana/python-sensor/blob/master/bin/create_general_release.py)
5. Run `python setup.py sdist bdist_wheel` to create the packages file in `./dist/`
6. Upload the package to Pypi with twine: `twine upload dist/instana-<version>*`
7. Validate the new release on https://pypi.org/project/instana/
8. Update Python documentation with latest changes: https://docs.instana.io/ecosystem/python/
9. Publish the draft release on [Github](https://github.com/instana/python-sensor/releases)

## AWS Lambda Layer

To release a new AWS Lambda layer, see `bin/aws-lambda/build_and_publish_lambda_layer.py`.

Upload layers to all AWS zones

```./bin/aws-lambda/build_and_publish_lambda_layer.py [-dev|-prod]```

This will give you a tag version in the console as: `Uploaded version is XY`

Finally, create lambda release on Github with this tag version

```./bin/create_lambda_release.py <tag_version>```

> _Post release, remember to update documentation and the Instana UI._
