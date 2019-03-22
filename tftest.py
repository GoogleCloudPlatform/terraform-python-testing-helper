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
import weakref

__version__ = '0.3.0'

_LOGGER = logging.getLogger('tftest')


TerraformCommandOutput = collections.namedtuple(
    'TerraformCommandOutput', 'retcode out err')

TerraformStateResource = collections.namedtuple(
    'TerraformStateResource', 'key provider type attributes depends_on raw')


def parse_args(init_vars=None, tf_vars=None, **kw):
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
  if kw.get('color') is False:
    cmd_args.append('-no-color')
  if kw.get('input') is False:
    cmd_args.append('-input=false')
  if kw.get('json_format') is True:
    cmd_args.append('-json')
  if kw.get('lock') is False:
    cmd_args.append('-lock=false')
  if kw.get('plugin_dir'):
    cmd_args += ['-plugin-dir', kw['plugin_dir']]
  if isinstance(init_vars, dict):
    cmd_args += ['-backend-config=\'{}={}\''.format(k, v)
                 for k, v in init_vars.items()]
  elif isinstance(init_vars, str):
    cmd_args += ['-backend-config', '{}'.format(init_vars)]
  if tf_vars:
    cmd_args += list(itertools.chain.from_iterable(
        ("-var", "{}={}".format(k, v)) for k, v in tf_vars.items()
    ))
  return cmd_args


class TerraformTestError(Exception):
  pass


class TerraformJSONBase(object):
  """Base class for JSON wrappers."""

  def __init__(self, raw):
    self.raw = raw

  def __bytes__(self):
    return bytes(self.raw)

  def __len__(self):
    return len(self.raw)

  def __str__(self):
    return str(self.raw)


class TerraformOutputs(TerraformJSONBase):
  """Minimal wrapper to directly expose output values."""

  def __init__(self, raw):
    super(TerraformOutputs, self).__init__(raw)
    self.sensitive = tuple(k for k, v in raw.items() if v.get('sensitive'))

  def __getitem__(self, name):
    return self.raw[name]['value']


class TerraformStateModule(object):
  """Minimal wrapper for Terraform state modules."""

  def __init__(self, path, raw):
    self._raw = raw
    self.path = path
    self.outputs = TerraformOutputs(raw['outputs'])
    self.depends_on = raw['depends_on']
    # key type provider attributes depends_on
    self.resources = {}
    for k, v in raw['resources'].items():
      self.resources[k] = TerraformStateResource(
          k, v['provider'], v['type'],
          v.get('primary', {}).get('attributes', {}), v['depends_on'], v)


class TerraformState(TerraformJSONBase):
  """Minimal wrapper for Terraform state JSON format."""

  def __init__(self, raw):
    super(TerraformState, self).__init__(raw)
    self.modules = {}
    for k, v in raw.items():
      if k != 'modules':
        setattr(self, k, v)
        continue
      for mod in v:
        path = '.'.join(mod['path'])
        self.modules[path] = TerraformStateModule(path, mod)


