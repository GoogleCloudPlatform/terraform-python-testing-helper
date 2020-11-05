/**
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */


module "service-account" {
  source     = "../_modules/iam-service-account"
  project_id = var.project_id
  prefix     = var.prefix
  name       = var.name
}

resource "google_project_iam_member" "test_root_resource" {
  project = var.project_id
  role    = "roles/viewer"
  member  = module.service-account.iam_email
}
