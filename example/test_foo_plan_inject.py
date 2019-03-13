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


ROOT = os.path.dirname(os.path.abspath(__file__))
TF = tftest.TerraformTest(os.path.join(ROOT, 'foo'))


def setup():
  TF.setup(command='plan', extra_files=[
           os.path.join(ROOT, 'terraform.tfvars')])


def test_resources():
  """Test that plan contains all expected resources."""
  values = re.findall(r'(?m)^\s*\+\s+(null_resource\S+)\s*^', TF.setup_output)
  assert values == ['null_resource.foo_resource[0]',
                    'null_resource.foo_resource[1]'], values


def test_attributes():
  """Test that resources have the correct attributes."""
  values = re.findall(r'(?m)^\s*triggers\.foo:\s*"(\S+)"\s*^', TF.setup_output)
  assert values == ['spam', 'eggs'], values


def test_apply():
  """Test that apply creates the correct resources, don't destroy."""
  return
  # extra_files = _map_files(
  #     _TF_MOD, ['backend.tf', 'provider.tf', 'terraform.tfvars'])
  # tf_vars = {'names': '["account-one", "account-two"]'}
  # tf = tftest.TerraformTest(_TF_MOD)
  # tf.setup(extra_files=extra_files, tf_vars=tf_vars,
  #          plugin_dir=os.environ.get('PLUGIN_DIR'), destroy=False)
  # resources = tf.state_pull().modules['root'].resources
  # assert_equals(sorted(list(resources.keys())), [
  #     'data.template_file.keys.0',
  #     'data.template_file.keys.1',
  #     'google_project_iam_binding.project-roles',
  #     'google_service_account.service_accounts.0',
  #     'google_service_account.service_accounts.1'
  # ])
