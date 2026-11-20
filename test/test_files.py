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
"Test fixture file setup, directory linking, and cleanup behavior."

import os
from pathlib import Path
import tempfile
import tftest


def test_setup_files():
  with tempfile.TemporaryDirectory() as tmpdir:
    with tempfile.NamedTemporaryFile(delete=False) as tmpfile:
      tmpfile_path = Path(tmpfile.name)
    try:
      tf = tftest.TerraformTest(tmpdir, basedir=tmpfile_path.parent)
      tf.setup(extra_files=[tmpfile_path.name])
      assert (Path(tmpdir) / tmpfile_path.name).exists()
      tf = None
      assert not (Path(tmpdir) / tmpfile_path.name).exists()
    finally:
      tmpfile_path.unlink(missing_ok=True)


def test_setup_files_and_dirs_with_context_manager(tmp_path):
  mod_dir = tmp_path / 'mod'
  mod_dir.mkdir()
  (mod_dir / 'main.tf').write_text('output "ok" {\n  value = true\n}\n')
  extra_file = tmp_path / 'extra.auto.tfvars'
  extra_file.write_text('')
  extra_dir = tmp_path / 'sub_dir'
  extra_dir.mkdir()
  (extra_dir / 'nested.txt').write_text('hello')

  with tftest.TerraformTest(mod_dir) as tf:
    tf.setup(extra_files=[extra_file, extra_dir])
    assert (mod_dir / 'extra.auto.tfvars').is_file()
    assert (mod_dir / 'sub_dir' / 'nested.txt').is_file()

  assert not (mod_dir / 'extra.auto.tfvars').exists()
  assert not (mod_dir / 'sub_dir').exists()
  assert (extra_dir / 'nested.txt').is_file()


def test_existing_lockfile_preserved_on_cleanup(fixtures_dir, tmp_path):
  mod_with_lock = tmp_path / 'with_lock'
  mod_with_lock.mkdir()
  (mod_with_lock / 'main.tf').write_text('terraform {}\n')
  lockfile = mod_with_lock / '.terraform.lock.hcl'
  lockfile.write_text('# existing lockfile\n')

  with tftest.TerraformTest(mod_with_lock) as tf:
    tf.setup()
  assert lockfile.is_file()
  assert lockfile.read_text() == '# existing lockfile\n'

  mod_without_lock = tmp_path / 'without_lock'
  mod_without_lock.mkdir()
  (mod_without_lock / 'main.tf').write_text('resource "null_resource" "x" {}\n')
  with tftest.TerraformTest(mod_without_lock) as tf:
    tf.setup()
    assert (mod_without_lock / '.terraform.lock.hcl').is_file()
  assert not (mod_without_lock / '.terraform.lock.hcl').exists()
