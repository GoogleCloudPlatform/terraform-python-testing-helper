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

"Test init and plan with prevent_destroy lifecycles"
import logging
from unittest.mock import mock_open, patch

import pytest
import tftest


def test_with_no_lifecycle_override(fixtures_dir):
  tf = tftest.TerraformTest('prevent_destroy', fixtures_dir)
  tf.setup()
  tf.apply(auto_approve=True)
  with pytest.raises(tftest.TerraformTestError):
    tf.destroy(auto_approve=True)
    tf.output()


def test_with_with_lifecycle_override(fixtures_dir):
  tf = tftest.TerraformTest('prevent_destroy', fixtures_dir)
  tf.setup(disable_prevent_destroy=True)
  tf.apply(auto_approve=True)
  tf.destroy(auto_approve=True)


@patch('tftest.shutil.copy')
def test_raises_exception_if_file_backup_fails(mock_copy, fixtures_dir, caplog):
  caplog.set_level(logging.ERROR)
  tf = tftest.TerraformTest('prevent_destroy', fixtures_dir)
  mock_copy.side_effect = [FileNotFoundError(
      '[Errno 2] No such file or directory: "sddsdsds"')]
  with pytest.raises(tftest.TerraformTestError):
    tf.setup(disable_prevent_destroy=True)
  assert caplog.messages[0].startswith('Unable to backup terraform file ')


@patch('tftest.shutil.copy')
def test_raises_exception_when_read_or_write_fails(mock_copy, fixtures_dir, caplog):
  caplog.set_level(logging.ERROR)
  tf = tftest.TerraformTest('prevent_destroy', fixtures_dir)
  with patch('builtins.open', mock_open(read_data='')) as mock_file:
    mock_file.return_value.write.side_effect = [
        IOError('[Errno 13] Permission denied: "sddsdsds"')]
    with pytest.raises(tftest.TerraformTestError):
      tf.setup(disable_prevent_destroy=True)
  assert caplog.messages[0].startswith(
      'Unable to update prevent_destroy in file ')
