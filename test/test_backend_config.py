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
"Test local backend configuration arguments."

from pathlib import Path
import shutil
import pytest
import tftest


@pytest.fixture
def run_init(fixtures_dir, tmp_path):
  mod_dir = tmp_path / 'backend_config'
  shutil.copytree(Path(fixtures_dir) / 'backend_config', mod_dir)

  def init_runner(**backend_config):
    with tftest.TerraformTest(mod_dir) as tf:
      tf.setup(init_vars=backend_config)
      tf.apply()
      assert (mod_dir / backend_config['path']).is_file()

  return init_runner


def test_simple_args(run_init):
  run_init(path='terraform-1.tfstate')


def test_spaced_args(run_init):
  run_init(path='terraform 1.tfstate')
