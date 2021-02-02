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
import os
import sys

p = os.path.abspath('../')
if p not in sys.path:
    sys.path.append(p)

import pytest
import tftest


# @pytest.fixture
# def output(fixtures_dir):
#   tf = tftest.TerraformTest('tg_plan', fixtures_dir, binary='terragrunt')
#   tf.setup()
#   tf.plan_all()
#   yield tf.plan_all()
#   yield tf.output()
#   tf.destroy()


# def test_apply(output):
#     print(output)

tf = tftest.TerraformTest('fixtures/tg_plan', binary='terragrunt')
tf.setup()
plan = tf.plan(output=True)
print('plan: ', plan)
