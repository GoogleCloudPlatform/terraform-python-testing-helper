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

"Test the Terraform state wrapper class."

import pytest
import tftest


@pytest.fixture
def state(fixtures_dir):
  import json
  with open('%s/state.json' % fixtures_dir) as fp:
    return tftest.TerraformState(json.load(fp))


def test_attributes(state):
  assert state.version == 4
  assert state.terraform_version == '0.12.10'


def test_outputs(state):
  assert state.outputs['foo'] == 'foo-value'


def test_resources(state):
  res = state.resources['module.vpc-remote.google_compute_network.network']
  assert res['mode'] == 'managed'
  assert res['instances'][0]['attributes']['name'] == 'remote'
