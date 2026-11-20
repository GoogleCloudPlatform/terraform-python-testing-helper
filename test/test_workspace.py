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
"Test init and plan using an actual example."

from pathlib import Path
import pytest
import tftest


@pytest.fixture(scope='module')
def terraform_test(fixtures_dir):
  with tftest.TerraformTest('plan_no_variables', fixtures_dir) as tf:
    tf.setup()
    tf_dir = tf.tfdir
    yield tf
  assert not (Path(tf_dir) / 'terraform.tfstate.d').exists()
  assert not (Path(tf_dir) / '.terraform.lock.hcl').exists()


def test_new_workspace(terraform_test):
  tf_output = terraform_test.workspace(name="workspace_test")
  assert 'Created and switched to workspace "workspace_test"' in tf_output


def test_select_workspace(terraform_test):
  tf_output = terraform_test.workspace(name="workspace_test")
  tf_output = terraform_test.workspace(name="default")
  assert 'Switched to workspace "default"' in tf_output


def test_setup_with_workspace(terraform_test):
  tf_output = terraform_test.setup(workspace_name="setup_workspace")
  assert 'Created and switched to workspace "setup_workspace"' in tf_output
