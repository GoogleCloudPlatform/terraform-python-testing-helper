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

variable "foo_var" {
  default = ["foo"]
}

resource "null_resource" "foo_resource" {
  count = "${length(var.foo_var)}"

  triggers {
    index = "${count.index}"
    foo   = "${element(var.foo_var, count.index)}"
  }
}

output "foos" {
  value = "${null_resource.foo_resource.*.triggers}"
}
