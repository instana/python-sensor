# Contributing to the Instana Python Sensor

Our project welcomes external contributions. If you have an itch, please feel
free to scratch it.

To contribute with code, please submit a [pull request].

A good way to familiarize yourself with the codebase and contribution process is
to look for and tackle low-hanging fruit in the [issue tracker].

<!--Before embarking on a more ambitious contribution, please quickly [get in touch](#communication) with us.-->

**Note: We appreciate your effort, and want to avoid a situation where a 
contribution requires extensive rework (by you or by us), sits in backlog for a 
long time, or cannot be accepted at all!**

## Proposing new features

If you would like to implement a new feature, please [raise an issue] before 
sending a pull request so the feature can be discussed. This is to avoid
you wasting your valuable time working on a feature that the project developers
are not interested in accepting into the code base.

Do not forget to add the labels `enhancement` or `feature` to your issue.

## Fixing bugs

If you would like to fix a bug, please [raise an issue] before sending a
pull request so it can be tracked.

Do not forget to add the label `bug` to your issue.

## Merge approval

The project maintainers use `LGTM` (Looks Good To Me) in comments on the code
review to indicate acceptance. A pull request requires LGTMs from, at least, one
of the maintainers of each component affected.

For a list of the maintainers, see the [MAINTAINERS.md](MAINTAINERS.md) page.

## Legal

### Copyright

Each source file must include a Copyright header to IBM. When submitting a pull 
request for review which contains new source code files, the developer must 
include the following content in the beginning of the file.

```
# (c) Copyright IBM Corp. <YEAR>

```

### Sign your work

We have tried to make it as easy as possible to make contributions. This
applies to how we handle the legal aspects of contribution. 

We use the same approach - the [Developer's Certificate of Origin 1.1 (DCO)] - that the [Linux® Kernel community] uses to manage code contributions.

We simply ask that when submitting a pull request for review, the developer
must include a sign-off statement in the commit message.

Here is an example Signed-off-by line, which indicates that the
submitter accepts the DCO:

```
Signed-off-by: John Doe <john.doe@example.com>
```

You can include this automatically when you commit a change to your
local git repository using the following command:

```shell
git commit -s
```

<!--
## Communication
**FIXME** Please feel free to connect with us on our [Slack channel](link).

## Setup
**FIXME** Please add any special setup instructions for your project to help the developer
become productive quickly.

## Testing
**FIXME** Please provide information that helps the developer test any changes they make
before submitting.

## Coding style guidelines
**FIXME** Optional, but recommended: please share any specific style guidelines you might
have for your project.
-->

<!-- Reference links -->

[pull request]: https://github.com/instana/python-sensor/pulls "Python Sensor Pull Requests"
[issue tracker]: https://github.com/instana/python-sensor/issues "Python Sensor Issue Tracker"
[raise an issue]: https://github.com/instana/python-sensor/issues "Raise an issue"
[Developer's Certificate of Origin 1.1 (DCO)]: https://github.com/hyperledger/fabric/blob/master/docs/source/DCO1.1.txt "DCO1.1"
[Linux® Kernel community]: https://elinux.org/Developer_Certificate_Of_Origin  "Linux Kernel DCO"
