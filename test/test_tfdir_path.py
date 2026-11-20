# Copyright 2026 Google LLC
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

import tempfile
from pathlib import Path
import tftest


def test_tfdir_as_path():
  with tempfile.TemporaryDirectory() as tmpdir:
    tmpdir_path = Path(tmpdir).resolve()
    tf = tftest.TerraformTest(tmpdir_path)
    assert isinstance(tf.tfdir, Path)
    assert (tf.tfdir / 'something') == tmpdir_path / 'something'


def test_tfdir_as_str():
  with tempfile.TemporaryDirectory() as tmpdir:
    tf = tftest.TerraformTest(tmpdir)
    assert isinstance(tf.tfdir, Path)
    assert (tf.tfdir / 'something') == Path(tmpdir) / 'something'


def test_tfdir_relative():
  with tempfile.TemporaryDirectory() as tmpdir:
    sub = Path(tmpdir) / 'child'
    sub.mkdir()
    tf_from_str = tftest.TerraformTest('child', basedir=tmpdir)
    tf_from_path = tftest.TerraformTest(Path('child'), basedir=Path(tmpdir))
    assert isinstance(tf_from_str.tfdir, Path)
    assert isinstance(tf_from_path.tfdir, Path)
    assert tf_from_str.tfdir == sub
    assert tf_from_path.tfdir == sub
