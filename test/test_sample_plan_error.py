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

"Test command out attribute of tftest exception class."

import pytest
import tftest


def test_cmd_err(fixtures_dir):
  with pytest.raises(tftest.TerraformTestError) as e:
    tf = tftest.TerraformTest('foobar')
    tf.setup()
  assert not e.value.cmd_error
  tf = tftest.TerraformTest('plan', fixtures_dir)
  tf.setup()
  with pytest.raises(tftest.TerraformTestError) as e:
    tf.plan()
  assert e.value.cmd_error