class TerraformTest(object):
  """Helper class for use in testing Terraform modules.

  This helper class can be used to set up fixtures in Terraform tests, so that
  the usual Terraform commands (init, plan, apply, output, destroy) can be run
  on a module. Configuration is done at instantiation first, by passing in the
  Terraform root module path, and the in the setup method through files that
  will be temporarily linked in the module, and Terraform variables.

  The standard way of using this is by calling setup to configure the module
  through temporarily linked Terraform files and variables, run one or more
  Terraform commands, then check command output, state, or created resources
  from individual tests.

  The local .terraform directory (including local state) and any linked file
  are removed when the instance is garbage collected. Destroy is only called
  from the teardown() method, or on error when using setup with autorun.

  Args:
    tfdir: the Terraform module directory to test, either an absolute path, or
      relative to basedir.
    basedir: optional base directory to use for relative paths, defaults to the
      directory above the one this module lives in.
    terraform: path to the Terraform command.
  """

  def __init__(self, tfdir, basedir=None, terraform='terraform'):
    """Set Terraform folder to operate on, and optional base directory."""
    self._basedir = basedir or os.getcwd()
    self.terraform = terraform
    self.tfdir = self._abspath(tfdir)
    self.setup_output = None

  @classmethod
  def _cleanup(cls, tfdir, filenames):
    """Remove linked files and .terraform folder at instance deletion."""
    _LOGGER.debug('cleaning up %s %s', tfdir, filenames)
    path = os.path.join(tfdir, '.terraform')
    if os.path.isdir(path):
      shutil.rmtree(path)
    path = os.path.join(tfdir, 'terraform.tfstate')
    if os.path.isfile(path):
      os.unlink(path)
    for filename in filenames:
      path = os.path.join(tfdir, filename)
      if os.path.islink(path):
        os.unlink(path)

  def _abspath(self, path):
    """Make relative path absolute from base dir."""
    return path if path.startswith('/') else os.path.join(self._basedir, path)

  def setup(self, extra_files=None, plugin_dir=None, init_vars=None,
            tf_vars=None, command=None, destroy=False):
    """Setup method to use in test fixtures.

    This method prepares a new Terraform environment for testing the module
    specified at init time, and optionally performs the standard sequence of
    Terraform commands so that outputs and state can be accessed from tests.

    Args:
      extra_files: list of absolute or relative to base paths to be linked in
        the root module folder.
      plugin_dir: path to a plugin directory to be used for Terraform init, eg
        built with terraform-bundle.
      init_vars: Terraform backend configuration variables for init.
      tf_vars: Terraform variables for plan and apply.
      command: run Terraform commands in order up to command, default to not
        running any Terraform commands.
      destroy: run destroy in case of errors during apply.

    Returns:
      Wrapped output if apply is run from here.
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
          _LOGGER.warn(e)
        else:
          _LOGGER.debug('linked %s', link_src)
          filenames.append(filename)
      else:
        _LOGGER.warn('no such file {}'.format(link_src))
    self._finalizer = weakref.finalize(
        self, self._cleanup, self.tfdir, filenames)
    if not command:
      return
    self.init(plugin_dir=plugin_dir, init_vars=init_vars)
    self.setup_output = self.run_commands(
        tf_vars=tf_vars, plan=(command == 'plan'),
        output=(command == 'output'), destroy=destroy)
    return self.setup_output

  def run_commands(self, tf_vars=None, plan=False, output=True, destroy=True):
    """Convenience method to run a common set of commands in order.

    This method is used to simpify running the usual suite of plan/apply/output
    in order, and optionally trap errors during apply so destroy is called to
    clean up any leftover resources.

    Args:
      tf_vars: the Terraform variables to use for plan/apply/destroy
      plan: run plan only
      output: run output after apply
      destroy: run destroy if apply raises an error

    Returns:
      Wrapped output if output is run from here.
    """
    if plan:
      return self.plan(tf_vars=tf_vars)
    # catch errors so we can run destroy before re-raising
    try:
      result = self.apply(tf_vars=tf_vars)
    except TerraformTestError:
      if destroy:
        _LOGGER.warn('running teardown to clean up')
        self.teardown(tf_vars)
      raise
    if not output:
      return result
    return self.output()

  def teardown(self, tf_vars=None):
    """Teardown method that runs destroy without raising errors."""
    try:
      self.destroy(tf_vars=tf_vars)
    except TerraformTestError:
      _LOGGER.exception('error in teardown destroy')

  def init(self, input=False, color=False, plugin_dir=None, init_vars=None):
    """Run Terraform init command."""
    cmd_args = parse_args(input=input, color=color,
                          plugin_dir=plugin_dir, init_vars=init_vars)
    return self.execute_command('init', *cmd_args).out

  def plan(self, input=False, color=False, tf_vars=None):
    """Run Terraform plan command."""
    cmd_args = parse_args(input=input, color=color, tf_vars=tf_vars)
    return self.execute_command('plan', *cmd_args).out

  def apply(self, input=False, color=False, auto_approve=True, tf_vars=None):
    """Run Terraform apply command."""
    cmd_args = parse_args(input=input, color=color,
                          auto_approve=auto_approve, tf_vars=tf_vars)
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
        output = TerraformOutputs(json.loads(output))
      except json.JSONDecodeError as e:
        _LOGGER.warn('error decoding output: {}'.format(e))
    return output

  def destroy(self, color=False, auto_approve=True, tf_vars=None):
    """Run Terraform destroy command."""
    cmd_args = parse_args(
        color=color, auto_approve=auto_approve, tf_vars=tf_vars)
    return self.execute_command('destroy', *cmd_args).out

  def refresh(self, color=False, lock=False, tf_vars=None):
    """Run Terraform refresh command."""
    cmd_args = parse_args(
        color=color, lock=lock, tf_vars=tf_vars)
    return self.execute_command('refresh', *cmd_args).out

  def state_pull(self):
    """Pull state."""
    state = self.execute_command('state', 'pull')
    try:
      state = TerraformState(json.loads(state.out))
    except json.JSONDecodeError as e:
      _LOGGER.warn('error decoding state: {}'.format(e))
    return state

  def execute_command(self, cmd, *cmd_args):
    """Run arbitrary Terraform command."""
    _LOGGER.debug([cmd, cmd_args])
    cmdline = [self.terraform, cmd]
    cmdline += cmd_args
    p = subprocess.Popen(cmdline, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         cwd=self.tfdir, env=os.environ.copy())
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
