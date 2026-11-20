# Python Test Helper for Terraform and OpenTofu

This simple helper facilitates testing Terraform and OpenTofu modules from Python unit tests by wrapping the `terraform` (or `tofu`) executable and exposing convenience methods to set up fixtures, execute commands, and parse their output.

It supports both lightweight tests that only run `init` and `plan` to ensure code is valid and creates the expected resources, and full end-to-end tests that run `apply`, `output`, and `destroy` against live environments or local state.

As an additional convenience, the module provides parsed wrappers around JSON plan output (via `terraform plan -out` and `terraform show -json`), module outputs (via `terraform output -json`), and pulled state (`terraform state pull`).

This module is inspired by [Terratest](https://github.com/gruntwork-io/terratest) for the lightweight approach to testing Terraform, and [python-terraform](https://github.com/beelit94/python-terraform) for wrapping the CLI in Python.

## Example Usage

The [`test`](https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/tree/master/test) folder contains examples of tests for both `plan` and `apply`, using synthetic JSON fixtures and minimal root modules. Extensive real-world usage can be found in the [Cloud Foundation Fabric](https://github.com/GoogleCloudPlatform/cloud-foundation-fabric) repository, for which this module was originally developed.

Using `TerraformTest` as a context manager ensures linked files and runtime artifacts (`.terraform/`, state files, and generated lockfiles) are cleaned up deterministically when the block exits:

```python
import pytest
import tftest


@pytest.fixture
def plan(fixtures_dir):
  with tftest.TerraformTest('plan', fixtures_dir) as tf:
    tf.setup(extra_files=['plan.auto.tfvars'])
    yield tf.plan(output=True)


def test_variables(plan):
  assert 'prefix' in plan.variables
  assert plan.variables['names'] == ['one', 'two']


def test_outputs(plan):
  assert sorted(plan.outputs['gcs_buckets'].keys()) == plan.variables['names']


def test_root_resource(plan):
  res = plan.resources['google_project_iam_member.test_root_resource']
  assert res['values']['project'] == plan.variables['project_id']


def test_modules(plan):
  mod = plan.modules['module.gcs-buckets']
  res = mod.resources['google_storage_bucket.buckets[0]']
  assert res['values']['location'] == plan.variables['gcs_location']
```

To inspect or reuse a binary plan file directly, pass `plan_out` to `plan()` and optionally pass `plan_file` to `apply()`:

```python
def test_saved_plan(fixtures_dir, tmp_path):
  plan_file = tmp_path / 'out.tfplan'
  with tftest.TerraformTest('apply', fixtures_dir) as tf:
    tf.setup()
    tf.plan(plan_out=plan_file, tf_vars={'names': ['one']})
    tf.apply(plan_file=plan_file)
    assert tf.output()['triggers'][0]['name'] == 'one'
    tf.destroy()
```

To run against OpenTofu instead of Terraform, pass `binary='tofu'` when instantiating `TerraformTest`.

## Compatibility

Version `2.0.0` requires Python `3.10` or newer, standardizes `tf.tfdir` as a `pathlib.Path` object, and removes the experimental method caching layer (`enable_cache` / `use_cache`). Terragrunt support was removed in `1.8.6`. Check [`CHANGELOG.md`](https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/blob/master/CHANGELOG.md) for full release history.

## Testing

Tests use `pytest` and have no runtime dependencies beyond a `terraform` or `tofu` binary (`pytest --tf-binary=tofu`). Development dependencies are listed in `DEV-REQUIREMENTS.txt`.

## Disclaimer

This is not an officially supported Google product.
