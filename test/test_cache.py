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

import logging
import os
import shutil
import pytest
import tftest
from unittest.mock import patch, DEFAULT, Mock

pytest_plugins = [
    str("_pytest.pytester"),
]

_LOGGER = logging.getLogger('tftest')

cache_methods = ["setup", "init", "plan", "apply", "output", "destroy"]


@pytest.fixture
def tf(request, fixtures_dir):
  terra = tftest.TerraformTest(
      tfdir='plan_no_resource_changes',
      basedir=fixtures_dir,
      enable_cache=request.param,
  )
  yield terra

  _LOGGER.debug("Removing cache dir")
  try:
    shutil.rmtree(terra.cache_dir)
  except FileNotFoundError:
    _LOGGER.debug("%s does not exists", terra.cache_dir)


@pytest.mark.parametrize("tf", [True], indirect=True)
def test_use_cache(tf):
  """
  Ensures cache is used and runs the execute_command() for first call of the 
  method only
  """
  for method in cache_methods:
    with patch.object(tf, 'execute_command', wraps=tf.execute_command) as mock_execute_command:
      for _ in range(2):
        getattr(tf, method)(use_cache=True)
      assert mock_execute_command.call_count == 1


@pytest.mark.parametrize("tf", [
    pytest.param(
        True,
        id="enable_cache"
    ),
    pytest.param(
        False,
        id="disable_cache"
    ),
], indirect=True)
def test_no_use_cache(tf):
  """
  Ensures cache is not used and runs the execute_command() for every call of
  the method
  """
  expected_call_count = 2
  for method in cache_methods:
    with patch.object(tf, 'execute_command', wraps=tf.execute_command) as mock_execute_command:
      for _ in range(expected_call_count):
        getattr(tf, method)(use_cache=False)
      assert mock_execute_command.call_count == expected_call_count
