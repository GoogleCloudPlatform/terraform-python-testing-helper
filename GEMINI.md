# Gemini CLI Instructions for terraform-python-testing-helper

- **Git Workflow:** Never use `git commit --amend`. Always create a new commit and push to the same branch to update an existing Pull Request.
- **File Editing:** Always use the `replace` tool (or `write_file` for new files) for file edits. Do NOT use shell heredocs (`cat << 'EOF'`) or inline Python scripts to modify files.
- **Copyright Boilerplate:** All new files must include the Apache 2.0 license boilerplate at the top. Ensure the copyright year is current (e.g., 2026).
- **Linting:** Always run the project's linters before committing changes. Specifically, check formatting with `yapf --diff --recursive --parallel *.py test` and verify license headers with `python3 .github/workflows/scripts/check_boilerplate.py .`.
- **Regressions & Testing:** When fixing a regression, fix it at the source library level. Do not modify the caller's code to work around the issue. Always create a reliable test case that reproduces the error before implementing the fix.