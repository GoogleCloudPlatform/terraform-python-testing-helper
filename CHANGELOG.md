# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.1]

## Changed

- fix links and typos in README

## [1.0.0]

### Added

- support child modules in plan output
- added support for `__contains__` in dict wrapper classes
- add simple examples for plan and apply as fixtures

### Changed

- refactor plan output attributes (breaking change)
- refactor state wrapper (breaking change)
- refactor tests

### Removed

- refactor the module interface (breaking change)
  - remove the ability to run commands implicitly in `setup`
  - remove the `run_commands` method
  - remove the `teardown` method
  - unify the `plan` and `plan_out` methods

[Unreleased]: https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/compare/v4.0.0...HEAD
[1.0.1]: https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/compare/v0.6.2...v1.0.0
