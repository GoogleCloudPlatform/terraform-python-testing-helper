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
  source     = "github.com/terraform-google-modules/cloud-foundation-fabric//modules/iam-service-accounts?ref=v3.2.0"
  project_id = var.project_id
  prefix     = var.prefix
  names      = var.names
}

module "gcs-buckets" {
  source     = "github.com/terraform-google-modules/cloud-foundation-fabric//modules/gcs?ref=v3.2.0"
  project_id = var.project_id
  prefix     = var.prefix
  names      = var.names
  location   = var.gcs_location
}

resource "google_project_iam_member" "test_root_resource" {
  project = var.project_id
  role    = "roles/viewer"
  member  = module.service-accounts.iam_email
}
