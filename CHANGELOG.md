# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.5.0]

- add an option to allow the use of targeted resources using the `-target` flag

## [1.4.1]

### Fixed

- fix `KeyError` on plan output when no Terraform outputs have been defined (cf [#9] and [#10])

## [1.3.0]

### Added

- add an option to allow leaving `.terraform` and `terraform.state` in place on exit

## [1.2.0]

### Added

- proxy raw dict iter in `TerraformValueDict`

## [1.1.0]

### Added

- proxy raw dict methods in `TerraformValueDict`

## [1.0.1]

### Changed

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

[Unreleased]: https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/compare/v1.5.0...HEAD
[1.5.0]: https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/compare/v1.4.1...v1.5.0
[1.4.1]: https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/compare/v1.3.0...v1.4.1
[1.3.0]: https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/compare/v0.6.2...v1.0.0
