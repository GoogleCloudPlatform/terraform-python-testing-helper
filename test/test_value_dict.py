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

"Test the Terraform value dict wrapper class."

import pytest
import tftest


_RAW = {'a': {'value': 1, 'sensitive': True}, 'b': {'value': 2}}


@pytest.fixture
def wrapper():
  return tftest.TerraformValueDict(_RAW)


def test_getitem(wrapper):
  assert wrapper['a'] == 1


def test_getitem_dict_attrs(wrapper):
  assert wrapper.keys() == _RAW.keys()


def test_iter(wrapper):
  assert [k for k in wrapper] == [k for k in _RAW]
