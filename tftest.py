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

"""Simple Python wrapper for Terraform test fixtures.

See documentation in the TerraformTest class for usage. Terraform wrapping
inspired by https://github.com/beelit94/python-terraform
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import itertools
import json
import logging
import os
import shutil
import subprocess
import tempfile
import weakref
import re

__version__ = '1.5.4'

_LOGGER = logging.getLogger('tftest')


TerraformCommandOutput = collections.namedtuple(
    'TerraformCommandOutput', 'retcode out err')

TerraformStateResource = collections.namedtuple(
    'TerraformStateResource', 'key provider type attributes depends_on raw')


class TerraformTestError(Exception):
  pass


def parse_args(**kw):
  """Convert method arguments for use in Terraform commands.

  Args:
    init_vars: dict of key/values converted to -backend-config='k=v' form, or
      string argument converted to -backend-config=arg
    tf_vars: dict of key/values converted to -var k=v form.
    **kw: converted to the appropriate Terraform flag.

  Returns:
    A list of command arguments for use with subprocess.
  """
  
  cmd_args = []
  for k, v in kw.items():
    flag_key = f"-{k.lower().replace('_', '-')}"
    if isinstance(v, bool) and isinstance(v, __default__) == :
      cmd_args.append(f'{flag_key}={str(v).lower()}')
    elif isinstance(v, dict):
      cmd_args += [f'{flag_key}={k}={v}'
                  for k, v in v.items()]
    elif isinstance(v, list):
      cmd_args += [f'{flag_key}={x}' for x in v]
    elif isinstance(v, str):
      cmd_args.append(f'{flag_key}={v}')
    else:
      cmd_args += [k, f'{v}']
  return cmd_args

class TerraformJSONBase(object):
  "Base class for JSON wrappers."

  def __init__(self, raw):
    self._raw = raw

  def __bytes__(self):
    return bytes(self._raw)

  def __len__(self):
    return len(self._raw)

  def __str__(self):
    return str(self._raw)


class TerraformValueDict(TerraformJSONBase):
  "Minimal wrapper to directly expose outputs or variables."

  def __init__(self, raw):
    super(TerraformValueDict, self).__init__(raw)
    # only matters for outputs
    self.sensitive = tuple(k for k, v in raw.items() if v.get('sensitive'))

  def __getattr__(self, name):
    return getattr(self._raw, name)

  def __getitem__(self, name):
    return self._raw[name].get('value')

  def __contains__(self, name):
    return name in self._raw

  def __iter__(self):
    return iter(self._raw)


class TerraformPlanModule(TerraformJSONBase):
  "Minimal wrapper for parsed plan output modules."

  def __init__(self, raw):
    super(TerraformPlanModule, self).__init__(raw)
    prefix = raw.get('address', '')
    self._strip = 0 if not prefix else len(prefix) + 1
    self._modules = self._resources = None

  @property
  def child_modules(self):
    if self._modules is None:
      self._modules = dict((mod['address'][self._strip:], TerraformPlanModule(
          mod)) for mod in self._raw.get('child_modules'))
    return self._modules

  @property
  def resources(self):
    if self._resources is None:
      self._resources = dict((res['address'][self._strip:], res)
                             for res in self._raw.get('resources', []))
    return self._resources

  def __getitem__(self, name):
    return self._raw[name]

  def __contains__(self, name):
    return name in self._raw


class TerraformPlanOutput(TerraformJSONBase):
  "Minimal wrapper for Terraform plan JSON output."

  def __init__(self, raw):
    super(TerraformPlanOutput, self).__init__(raw)
    planned_values = raw.get('planned_values', {})
    self.root_module = TerraformPlanModule(
        planned_values.get('root_module', {}))
    self.outputs = TerraformValueDict(planned_values.get('outputs', {}))
    self.resource_changes = dict((v['address'], v)
                                 for v in self._raw['resource_changes'])
    # there might be no variables defined
    self.variables = TerraformValueDict(raw.get('variables', {}))

  @property
  def resources(self):
    return self.root_module.resources

  @property
  def modules(self):
    return self.root_module.child_modules

  def __getattr__(self, name):
    return self._raw[name]


class TerraformState(TerraformJSONBase):
  "Minimal wrapper for Terraform state JSON format."

  def __init__(self, raw):
    super(TerraformState, self).__init__(raw)
    self.outputs = TerraformValueDict(raw.get('outputs', {}))
    self._resources = None

  @property
  def resources(self):
    if not self._resources:
      resources = {}
      for res in self._raw['resources']:
        name = '%s.%s.%s' % (
            res.get('module'), res.get('type'), res.get('name'))
        resources[name] = res
      self._resources = resources
    return self._resources

  def __getattr__(self, name):
    return self._raw[name]


class TerraformTest(object):
  """Helper class for use in testing Terraform modules.

  This helper class can be used to set up fixtures in Terraform tests, so that
  the usual Terraform commands (init, plan, apply, output, destroy) can be run
  on a module. Configuration is done at instantiation first, by passing in the
  Terraform root module path, and then in the setup method through files that
  will be temporarily linked in the module, and Terraform variables.

  The standard way of using this is by calling setup to configure the module
  through temporarily linked Terraform files and variables, run one or more
  Terraform commands, then check command output, state, or created resources
  from individual tests.

  The local .terraform directory (including local state) and any linked file
  are removed when the instance is garbage collected. Destroy needs to be
  called explicitly using destroy().

  Args:
    tfdir: the Terraform module directory to test, either an absolute path, or
      relative to basedir.
    basedir: optional base directory to use for relative paths, defaults to the
      directory above the one this module lives in.
    terraform: path to the Terraform command.
    env: a dict with custom environment variables to pass to terraform.
  """

  def __init__(self, tfdir, basedir=None, binary='terraform', env=None):
    """Set Terraform folder to operate on, and optional base directory."""
    self._basedir = basedir or os.getcwd()
    self.binary = binary
    self.tfdir = self._abspath(tfdir)
    self.env = os.environ.copy()
    if env is not None:
      self.env.update(env)

  @classmethod
  def _cleanup(cls, tfdir, filenames, binary, deep=True):
    """Remove linked files, .terraform and/or .terragrunt-cache folder at instance deletion."""
    _LOGGER.debug('cleaning up %s %s', tfdir, filenames)
    for filename in filenames:
      path = os.path.join(tfdir, filename)
      if os.path.islink(path):
        os.unlink(path)
    if not deep:
      return
    
    if binary == 'terraform':
      path = os.path.join(tfdir, '.terraform')
      if os.path.isdir(path):
        shutil.rmtree(path)
      path = os.path.join(tfdir, 'terraform.tfstate')
      if os.path.isfile(path):
        os.unlink(path)
    else:
      path = os.path.join(tfdir, '.terragrunt-cache')
      if os.path.isdir(path):
        shutil.rmtree(path)
  
  def tg_global_doc(tg_func):
    doc = """
  terragrunt-config: Path to the Terragrunt config file. Default is terragrunt.hcl.
  terragrunt-tfpath: Path to the Terraform binary. Default is terraform (on PATH).
  terragrunt-no-auto-init: Don't automatically run 'terraform init' during other terragrunt commands. You must run 'terragrunt init' manually.
  terragrunt-no-auto-retry: Don't automatically re-run command in case of transient errors.
  terragrunt-non-interactive: Assume "yes" for all prompts.
  terragrunt-working-dir: The path to the Terraform templates. Default is current directory.
  terragrunt-download-dir: The path where to download Terraform code. Default is .terragrunt-cache in the working directory.
  terragrunt-source: Download Terraform configurations from the specified source into a temporary folder, and run Terraform in that temporary folder.
  terragrunt-source-update: Delete the contents of the temporary folder to clear out any old, cached source code before downloading new source code into it.
  terragrunt-iam-role: Assume the specified IAM role before executing Terraform. Can also be set via the TERRAGRUNT_IAM_ROLE environment variable.
  terragrunt-ignore-dependency-errors: *-all commands continue processing components even if a dependency fails.
  terragrunt-ignore-dependency-order: *-all commands will be run disregarding the dependencies
  terragrunt-ignore-external-dependencies: *-all commands will not attempt to include external dependencies
  terragrunt-include-external-dependencies:  *-all commands will include external dependencies
  terragrunt-parallelism:  *-all commands parallelism set to at most N modules
  terragrunt-exclude-dir: Unix-style glob of directories to exclude when running *-all commands
  terragrunt-include-dir: Unix-style glob of directories to include when running *-all commands
  terragrunt-check: Enable check mode in the hclfmt command.
  terragrunt-hclfmt-file: The path to a single terragrunt.hcl file that the hclfmt command should run on.
  terragrunt-override-attr: A key=value attribute to override in a provider block as part of the aws-provider-patch command. May be specified multiple times.
  terragrunt-debug: Write terragrunt-debug.tfvars to working folder to help root-cause issues.
    """
    tg_func.__doc__ += doc
    return tg_func

  def _abspath(self, path):
    """Make relative path absolute from base dir."""
    
    # print(inspect.getdoc(self.setup))
    return path if path.startswith('/') else os.path.join(self._basedir, path)

  def setup(self, extra_files=None, plugin_dir=None, init_vars=None,
            backend=True, cleanup_on_exit=True):
    """Setup method to use in test fixtures.

    This method prepares a new Terraform environment for testing the module
    specified at init time, and returns init output.

    Args:
      extra_files: list of absolute or relative to base paths to be linked in
        the root module folder
      plugin_dir: path to a plugin directory to be used for Terraform init, eg
        built with terraform-bundle
      init_vars: Terraform backend configuration variables
      backend: Terraform backend argument
      cleanup_on_exit: remove .terraform and terraform.tfstate files on exit

    Returns:
      Terraform init output.
    """
    # link extra files inside dir
    filenames = []
    for link_src in (extra_files or []):
      link_src = self._abspath(link_src)
      filename = os.path.basename(link_src)
      if os.path.isfile(link_src):
        link_dst = os.path.join(self.tfdir, filename)
        try:
          os.symlink(link_src, link_dst)
        except FileExistsError as e:  # pylint:disable=undefined-variable
          _LOGGER.warning(e)
        else:
          _LOGGER.debug('linked %s', link_src)
          filenames.append(filename)
      else:
        _LOGGER.warning('no such file {}'.format(link_src))
    self._finalizer = weakref.finalize(
        self, self._cleanup, self.tfdir, filenames, self.binary, deep=cleanup_on_exit)
    if self.binary == 'terraform':
      return self.tf_init(plugin_dir=plugin_dir, init_vars=init_vars, backend=backend)
    else:
      return self.tg_init(plugin_dir=plugin_dir, init_vars=init_vars, backend=backend)

  def _plan(self, output=False, *cmd):
    """
    cmd: Terragrunt/Terraform plan command (plan|plan-all|run-all, plan)
    """
    cmd_args = parse_args(**kw)
    if not output:
      return self.execute_command(*cmd, *cmd_args).out

    if output:
      with tempfile.NamedTemporaryFile() as fp:
        cmd_args.append('-out={}'.format(fp.name))
        kw['out'] = fp.name

    self.execute_command(*cmd, *cmd_args)
    if cmd == ['run-all', 'plan']:
      return self.execute_command('run-all', 'show' *cmd_args)
    else:
      return self.execute_command('show', *cmd_args)
  
  def tf_init(self, input=False, no_color=True, plugin_dir=None,
           init_vars=None, backend=True):
    """Run Terraform or Terragrunt init command."""
    cmd_args = parse_args(locals())
    print('cmd_args: ', cmd_args)
    return self.execute_command('init', *cmd_args).out

  @tg_global_doc
  def tg_init(self, all=False, input=False, no_color=True, plugin_dir=None,
              init_vars=None, backend=True, **kw):
    """Run Terragrunt init command."""
    cmd_args = parse_args(input=input, no_color=no_color, backend=backend,
                           plugin_dir=plugin_dir,
                          init_vars=init_vars)
    if all:
      return self.execute_command('run-all', 'init', *cmd_args).out
    else:
      return self.execute_command('init', *cmd_args).out

  def tf_validate(self, no_color=True, json=None):
    """Run Terraform or Terragrunt validate command."""
    cmd_args = parse_args(no_color=True, json=None)
    return self.execute_command('validate', *cmd_args).out

  def tg_validate(self, no_color=True, json=None, **kw):
    """Run Terraform run-all validate command."""
    cmd_args = parse_args(no_color=True, json=None)
    return self.execute_command('run-all', 'validate', *cmd_args).out

  def plan(self, input=False, no_color=True, refresh=True, tf_vars=None, targets=None, output=False, tf_var_file=None):
    """Run Terraform plan command, optionally returning parsed plan output.""" 
    result = self._plan('plan', input=False, no_color=True, refresh=True, tf_vars=None, targets=None, output=False, tf_var_file=None)

    try:
      return TerraformPlanOutput(json.loads(result.out))
    except json.JSONDecodeError as e:
      raise TerraformTestError('Error decoding plan output: {}'.format(e))

  def tg_plan_all(self, input=False, no_color=True, refresh=True, tf_vars=None, targets=None, output=False, tf_var_file=None):
    """
    Run Terragrunt plan all command, optionally returning parsed plan output.
    """
    result = self._plan('run-all', 'plan', input=False, no_color=True, refresh=True, tf_vars=None, targets=None, output=False, tf_var_file=None)
    
    if output:
      #TODO: Find better way to parse result other than regex
      plans = re.split('\n(?=\\{"format_version"\\:)', result.out)
      output_dict = []
      for plan in plans:
        try:
          out = TerraformPlanOutput(json.loads(plan))  
          #TODO: Find a way to distinguish each plan from each other (couldn't find an attr in `out` to use as a key to pair with `out` value)   
          # for now returns list of tftest.TerraformPlanModule objects
          output.append(out.root_module)
        except json.JSONDecodeError as e:
          raise TerraformTestError('Error decoding plan output: {}'.format(e))
      
      return output_dict

  def tf_apply(self, input=False, no_color=True, auto_approve=True, tf_vars=None, targets=None, tf_var_file=None):
    """Run Terraform or Terragrunt apply command."""
    cmd_args = parse_args(input=False, no_color=True, 
                          auto_approve=True, tf_vars=None, 
                          targets=None, tf_var_file=None)
    return self.execute_command('apply', *cmd_args).out

  def tg_apply_all(self, input=False, no_color=True, auto_approve=True, tf_vars=None, targets=None, tf_var_file=None, **kw):
    """Run Terraform or Terragrunt apply command."""
    cmd_args = parse_args(input=False, no_color=True, 
                          auto_approve=True, tf_vars=None, 
                          targets=None, tf_var_file=None)
    return self.execute_command('run-all', 'apply', *cmd_args).out

  def _output_args(self, name, **kw):
    cmd_args = parse_args(**kw)
    if name:
      cmd_args.append(name)
    return cmd_args

  def tf_output(self, name=None, no_color=True, json_format=True):
    """Run Terraform or Terragrunt output command."""
    cmd_args = _output_args(name, color, json_format)
    output = self.execute_command('output', *cmd_args).out
    _LOGGER.debug('output %s', output)
    if json_format:
      try:
        output = TerraformValueDict(json.loads(output))
      except json.JSONDecodeError as e:
        _LOGGER.warning('error decoding output: {}'.format(e))
    return output

  def destroy(self, **kw):
    """Run Terraform destroy command."""
    cmd_args = parse_args(**kw)
    return self.execute_command('destroy', *cmd_args).out

  def refresh(self, **kw):
    """Run Terraform refresh command."""
    cmd_args = parse_args(**kw)
    return self.execute_command('refresh', *cmd_args).out

  def state_pull(self):
    """Pull state."""
    state = self.execute_command('state', 'pull')
    try:
      state = TerraformState(json.loads(state.out))
    except json.JSONDecodeError as e:
      _LOGGER.warning('error decoding state: {}'.format(e))
    return state

  def execute_command(self, cmd, *cmd_args):
    """Run arbitrary Terraform command."""
    _LOGGER.debug([cmd, cmd_args])
    cmdline = [self.binary, cmd]
    cmdline += cmd_args
    print(cmdline)
    try:
      p = subprocess.Popen(cmdline, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, cwd=self.tfdir, env=self.env)
    except FileNotFoundError as e:
      raise TerraformTestError('Terraform executable not found: %s' % e)
    out, err = p.communicate()
    out = out.decode('utf-8', errors='ignore')
    err = err.decode('utf-8', errors='ignore')
    retcode = p.returncode
    if retcode == 1:
      message = 'Error running command {command}: {retcode} {out} {err}'.format(
          command=cmd, retcode=retcode, out=out, err=err)
      _LOGGER.critical(message)
      raise TerraformTestError(message)
    return TerraformCommandOutput(retcode, out, err)
