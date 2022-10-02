# Python Test Helper for Terraform

This simple helper facilitates testing Terraform modules from Python unit tests, by wrapping the Terraform executable and exposing convenience methods to set up fixtures, execute Terraform commands, and parse their output.

It allows for different types of tests: lightweight tests that only use Terraform `init` and `plan` to ensure code is syntactically correct and the right number and type of resources should be created, or full-fledged tests that run the full `apply`/`output`/`destroy` cycle, and can then be used to test the actual created resources, or the state file.

As an additional convenience, the module also provides an easy way to request and access the plan output (via `terraform plan -out` and `terraform show`) and the outputs (via `terraform output -json`), and return them wrapped in simple classes that streamline accessing their attributes.

This module is heavily inspired by two projects: [Terratest](https://github.com/gruntwork-io/terratest) for the lightweight approach to testing Terraform, and [python-terraform](https://github.com/beelit94/python-terraform) for wrapping the Terraform command in Python.

## Example Usage

The [`test`](https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/tree/master/test) folder contains simple examples on how to write tests for both `plan` and `apply`, using either synthetic fixtures (simple representations of the plan output and output files), or minimal root modules. More examples can be found in the [Cloud Foundation Fabric](https://github.com/terraform-google-modules/cloud-foundation-fabric) repository, for which this module was developed.

This is a test that uses plan output on an actual module:

```hcl
import pytest
import tftest


@pytest.fixture
def plan(fixtures_dir):
  tf = tftest.TerraformTest('plan', fixtures_dir)
  tf.setup(extra_files=['plan.auto.tfvars'])
  return tf.plan(output=True)


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

## Terragrunt support

Support for Terragrunt actually follows the same principle of the thin `TerraformTest` wrapper.

Please see the following example for how to use it:

```python
import pytest
import tftest


@pytest.fixture
def run_all_apply_out(fixtures_dir):
  # notice for run-all, you need to specify when TerragruntTest is constructed
  tg = tftest.TerragruntTest('tg_apply_all', fixtures_dir, tg_run_all=True)
  # the rest is very similar to how you use TerraformTest
  tg.setup()
  # to use --terragrunt-<option>, pass in tg_<option in snake case>
  tg.apply(output=False, tg_non_interactive=True)
  yield tg.output()
  tg.destroy(auto_approve=True, tg_non_interactive=True)

  
def test_run_all_apply(run_all_apply_out):
    triggers = [o["triggers"] for o in run_all_apply_out]
    assert [{'name': 'foo', 'template': 'sample template foo'}] in triggers
    assert [{'name': 'bar', 'template': 'sample template bar'}] in triggers
    assert [{'name': 'one', 'template': 'sample template one'},
            {'name': 'two', 'template': 'sample template two'}] in triggers
    assert len(run_all_apply_out) == 3
```

## Caching

The `TerraformTest` `setup`, `init`, `plan`, `apply`, `output` and `destroy` methods have the ability to cache it's associate output to a local `.tftest-cache` directory. For subsequent calls of the method, the cached value can be returned instead of calling the actual underlying `terraform` command. Using the cache value can be significantly faster than running the Terraform command again especially if the command is time-intensive.

To determine if the cache should be used, first a hash value is generated using the current `TerraformTest` instance `__init__` and calling method arguments. The hash value is compared to the hash value of the cached instance's associated arguments. If the hash is the same then the cache is used, otherwise the method is executed.

The benefits of the caching feature include:
- Faster setup time for testing terraform modules that don't change between testing sessions
- Writing tests without worrying about errors within their test code resulting in the Terraform setup logic to run again

Please see the following example for how to use it:

```python
import pytest
import tftest


@pytest.fixture
def output(fixtures_dir):
  tf = tftest.TerraformTest('apply', fixtures_dir, enable_cache=True)
  tf.setup(use_cache=True)
  tf.apply(use_cache=True)
  yield tf.output(use_cache=True)
  tf.destroy(use_cache=True, **{"auto_approve": True})


def test_apply(output):
  value = output['triggers']
  assert len(value) == 2
  assert list(value[0].keys()) == ['name', 'template']
  assert value[0]['name'] == 'one'

```



## Compatibility

Starting from version `1.0.0` Terraform `0.12` is required, and tests written with previous versions of this module are incompatible. Check the [`CHANGELOG.md`](https://github.com/GoogleCloudPlatform/terraform-python-testing-helper/blob/master/CHANGELOG.md) file for details on what's changed.

## Testing

Tests use the `pytest` framework and have no other dependency except on the Terraform binary. The version used during development is in the `DEV-REQUIREMENTS.txt` file.

## Disclaimer

This is not an officially supported Google product.
