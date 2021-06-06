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
import pytest

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


@pytest.mark.parametrize("kwargs, expected", ARGS_TESTS)
def test_args(kwargs, expected):
  assert tftest.parse_args() == []
  assert tftest.parse_args(**kwargs) == expected


TERRAGRUNT_ARGS_TESTCASES = [
    ({"tg_config": "Obama"}, ['--terragrunt-config', 'Obama']),
    ({"tg_tfpath": "Barrack"}, ['--terragrunt-tfpath', 'Barrack']),
    ({"tg_no_auto_init": True}, ['--terragrunt-no-auto-init']),
    ({"tg_no_auto_init": False}, []),
    ({"tg_no_auto_retry": True}, ['--terragrunt-no-auto-retry']),
    ({"tg_no_auto_retry": False}, []),
    ({"tg_non_interactive": True}, ['--terragrunt-non-interactive']),
    ({"tg_non_interactive": False}, []),
    ({"tg_working_dir": "George"}, ['--terragrunt-working-dir', 'George']),
    ({"tg_download_dir": "Bush"}, ['--terragrunt-download-dir', 'Bush']),
    ({"tg_source": "Clinton"}, ['--terragrunt-source', 'Clinton']),
    ({"tg_source_update": True}, ['--terragrunt-source-update']),
    ({"tg_source_update": False}, []),
    ({"tg_iam_role": "Bill"}, ['--terragrunt-iam-role', 'Bill']),
    ({"tg_ignore_dependency_errors": True}, ['--terragrunt-ignore-dependency-errors']),
    ({"tg_ignore_dependency_errors": False}, []),
    ({"tg_ignore_dependency_order": True}, ['--terragrunt-ignore-dependency-order']),
    ({"tg_ignore_dependency_order": False}, []),
    ({"tg_ignore_external_dependencies": "dont care what is here"},
     ['--terragrunt-ignore-external-dependencies']),
    ({"tg_include_external_dependencies": True}, ['--terragrunt-include-external-dependencies']),
    ({"tg_include_external_dependencies": False}, []),
    ({"tg_parallelism": 20}, ['--terragrunt-parallelism 20']),
    ({"tg_exclude_dir": "Ronald"}, ['--terragrunt-exclude-dir', 'Ronald']),
    ({"tg_include_dir": "Reagan"}, ['--terragrunt-include-dir', 'Reagan']),
    ({"tg_check": True}, ['--terragrunt-check']),
    ({"tg_check": False}, []),
    ({"tg_hclfmt_file": "Biden"}, ['--terragrunt-hclfmt-file', 'Biden']),
    ({"tg_override_attr": {"Iron": "Man", "Captain": "America"}},
     ['--terragrunt-override-attr=Iron=Man', '--terragrunt-override-attr=Captain=America']),
    ({"tg_debug": True}, ['--terragrunt-debug']),
    ({"tg_debug": False}, []),

]


@pytest.mark.parametrize("kwargs, expected", TERRAGRUNT_ARGS_TESTCASES)
def test_terragrunt_args(kwargs, expected):
  assert tftest.parse_args(**kwargs) == expected


def test_var_args():
  assert sorted(tftest.parse_args(init_vars={'a': 1, 'b': '["2"]'})) == sorted(
      ["-backend-config=a=1", '-backend-config=b=["2"]'])
  assert sorted(tftest.parse_args(tf_vars={'a': 1, 'b': '["2"]'})) == sorted(
      ['-var', 'b=["2"]', '-var', 'a=1'])


def test_targets():
  assert tftest.parse_args(targets=['one', 'two']) == sorted(
      ['-target=one', '-target=two'])
