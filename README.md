# Terraform Test Helper

This simple helper facilitates testing Terraform modules from Python unit test. It does so by wrapping the Terraform executable, and exposing convenience methods to set up fixtures, execute terraform commands, and parse their output.

It allows for different types of tests: lightweight tests that only use Terraform init and plan to ensure code is syntactically correct, and the right number and type of resources should be created; full-fledged tests that also run Terraform apply and output (and destroy if needed), and can check created resources through outputs, state, and using live tests (eg pinging an instance).

## Example Usage

TODO: describe usage
