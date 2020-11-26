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

"Test the function for mapping Terraform arguments."

import tftest


ARGS_TESTS = (
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
    ({'tf_var_file': None}, []),
    ({'tf_var_file': 'foo.tfvar'}, ['-var-file=foo.tfvar']),
)


def test_args():
  assert tftest.parse_args() == []
  for kwargs, expected in ARGS_TESTS:
    assert tftest.parse_args(**kwargs) == expected


def test_var_args():
  assert sorted(tftest.parse_args(init_vars={'a': 1, 'b': '["2"]'})) == sorted(
      ["-backend-config=a=1", '-backend-config=b=["2"]'])
  assert sorted(tftest.parse_args(tf_vars={'a': 1, 'b': '["2"]'})) == sorted(
      ['-var', 'b=["2"]', '-var', 'a=1'])


def test_targets():
  assert tftest.parse_args(targets=['one', 'two']) == sorted(
      ['-target=one', '-target=two'])
