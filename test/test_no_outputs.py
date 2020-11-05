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

"Test plan withno outputs."

import pytest
import tftest


@pytest.fixture
def plan(fixtures_dir):
  tf = tftest.TerraformTest('no_outputs', fixtures_dir)
  tf.setup(extra_files=['plan.auto.tfvars'])
  return tf.plan(output=True)


def test_variables(plan):
  assert 'prefix' in plan.variables
  assert plan.variables['name'] == 'test'


def test_outputs(plan):
  assert plan.outputs._raw == {}


def test_root_resource(plan):
  res = plan.resources['google_project_iam_member.test_root_resource']
  assert res['values']['project'] == plan.variables['project_id']


def test_modules(plan):
  mod = plan.modules['module.service-account']
  assert set(mod.resources.keys()) == set(
      ['google_service_account.service_account'])
