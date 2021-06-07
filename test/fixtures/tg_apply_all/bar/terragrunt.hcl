include {
  path = find_in_parent_folders()
}

terraform {
  source = "../..//apply"
}

inputs = {
    names = ["bar"]
}
