# Python Test Helper for Terraform

This simple helper facilitates testing Terraform modules from Python unit test. It does so by wrapping the Terraform executable, and exposing convenience methods to set up fixtures, execute terraform commands, and parse their output.

It allows for different types of tests: lightweight tests that only use Terraform init and plan to ensure code is syntactically correct, and the right number and type of resources should be created; or full-fledged tests that also run Terraform apply and output (destroying if needed), and can check created resources through outputs, state, and then running live tests (eg pinging an instance) against created resources.

This module is heavily inspired by two projects: [Terragrunt](https://github.com/gruntwork-io/terragrunt) for the lightweight approach to testing Terraform, and [python-terraform](https://github.com/beelit94/python-terraform) for wrapping the Terraform command in Python.

## Example Usage

The `example` folder contains one example for each test style. This is a snippet from the plan-based tests:

```python
TF = tftest.TerraformTest(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'foo'))

def setup():
  TF.setup(command='plan')

def test_resources():
  """Test that plan contains all expected resources."""
  values = re.findall(r'(?m)^\s*\+\s+(null_resource\S+)\s*^', TF.setup_output)
  assert values == ['null_resource.foo_resource'], values
```

And from the apply-based tests:

```python
TF = tftest.TerraformTest(os.path.join(ROOT, 'foo'))

def setup():
  TF.setup(command='output', destroy=True)

def teardown():
  TF.teardown()

def test_output():
  """Test that apply creates the correct resources and outputs are correct."""
  assert TF.setup_output['foos'] == [
      {'foo': 'foo', 'index': '0'}], TF.setup_output['foos']

def test_state():
  """Test that state has the correct resources and attributes."""
  resources = TF.state_pull().modules['root'].resources
  assert resources['null_resource.foo_resource'].attributes['triggers.%'] == '2'
```

## Testing

The simple tests in the [tests](tests/) folder require Python 3.x and can be run with `nosetests3` or `pytest`.

## Disclaimer

This is not an officially supported Google product.