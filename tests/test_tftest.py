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

import json
import os
import tempfile
import unittest.mock

from nose.tools import assert_equals, assert_false, assert_true

import tftest


_ARGS_TESTS = (
    ({'auto_approve': False}, []),
    ({'color': True}, []),
    ({'input': True}, []),
    ({'json_format': False}, []),
    ({'lock': True}, []),
    ({'plugin_dir': ''}, []),
    ({'auto_approve': True}, ['-auto-approve']),
    ({'color': False}, ['-no-color']),
    ({'input': False}, ['-input=false']),
    ({'json_format': True}, ['-json']),
    ({'lock': False}, ['-lock=false']),
    ({'plugin_dir': 'abc'}, ['-plugin-dir', 'abc']),
    ({'color': False, 'input': False}, ['-no-color', '-input=false'])
)
_AUTORUN_CALLS = [
    ['terraform', 'init', '-no-color', '-input=false'],
    ['terraform', 'apply', '-auto-approve', '-no-color', '-input=false'],
    ['terraform', 'output', '-no-color', '-json'],
    ['terraform', 'destroy', '-auto-approve', '-no-color'],
]


def test_parse_args():
  assert_equals(tftest.parse_args(), [])
  for kwargs, expected in _ARGS_TESTS:
    assert_equals(tftest.parse_args(**kwargs), expected)
  assert_equals(
      sorted(tftest.parse_args(init_vars={'a': 1, 'b': '["2"]'})),
      sorted(["-backend-config='a=1'", '-backend-config=\'b=["2"]\'']))
  assert_equals(
      sorted(tftest.parse_args(tf_vars={'a': 1, 'b': '["2"]'})),
      sorted(['-var', 'b=["2"]', '-var', 'a=1'])
  )


def test_json_output_class():
  out = tftest.TerraformOutputs(
      {'a': {'value': 1}, 'b': {'value': 2, 'sensitive': True}})
  assert_equals(out.sensitive, ('b',))
  assert_equals((out['a'], out['b']), (1, 2))


def test_json_state_class():
  s = tftest.TerraformState({
      'version': 'foo',
      'modules': [
          {
              'path': 'a',
              'outputs': {'a_out': {'value': 1}},
              'resources': {'a_resource': {
                  'provider': 'dummy', 'type': 'dummy',
                  'attributes': {'id': 'a'}, 'depends_on': []
              }},
              'depends_on': 'a_depends_on'
          },
          {
              'path': 'b',
              'outputs': {'b_out': {'value': 2}},
              'resources': {'b_resource': {
                  'provider': 'dummy', 'type': 'dummy',
                  'attributes': {'id': 'b'}, 'depends_on': []
              }},
              'depends_on': 'b_depends_on'
          }
      ]
  })
  assert_equals(sorted(list(s.modules.keys())), ['a', 'b'])
  assert_equals(type(s.modules['a']), tftest.TerraformStateModule)
  assert_equals(type(s.modules['a'].outputs), tftest.TerraformOutputs)


def test_setup_files():
  "Test that extra files are linked in on setup and removed on dereferencing."
  with tempfile.TemporaryDirectory() as tmpdir:
    with tempfile.NamedTemporaryFile() as tmpfile:
      tf = tftest.TerraformTest(tmpdir)
      tf.setup(extra_files=[tmpfile.name])
      assert_true(os.path.exists(os.path.join(
          tmpdir, os.path.basename(tmpfile.name))))
      tf = None
      assert_false(os.path.exists(os.path.join(
          tmpdir, os.path.basename(tmpfile.name))))


def test_autorun():
  "Test that autorun executes the right commands in setup and destroy"
  with unittest.mock.patch('tftest.os.environ.copy', return_value={}):
    with unittest.mock.patch('tftest.subprocess.Popen', autospec=True) as Popen:
      Popen.return_value.communicate.return_value = (
          b'{"a":{"value":1, "sensitive": 0}}', b'error')
      Popen.return_value.returncode = 0
      with tempfile.TemporaryDirectory() as tmpdir:
        tf = tftest.TerraformTest(tmpdir)
        tf.setup(command='output', destroy=True)
        tf.teardown()
      # popen instantiations
      kwargs = {'cwd': tmpdir, 'env': {}, 'stderr': -1, 'stdout': -1}
      call_args_list = Popen.call_args_list
      for i, call in enumerate(call_args_list):
        assert_equals(call, unittest.mock.call(_AUTORUN_CALLS[i], **kwargs))
