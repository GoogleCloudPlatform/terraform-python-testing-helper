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

"""Example plan test with no injected files."""

import os
import re


import tftest


TF = tftest.TerraformTest(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'foo'))


def setup():
  TF.setup(command='plan')


def test_resources():
  """Test that plan contains all expected resources."""
  values = re.findall(r'(?m)^\s*\+\s+(null_resource\S+)\s*^', TF.setup_output)
  assert values == ['null_resource.foo_resource'], values


def test_attributes():
  """Test that resources have the correct attributes."""
  values = re.findall(r'(?m)^\s*triggers\.foo:\s*"(\S+)"\s*^', TF.setup_output)
  assert values == ['foo'], values


def test_attributes_tfvars():
  """Test that a different variable generates different attributes."""
  plan = TF.plan(tf_vars={'foo_var': '["foo", "spam"]'})
  values = re.findall(r'(?m)^\s*triggers\.foo:\s*"(\S+)"\s*^', plan)
  assert values == ['foo', 'spam'], values
