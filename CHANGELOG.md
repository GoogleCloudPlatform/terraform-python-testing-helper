# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.5.6]

- improve Windows support [#28]

## [1.5.6]

- retag 1.5.5 as 1.5.6

## [1.5.5]

- do not fail when `resource_changes` key is not present in output
- this release has been skippe don pypi

## [1.5.4]

- fix quoting in backend config args

## [1.5.3]

- allow customizing environment variables

## [1.5.2]

- fix errors when plan has no variables

## [1.5.1]

- add support for `-var-file` flag

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

[Unreleased]: https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/compare/v1.5.7...HEAD
[1.5.7]: https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/compare/v1.5.6...v1.5.7
[1.5.6]: https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/compare/v1.5.5...v1.5.6
[1.5.5]: https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/compare/v1.5.4...v1.5.5
[1.5.4]: https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/compare/v1.5.3...v1.5.4
[1.5.3]: https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/compare/v1.5.2...v1.5.3
[1.5.2]: https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/compare/v1.5.1...v1.5.2
[1.5.1]: https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/compare/v1.5.0...v1.5.1
[1.5.0]: https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/compare/v1.4.1...v1.5.0
[1.4.1]: https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/compare/v1.3.0...v1.4.1
[1.3.0]: https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/compare/v0.6.2...v1.0.0
