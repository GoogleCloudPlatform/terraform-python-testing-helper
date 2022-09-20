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
import pytest
import tftest
from unittest.mock import patch

pytest_plugins = [
    str("_pytest.pytester"),
]

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

basic_terra_py = """
import pytest
import logging
import sys
import tftest

log = logging.getLogger(__name__)
stream = logging.StreamHandler(sys.stdout)
log.addHandler(stream)
log.setLevel(logging.DEBUG)


@pytest.mark.parametrize("terra", {}, indirect=['terra'])
def test_terra_param(terra):
    log.debug(terra)
"""


@pytest.fixture
def base_tester(pytester):
  """Creates conftest.py file that will be used within the testing pytest session"""
  pytester.makeconftest(
      """
        import sys
        if "tftest_fixt" not in sys.modules:
            pytest_plugins = "tftest_fixt"
    """
  )
  return pytester


def test_terra_kwargs(base_tester):
  """Ensure all kwargs are supported and fixture is parametrizable"""
  params = [
      {
          "binary": "terraform",
          "basedir": "/fixture",
          "tfdir": "bar",
          "env": {},
      },
      {
          "binary": "terragrunt",
          "basedir": "/fixture",
          "tfdir": "bar",
          "env": {},
          "tg_run_all": True,
      },
  ]
  base_tester.makepyfile(basic_terra_py.format(params))
  reprec = base_tester.inline_run()

  reprec.assertoutcome(passed=len(params))


# asserts tftest.TerraformTest method outputs are returned
test_without_cache_file = """
import tftest
import pytest
import os

def pytest_generate_tests(metafunc):
    metafunc.parametrize("terra",{terra_param},indirect=True,)


@pytest.mark.usefixtures("terra")
class TestTerraCommands:
    def test_terra_setup(self, terra_setup):
        assert type(terra_setup) == str

    @pytest.mark.parametrize("terra_plan", [{{"output": True}}], indirect=True)
    def test_terra_plan(self, terra_plan):
        assert isinstance(terra_plan, tftest.TerraformPlanOutput)

    def test_terra_apply(self, terra_apply):
        assert type(terra_apply) == str

    def test_terra_output(self, terra_output):
        assert isinstance(terra_output, tftest.TerraformValueDict)
"""

# asserts tftest.TerraformTest method outputs are returned and there associated
# patches are not called
test_with_cache_file = """
import tftest
import pytest
import os
from unittest.mock import patch

def pytest_generate_tests(metafunc):
    metafunc.parametrize("terra",{terra_param},indirect=True,)


@pytest.mark.usefixtures("terra")
class TestTerraCommands:
    # tftest.TerragruntTest methods don't need to be patched since
    # it uses tftest.TerraformTest methods
    @patch("tftest.TerraformTest.setup")
    def test_terra_setup(self, mock_setup, terra_setup):
        assert type(terra_setup) == str
        assert mock_setup.call_args_list == []

    @pytest.mark.parametrize("terra_plan", [{{"output": True}}], indirect=True)
    @patch("tftest.TerraformTest.plan")
    def test_terra_plan(self, mock_plan, terra_plan):
        assert isinstance(terra_plan, tftest.TerraformPlanOutput)
        assert mock_plan.call_args_list == []

    @patch("tftest.TerraformTest.apply")
    def test_terra_apply(self, mock_apply, terra_apply):
        assert type(terra_apply) == str
        assert mock_apply.call_args_list == []


    @patch("tftest.TerraformTest.output")
    def test_terra_output(self, mock_output, terra_output, terra):
        assert isinstance(terra_output, tftest.TerraformValueDict)
        assert mock_output.call_args_list == []
"""


def test_terra_fixt_without_cache(base_tester):
  """Ensure terra command fixtures run without error"""
  base_tester.makepyfile(
      test_without_cache_file.format(
          terra_param=[
              {
                  "binary": "terraform",
                  "tfdir": os.path.dirname(__file__) + "/fixtures/plan_no_resource_changes",
              },
              {
                  "binary": "terragrunt",
                  "tfdir": os.path.dirname(__file__) + "/fixtures/plan_no_resource_changes",
              },
          ]
      )
  )
  log.info("Running test file without cache")
  reprec = base_tester.inline_run("--cache-clear")
  reprec.assertoutcome(passed=sum(reprec.countoutcomes()))


def test_terra_fixt_with_cache(base_tester):
  """Ensure cache is used for subsequent pytest session"""
  log.info("Running test file without cache")
  base_tester.makepyfile(
      test_without_cache_file.format(
          terra_param=[
              {
                  "binary": "terraform",
                  "tfdir": os.path.dirname(__file__) + "/fixtures/plan_no_resource_changes",
              },
              {
                  "binary": "terragrunt",
                  "tfdir": os.path.dirname(__file__) + "/fixtures/plan_no_resource_changes",
              },
          ]
      )
  )

  # --cache-clear removes .pytest_cache cache files
  reprec = base_tester.inline_run("--cache-clear")
  reprec.assertoutcome(passed=sum(reprec.countoutcomes()))

  log.info("Running test file with cache")
  base_tester.makepyfile(
      test_with_cache_file.format(
          terra_param=[
              {
                  "binary": "terraform",
                  "tfdir": os.path.dirname(__file__) + "/fixtures/plan_no_resource_changes",
              },
              {
                  "binary": "terragrunt",
                  "tfdir": os.path.dirname(__file__) + "/fixtures/plan_no_resource_changes",
              },
          ]
      )
  )
  reprec = base_tester.inline_run()
  reprec.assertoutcome(passed=sum(reprec.countoutcomes()))


@patch("tftest.TerraformTest.plan", return_value=tftest.TerraformPlanOutput)
def test_subsequent_calls_use_cache(mock_plan, base_tester):
  """
  Ensures that the initial terra_plan fixture call uses the plan method
  and subsequent calls use the cache value within the same pytest session
  """
  test_file = """
    import tftest
    import pytest
    import os
    from unittest.mock import patch, call

    def pytest_generate_tests(metafunc):
        metafunc.parametrize("terra",{terra_param},indirect=True,)
        metafunc.parametrize("terra_plan", [{{"output": True}}], indirect=True)

    @pytest.mark.usefixtures("terra")
    def test_runs_command(terra_plan):
        assert type(terra_plan) == tftest.TerraformPlanOutput

    @pytest.mark.usefixtures("terra")
    def test_uses_cache(terra_plan):
        assert type(terra_plan) == tftest.TerraformPlanOutput
    """

  base_tester.makepyfile(
      test_file.format(
          terra_param=[
              {
                  "binary": "terraform",
                  "tfdir": os.path.dirname(__file__) + "/fixtures/plan_no_resource_changes",
              }
          ]
      )
  )

  # --cache-clear removes .pytest_cache cache files
  base_tester.inline_run("--cache-clear")
  assert mock_plan.call_count == 1
