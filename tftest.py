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

__version__ = '1.5.4'

_LOGGER = logging.getLogger('tftest')


TerraformCommandOutput = collections.namedtuple(
    'TerraformCommandOutput', 'retcode out err')

TerraformStateResource = collections.namedtuple(
    'TerraformStateResource', 'key provider type attributes depends_on raw')


class TerraformTestError(Exception):
  pass


def parse_args(init_vars=None, tf_vars=None, targets=None, **kw):
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
  if kw.get('auto_approve'):
    cmd_args.append('-auto-approve')
  if kw.get('backend') is False:
    cmd_args.append('-backend=false')
  if kw.get('color') is False:
    cmd_args.append('-no-color')
  if kw.get('force_copy'):
    cmd_args.append('-force-copy')
  if kw.get('input') is False:
    cmd_args.append('-input=false')
  if kw.get('json_format') is True:
    cmd_args.append('-json')
  if kw.get('lock') is False:
    cmd_args.append('-lock=false')
  if kw.get('plugin_dir'):
    cmd_args += ['-plugin-dir', kw['plugin_dir']]
  if kw.get('refresh') is False:
    cmd_args.append('-refresh=false')
  if isinstance(init_vars, dict):
    cmd_args += ['-backend-config={}={}'.format(k, v)
                 for k, v in init_vars.items()]
  elif isinstance(init_vars, str):
    cmd_args += ['-backend-config', '{}'.format(init_vars)]
  if tf_vars:
    cmd_args += list(itertools.chain.from_iterable(
        ("-var", "{}={}".format(k, v)) for k, v in tf_vars.items()
    ))
  if targets:
    cmd_args += [("-target={}".format(t)) for t in targets]
  if kw.get('tf_var_file'):
    cmd_args.append('-var-file={}'.format(kw['tf_var_file']))
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

  def __init__(self, tfdir, basedir=None, terraform='terraform', env=None):
    """Set Terraform folder to operate on, and optional base directory."""
    self._basedir = basedir or os.getcwd()
    self.terraform = terraform
    self.tfdir = self._abspath(tfdir)
    self.env = os.environ.copy()
    if env is not None:
      self.env.update(env)

  @classmethod
  def _cleanup(cls, tfdir, filenames, deep=True):
    """Remove linked files and .terraform folder at instance deletion."""
    _LOGGER.debug('cleaning up %s %s', tfdir, filenames)
    for filename in filenames:
      path = os.path.join(tfdir, filename)
      if os.path.islink(path):
        os.unlink(path)
    if not deep:
      return
    path = os.path.join(tfdir, '.terraform')
    if os.path.isdir(path):
      shutil.rmtree(path)
    path = os.path.join(tfdir, 'terraform.tfstate')
    if os.path.isfile(path):
      os.unlink(path)

  def _abspath(self, path):
    """Make relative path absolute from base dir."""
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
        self, self._cleanup, self.tfdir, filenames, deep=cleanup_on_exit)
    return self.init(plugin_dir=plugin_dir, init_vars=init_vars, backend=backend)

  def init(self, input=False, color=False, force_copy=False, plugin_dir=None,
           init_vars=None, backend=True):
    """Run Terraform init command."""
    cmd_args = parse_args(input=input, color=color, backend=backend,
                          force_copy=force_copy, plugin_dir=plugin_dir,
                          init_vars=init_vars)
    return self.execute_command('init', *cmd_args).out

  def plan(self, input=False, color=False, refresh=True, tf_vars=None, targets=None, output=False, tf_var_file=None):
    "Run Terraform plan command, optionally returning parsed plan output."
    cmd_args = parse_args(input=input, color=color,
                          refresh=refresh, tf_vars=tf_vars,
                          targets=targets,  tf_var_file=tf_var_file)
    if not output:
      return self.execute_command('plan', *cmd_args).out
    with tempfile.NamedTemporaryFile() as fp:
      cmd_args.append('-out={}'.format(fp.name))
      self.execute_command('plan', *cmd_args)
      result = self.execute_command('show', '-no-color', '-json', fp.name)
    try:
      return TerraformPlanOutput(json.loads(result.out))
    except json.JSONDecodeError as e:
      raise TerraformTestError('Error decoding plan output: {}'.format(e))

  def apply(self, input=False, color=False, auto_approve=True, tf_vars=None, targets=None, tf_var_file=None):
    """Run Terraform apply command."""
    cmd_args = parse_args(input=input, color=color,
                          auto_approve=auto_approve, tf_vars=tf_vars,
                          targets=targets, tf_var_file=tf_var_file)
    return self.execute_command('apply', *cmd_args).out

  def output(self, name=None, color=False, json_format=True):
    """Run Terraform output command."""
    cmd_args = []
    if name:
      cmd_args.append(name)
    cmd_args += parse_args(color=color, json_format=json_format)
    output = self.execute_command('output', *cmd_args).out
    _LOGGER.debug('output %s', output)
    if json_format:
      try:
        output = TerraformValueDict(json.loads(output))
      except json.JSONDecodeError as e:
        _LOGGER.warning('error decoding output: {}'.format(e))
    return output

  def destroy(self, color=False, auto_approve=True, tf_vars=None, targets=None, tf_var_file=None):
    """Run Terraform destroy command."""
    cmd_args = parse_args(color=color, auto_approve=auto_approve,
                          tf_vars=tf_vars, targets=targets,
                          tf_var_file=tf_var_file)
    return self.execute_command('destroy', *cmd_args).out

  def refresh(self, color=False, lock=False, tf_vars=None, targets=None):
    """Run Terraform refresh command."""
    cmd_args = parse_args(color=color, lock=lock,
                          tf_vars=tf_vars, targets=targets)
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
    cmdline = [self.terraform, cmd]
    cmdline += cmd_args
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
