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
def run_init(fixtures_dir):

  def init_runner(**backend_config):
    tf = tftest.TerraformTest('apply', fixtures_dir)
    tf.setup(init_vars=backend_config)

  return init_runner


def test_simple_args(run_init):
  run_init(path='terraform-1.tfstate')


def test_spaced_args(run_init):
  run_init(path='terraform 1.tfstate')
