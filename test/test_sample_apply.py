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

"Test init and apply using an actual example."

import pytest
import tftest


@pytest.fixture
def output(fixtures_dir):
  tf = tftest.TerraformTest('apply', fixtures_dir)
  tf.setup()
  tf.apply()
  yield tf.output()
  tf.destroy()


def test_apply(output):
  value = output['triggers']
  assert len(value) == 2
  assert list(value[0].keys()) == ['name', 'template']
  assert value[0]['name'] == 'one'
