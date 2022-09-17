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
import logging
import json
import pickle
from hashlib import sha1

_LOGGER = logging.getLogger('tftest')


@pytest.fixture(scope="session")
def terra(request):
  if request.param["binary"].endswith("terraform"):
    terra_cls = tftest.TerraformTest(**request.param)
  elif request.param["binary"].endswith("terragrunt"):
    terra_cls = tftest.TerragruntTest(**request.param)

  return terra_cls


def _execute_command(request, terra, cmd):
  cmd_kwargs = getattr(request, "param", {}).get(
      terra.tfdir, getattr(request, "param", {})
  )
  params = {
      **{
          k: v
          for k, v in terra.__dict__.items()
          if type(v) in [str, int, bool, dict, list]
      },
      **cmd_kwargs,
  }

  param_hash = sha1(
      json.dumps(params, sort_keys=True, default=str).encode("cp037")
  ).hexdigest()
  _LOGGER.debug(f"Param hash: {param_hash}")

  cache_key = request.config.cache.makedir("tftest") + (
      terra.tfdir + "/" + cmd + "-" + param_hash
  )
  _LOGGER.debug(f"Cache key: {cache_key}")
  cache_value = request.config.cache.get(cache_key, None)

  if cache_value:
    _LOGGER.info("Getting output from cache")
    return pickle.loads(cache_value.encode("cp037"))
  else:
    _LOGGER.info("Running command")
    out = getattr(terra, cmd)(**cmd_kwargs)
    if out:
      request.config.cache.set(
          cache_key, pickle.dumps(out).decode("cp037"))
    return out


@pytest.fixture(scope="session")
def terra_setup(terra, request):
  return _execute_command(request, terra, "setup")


@pytest.fixture(scope="session")
def terra_plan(terra_setup, terra, request):
  return _execute_command(request, terra, "plan")


@pytest.fixture(scope="session")
def terra_apply(terra_setup, terra, request):
  return _execute_command(request, terra, "apply")


@pytest.fixture(scope="session")
def terra_output(terra, request):
  return _execute_command(request, terra, "output")
