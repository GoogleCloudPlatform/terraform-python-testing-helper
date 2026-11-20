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

import os
import pytest
import tftest


def pytest_addoption(parser):
  parser.addoption('--tf-binary', action='store',
                   default=os.environ.get('TFTEST_BINARY', 'terraform'),
                   help='Terraform or OpenTofu binary to use in tests.')


@pytest.fixture(autouse=True)
def configure_tf_binary(request, monkeypatch):
  binary = request.config.getoption('--tf-binary')
  if binary != 'terraform':
    orig_init = tftest.TerraformTest.__init__

    def _init(self, tfdir, basedir=None, binary=binary, env=None):
      orig_init(self, tfdir, basedir=basedir, binary=binary, env=env)

    monkeypatch.setattr(tftest.TerraformTest, '__init__', _init)


@pytest.fixture(scope='session')
def fixtures_dir():
  return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')
