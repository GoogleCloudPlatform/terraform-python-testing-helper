# Terraform Test Helper

This simple helper facilitates testing Terraform modules from Python unit test. It does so by wrapping the Terraform executable, and exposing convenience methods to set up fixtures, execute terraform commands, and parse their output.

It allows for different types of tests: lightweight tests that only use Terraform init and plan to ensure code is syntactically correct, and the right number and type of resources should be created; or full-fledged tests that also run Terraform apply and output (destroying if needed), and can check created resources through outputs, state, and then running live tests (eg pinging an instance) against created resources.

This module is heavily inspired by two projects: [Terragrunt](https://github.com/gruntwork-io/terragrunt) for the lightweight approach to testing Terraform, and [python-terraform](https://github.com/beelit94/python-terraform) for wrapping the Terraform command in Python.

## Example Usage

TODO: describe usage
