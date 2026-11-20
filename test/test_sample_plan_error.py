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
"Test command execution, error handling, parallelism, and bool variables."

from pathlib import Path
import sys
import pytest
import tftest


def test_cmd_err(fixtures_dir):
  with pytest.raises(tftest.TerraformTestError) as e:
    tf = tftest.TerraformTest('foobar')
    tf.setup()
  assert not e.value.cmd_error
  with tftest.TerraformTest('plan', fixtures_dir) as tf:
    tf.setup()
    with pytest.raises(tftest.TerraformTestError) as e:
      tf.plan()
    assert e.value.cmd_error


def test_missing_binary_raises(tmp_path):
  tf = tftest.TerraformTest(tmp_path, binary='nonexistent-terraform-binary-xyz')
  with pytest.raises(tftest.TerraformTestError) as e:
    tf.setup()
  assert e.value.cmd_error is None


def test_bool_tf_vars_and_parallelism_execution(tmp_path):
  (tmp_path / 'main.tf').write_text('variable "flag" {\n'
                                    '  type = bool\n'
                                    '}\n'
                                    'output "flag" {\n'
                                    '  value = var.flag\n'
                                    '}\n')
  with tftest.TerraformTest(tmp_path) as tf:
    tf.setup()
    plan = tf.plan(output=True, parallelism=5, tf_vars={'flag': True})
    assert plan.outputs['flag'] is True


def test_nonzero_exit_codes_and_large_stderr(tmp_path):
  helper = tmp_path / 'fake_tf.py'
  helper.write_text('import sys\n'
                    'cmd = sys.argv[1]\n'
                    'if cmd == "panic":\n'
                    '  sys.stderr.write("E" * 200000 + "\\n")\n'
                    '  sys.exit(2)\n'
                    'if cmd == "plan" and "-detailed-exitcode" in sys.argv:\n'
                    '  sys.stdout.write("changes present\\n")\n'
                    '  sys.exit(2)\n'
                    'sys.exit(0)\n')
  wrapper = tmp_path / 'fake_tf.sh'
  wrapper.write_text(
      f'#!/usr/bin/env bash\nexec "{sys.executable}" "{helper}" "$@"\n')
  wrapper.chmod(0o755)

  tf = tftest.TerraformTest(tmp_path, binary=wrapper)
  with pytest.raises(tftest.TerraformTestError) as e:
    tf.execute_command('panic')
  assert e.value.cmd_error is not None
  assert len(e.value.cmd_error) >= 200000

  res = tf.execute_command('plan', '-detailed-exitcode')
  assert res.retcode == 2
  assert 'changes present' in res.out
