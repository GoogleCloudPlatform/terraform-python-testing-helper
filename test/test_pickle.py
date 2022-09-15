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

"Test serialization of tftest instances"

import pytest
import tftest
import pickle


def assert_pickle_flow(obj):
  """Ensures instance is the same after being pickled"""
  pickled_obj = pickle.dumps(obj)
  pickled_obj = pickle.loads(pickled_obj)
  assert isinstance(pickled_obj, type(obj))


@pytest.fixture(scope="module")
def tf(fixtures_dir):
  tf = tftest.TerraformTest("plan_no_resource_changes", fixtures_dir)
  tf.setup()
  return tf


def test_setup(fixtures_dir):
  tf = tftest.TerraformTest("plan_no_resource_changes", fixtures_dir)
  expected = tf.setup()
  assert_pickle_flow(expected)


def test_plan(tf):
  expected = tf.plan(output=True)
  assert_pickle_flow(expected)


def test_apply(tf):
  expected = tf.apply()
  assert_pickle_flow(expected)


def test_output(tf):
  expected = tf.output()
  assert_pickle_flow(expected)


def test_state_pull(tf):
  expected = tf.state_pull()
  assert_pickle_flow(expected)
