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

import tftest


_ARGS_TESTS = (
    ({'auto_approve': True}, ['-auto-approve']),
    ({'auto_approve': False}, []),
    ({'backend': True}, []),
    ({'backend': None}, []),
    ({'backend': False}, ['-backend=false']),
    ({'color': True}, []),
    ({'color': False}, ['-no-color']),
    ({'color': False, 'input': False}, ['-no-color', '-input=false']),
    ({'force_copy': True}, ['-force-copy']),
    ({'force_copy': None}, []),
    ({'force_copy': False}, []),
    ({'input': True}, []),
    ({'input': False}, ['-input=false']),
    ({'json_format': True}, ['-json']),
    ({'json_format': False}, []),
    ({'lock': True}, []),
    ({'lock': False}, ['-lock=false']),
    ({'plugin_dir': ''}, []),
    ({'plugin_dir': 'abc'}, ['-plugin-dir', 'abc']),
    ({'refresh': True}, []),
    ({'refresh': None}, []),
    ({'refresh': False}, ['-refresh=false']),
)
_AUTORUN_CALLS = [
    ['terraform', 'init', '-no-color', '-input=false'],
    ['terraform', 'apply', '-auto-approve', '-no-color', '-input=false'],
    ['terraform', 'output', '-no-color', '-json'],
    ['terraform', 'destroy', '-auto-approve', '-no-color'],
]


def test_parse_args():
  "Test parsing Terraform command arguments."
  assert tftest.parse_args() == []
  for kwargs, expected in _ARGS_TESTS:
    assert tftest.parse_args(**kwargs) == expected
  assert sorted(tftest.parse_args(init_vars={'a': 1, 'b': '["2"]'})) == sorted(
      ["-backend-config='a=1'", '-backend-config=\'b=["2"]\''])
  assert sorted(tftest.parse_args(tf_vars={'a': 1, 'b': '["2"]'})) == sorted(
      ['-var', 'b=["2"]', '-var', 'a=1'])


def test_json_output_class():
  "Test the output and variables wrapper class."
  out = tftest.TerraformValueDict(
      {'a': {'value': 1}, 'b': {'value': 2, 'sensitive': True}})
  assert out.sensitive == ('b',)
  assert (out['a'], out['b']) == (1, 2)


def test_json_state_class():
  "Test the state wrapper class."
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
  assert sorted(list(s.modules.keys())) == ['a', 'b']
  assert type(s.modules['a']) == tftest.TerraformStateModule
  assert type(s.modules['a'].outputs) == tftest.TerraformValueDict


def test_plan_out_class():
  "Test the plan JSON output wrapper class."
  s = {
      "format_version": "0.1",
      "terraform_version": "0.12.6",
      "variables": {
          "foo": {
              "value": "bar"
          }
      },
      "planned_values": {
          "outputs": {
              "spam": {
                  "sensitive": False,
                  "value": "baz"
              },
          },
          "root_module": {
              "child_modules": [{
                  "resources": [{
                      "address": "module.eggs.google_project.project",
                      "type": "google_project",
                      "name": "project",
                      "provider_name": "google",
                      "values": {"foo": "foo_value"}
                  }],
                  "child_modules": [{
                      "resources": [{
                          "address": "module.eggs.google_project.project",
                          "type": "google_project",
                          "name": "project",
                          "provider_name": "google",
                          "values": {"foo": "foo_value"}
                      }],
                  }
                  ]
              }]
          }
      },
      "resource_changes": [
          {
              "address": "module.spam.resource_type.resource.name",
              "module_address": "module.spam",
              "mode": "managed"
          }
      ],
      "output_changes": {
          "spam": {
              "actions": [
                  "create"
              ],
              "before": None,
              "after": "bar",
              "after_unknown": False
          },
      },
      "prior_state": {
          "format_version": "0.1",
          "terraform_version": "0.12.6"
      },
      "configuration": {
          "provider_config": {
              "google": {
                  "name": "google"
              }
          },
      }
  }
  plan_out = tftest.TerraformPlanOutput(s)
  assert plan_out.terraform_version == "0.12.6", plan_out.terraform_version
  assert plan_out.variables['foo'] == 'bar'
  assert plan_out.outputs['spam'] == 'baz'
  assert plan_out.modules['module.eggs'] == {}
  assert plan_out.resource_changes['module.spam.resource_type.resource.name'] == s['resource_changes'][0]
  assert plan_out.configuration == s['configuration']


def test_setup_files():
  "Test that extra files are linked in on setup and removed on dereferencing."
  with tempfile.TemporaryDirectory() as tmpdir:
    with tempfile.NamedTemporaryFile() as tmpfile:
      tf = tftest.TerraformTest(tmpdir)
      tf.setup(extra_files=[tmpfile.name])
      assert os.path.exists(os.path.join(
          tmpdir, os.path.basename(tmpfile.name)))
      tf = None
      assert not os.path.exists(os.path.join(
          tmpdir, os.path.basename(tmpfile.name)))


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
        assert call == unittest.mock.call(_AUTORUN_CALLS[i], **kwargs)
