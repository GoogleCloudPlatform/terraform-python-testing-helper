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


@pytest.fixture
def run_all_apply_out(fixtures_dir):
  tg = tftest.TerragruntTest('tg_apply_all', fixtures_dir, tg_run_all=True)
  tg.setup()
  tg.apply(output=False, tg_non_interactive=True)
  yield tg.output()
  tg.destroy(auto_approve=True, tg_non_interactive=True)


@pytest.fixture
def run_all_plan_output(fixtures_dir):
  tg = tftest.TerragruntTest('tg_apply_all', fixtures_dir, tg_run_all=True)
  tg.setup()
  return tg.plan(output=True, tg_working_dir=os.path.join(fixtures_dir, 'tg_apply_all'))


@pytest.fixture
def plan_foo_output(fixtures_dir):
  tg = tftest.TerragruntTest(os.path.join('tg_apply_all', 'foo'), fixtures_dir)
  tg.setup()
  return tg.plan(output=True)


@pytest.fixture
def bar_output(fixtures_dir):
  tg = tftest.TerragruntTest(os.path.join('tg_apply_all', 'bar'), fixtures_dir)
  tg.setup()
  tg.apply(output=False, tg_non_interactive=True)
  yield tg.output()
  tg.destroy(auto_approve=True, tg_non_interactive=True)


def test_run_all_apply(run_all_apply_out):
  triggers = [o["triggers"] for o in run_all_apply_out]
  assert [{'name': 'foo', 'template': 'sample template foo'}] in triggers
  assert [{'name': 'bar', 'template': 'sample template bar'}] in triggers
  assert [{'name': 'one', 'template': 'sample template one'},
          {'name': 'two', 'template': 'sample template two'}] in triggers
  assert len(run_all_apply_out) == 3


def test_tg_single_directory_apply(bar_output):
  assert bar_output["triggers"] == [{'name': 'bar', 'template': 'sample template bar'}]


def test_run_all_plan(run_all_plan_output):
  triggers = [o.outputs["triggers"] for o in run_all_plan_output]
  assert [{'name': 'foo', 'template': 'sample template foo'}] in triggers
  assert [{'name': 'bar', 'template': 'sample template bar'}] in triggers
  assert [{'name': 'one', 'template': 'sample template one'},
          {'name': 'two', 'template': 'sample template two'}] in triggers
  assert len(run_all_plan_output) == 3


def test_tg_single_directory_plan(plan_foo_output):
  assert plan_foo_output.outputs['triggers'] == [{'name': 'foo', 'template': 'sample template foo'}]
  assert plan_foo_output.variables['names'] == ['foo']
