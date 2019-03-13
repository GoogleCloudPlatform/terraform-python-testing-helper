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

"""Example apply test with local state."""

import os
import re


import tftest


ROOT = os.path.dirname(os.path.abspath(__file__))
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
  assert list(resources.keys()) == [
      'null_resource.foo_resource'], resources.keys()
  assert resources['null_resource.foo_resource'].attributes['triggers.%'] == '2'
