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

import pytest
import tftest

import os
import sys


@pytest.fixture
def output(fixtures_dir):
  tf = tftest.TerraformTest('tg_apply_all', fixtures_dir, binary='terragrunt')
  tf.setup(all=True)
  tf.tg_apply(all=True, output=False)
  yield tf.tg_output(all=True)
  tf.destroy(**{"auto_approve": True})


@pytest.fixture
def bar_output(fixtures_dir):
  tf = tftest.TerraformTest(os.path.join('tg_apply_all', 'bar'),
                            fixtures_dir, binary='terragrunt')
  tf.setup()
  tf.tg_apply(all=False, output=False)
  yield tf.tg_output(all=True)
  tf.destroy(**{"auto_approve": True})


def test_run_all_apply(output):
  triggers = [o["triggers"] for o in output]
  assert [{'name': 'foo', 'template': 'sample template foo'}] in triggers
  assert [{'name': 'bar', 'template': 'sample template bar'}] in triggers
  assert [{'name': 'one', 'template': 'sample template one'},
          {'name': 'two', 'template': 'sample template two'}] in triggers
  assert len(output) == 3


def test_tg_single_directory_apply(bar_output):
  triggers = [o["triggers"] for o in bar_output]
  assert [{'name': 'bar', 'template': 'sample template bar'}] in triggers
  assert len(bar_output) == 1
