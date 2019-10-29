# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"Test the plan output wrapper classes."

import pytest
import tftest


@pytest.fixture
def plan_out(fixtures_dir):
  import json
  with open('%s/plan_output.json' % fixtures_dir) as fp:
    return tftest.TerraformPlanOutput(json.load(fp))


def test_output_attributes(plan_out):
  assert plan_out.format_version == "0.1"
  assert plan_out.terraform_version == "0.12.6"


def test_variables(plan_out):
  assert plan_out.variables['foo'] == 'bar'


def test_resource_changes(plan_out):
  address = 'module.resource-change.foo_resource.somefoo'
  change = plan_out.resource_changes[address]
  assert change['address'] == address
  assert change['change']['before'] is None


def test_output_changes(plan_out):
  change = plan_out.output_changes['spam']
  assert change['after'] == 'bar'


def test_configuration(plan_out):
  assert plan_out.configuration['provider_config']['google']['name'] == 'google'


def test_root_module(plan_out):
  mod = plan_out.root_module
  assert plan_out.modules == mod.child_modules
  assert plan_out.resources == mod.resources


def test_resources(plan_out):
  res = plan_out.resources['spam.somespam']
  assert res['address'] == 'spam.somespam'
  assert res['values']['spam-value'] == 'spam'


def test_modules(plan_out):
  mod = plan_out.modules['module.parent']
  assert mod['address'] == 'module.parent'
  res = mod.resources['foo.somefoo']
  assert res['address'] == 'module.parent.foo.somefoo'
  assert res['values']['foo-value'] == 'foo'


def test_child_modules(plan_out):
  mod = plan_out.modules['module.parent'].child_modules['module.child']
  assert mod.resources['eggs.someeggs']['values']['eggs-value'] == 'eggs'
