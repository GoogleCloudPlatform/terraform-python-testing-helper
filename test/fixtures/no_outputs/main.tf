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


module "service-accounts" {
  source     = "terraform-google-modules/service-accounts/google"
  version    = "2.0.0"
  project_id = var.project_id
  prefix     = var.prefix
  names      = var.names
}

module "gcs-buckets" {
  source          = "terraform-google-modules/cloud-storage/google"
  version         = "1.0.0"
  project_id      = var.project_id
  prefix          = var.prefix
  names           = var.names
  location        = var.gcs_location
  set_admin_roles = true
  bucket_admins = zipmap(
    var.names,
    module.service-accounts.iam_emails_list
  )
}

resource "google_project_iam_member" "test_root_resource" {
  project = var.project_id
  role    = "roles/viewer"
  member  = module.service-accounts.iam_email
}
