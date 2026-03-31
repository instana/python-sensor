# Release Steps

## PyPI and GitHub

The project has a GitHub Action that publishes new versions of the Instana Python Tracer to GitHub and [PyPI] using the [Trusted Publisher Management System].

Only the GitHub `@instana/python-eng` team members are allowed to publish a new version of the Instana Python Tracer.

## AWS Lambda Layer

On top of the common Instana Python Tracer release, the GitHub `@instana/python-eng` team members also publish versions of the Instana Python Tracer AWS Lambda layer.

These releases are available on the GitHub Releases page.

<!-- Reference links -->

[PyPI]: https://pypi.org/project/instana/ "Instana Python Tracer on PyPI"
[Trusted Publisher Management System]: https://docs.pypi.org/trusted-publishers/ "Trusted Publisher Management System"
