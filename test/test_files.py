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

"Test fixture file setup and removal."

import os
import tempfile
import tftest


def test_setup_files():
  with tempfile.TemporaryDirectory() as tmpdir:
    with tempfile.NamedTemporaryFile() as tmpfile:
      tf = tftest.TerraformTest(tmpdir)
      tf.setup(extra_files=[tmpfile.name])
      assert os.path.exists(os.path.join(
          tmpdir, os.path.basename(tmpfile.name)))
      tf = None
      assert not os.path.exists(os.path.join(
          tmpdir, os.path.basename(tmpfile.name)))
