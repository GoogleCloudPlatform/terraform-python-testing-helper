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

__version__ = '1.5.5'

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

  if kw.get('tg_config'):
    cmd_args += ['--terragrunt-config', kw['tg_config']]
  if kw.get('tg_tfpath'):
    cmd_args += ['--terragrunt-tfpath', kw['tg_tfpath']]
  if kw.get('tg_no_auto_init') == True:
    cmd_args.append('--terragrunt-no-auto-init')
  if kw.get('tg_no_auto_retry') == True:
    cmd_args.append('--terragrunt-no-auto-retry')
  if kw.get('tg_non_interactive'):
    cmd_args.append('--terragrunt-non-interactive')
  if kw.get('tg_working_dir'):
    cmd_args += ['--terragrunt-working-dir', kw['tg_working_dir']]
  if kw.get('tg_download_dir'):
    cmd_args += ['--terragrunt-download-dir', kw['tg_download_dir']]
  if kw.get('tg_source'):
    cmd_args += ['--terragrunt-source', kw['tg_source']]
  if kw.get('tg_source_update') == True:
    cmd_args.append('--terragrunt-source-update')
  if kw.get('tg_iam_role'):
    cmd_args += ['--terragrunt-iam-role', kw['tg_iam_role']]
  if kw.get('tg_ignore_dependency_errors') == True:
    cmd_args.append('--terragrunt-ignore-dependency-errors')
  if kw.get('tg_ignore_dependency_order') == True:
    cmd_args.append('--terragrunt-ignore-dependency-order')
  if kw.get('tg_ignore_external_dependencies'):
    cmd_args.append('--terragrunt-ignore-external-dependencies')
  if kw.get('tg_include_external_dependencies') == False:
    cmd_args.append('--terragrunt-include-external-dependencies')
  if kw.get('tg_parallelism'):
    cmd_args.append('terragrunt-parralism={}'.format(kw['tg_parallelism']))
  if kw.get('tg_exclude_dir'):
    cmd_args += ['--terragrunt-exclude-dir', kw['tg_exclude_dir']]
  if kw.get('tg_include_dir'):
    cmd_args += ['--terragrunt-include-dir', kw['tg_include_dir']]
  if kw.get('tg_check') == True:
    cmd_args.append('--terragrunt-check')
  if kw.get('tg_hclfmt_file'):
    cmd_args += ['--terragrunt-hclfmt-file', kw['tg_hclfmt_file']]
  if isinstance(kw.get('tg_override_attr'), dict):
    cmd_args += ['--terragrunt-override-attr={}={}'.format(k, v)
                 for k, v in kw.get('tg_override_attr').items()]
  if kw.get('tg_debug') == True:
    cmd_args.append('--terragrunt-debug')

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

  def _plan(self, all=False, output=False,  **kw):
    """
    Run Terragrunt or Terraform plan and optionally return the plan output.

    Args:
      all: Runs Terragrunt command on all subfolders if True
      output: Returns the output of the plan command
    """

    cmd_args = parse_args(**kw)

    if 'out' not in kw:
      with tempfile.NamedTemporaryFile() as fp:
        cmd_args.append('-out={}'.format(fp.name))
        kw['out'] = fp.name

    if all:
      result = self.execute_command('run-all', 'plan', *cmd_args).out
      if not output:
        return result
      return self.execute_command('run-all', 'show', '-no-color', '-json', kw['out'])
    else:
      result = self.execute_command('plan', *cmd_args).out
      if not output:
        return result
      return self.execute_command('show', '-no-color', '-json', kw['out'])

  def _abspath(self, path):
    """Make relative path absolute from base dir."""

    # print(inspect.getdoc(self.setup))
    return path if path.startswith('/') else os.path.join(self._basedir, path)

  def setup(self, all=False, extra_files=None, plugin_dir=None, init_vars=None,
            backend=True, cleanup_on_exit=True, tg_non_interactive=False,
            tg_source_update=False, tg_config=None, tg_working_dir=None,
            **kw):
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

    if self.binary == 'terragrunt':
      return self.tg_init(all=all, init_vars=init_vars,
                          backend=backend, plugin_dir=plugin_dir,
                          tg_non_interactive=tg_non_interactive, tg_source_update=tg_source_update,
                          tg_config=tg_config, tg_working_dir=tg_working_dir, **kw)

    return self.tf_init(plugin_dir=plugin_dir, init_vars=init_vars, backend=backend)

  def tf_init(self, input=False, no_color=True, plugin_dir=None,
              init_vars=None, backend=True):
    """Run Terraform or Terragrunt init command."""
    cmd_args = parse_args(input=input, no_color=no_color,
                          backend=backend, plugin_dir=plugin_dir,
                          init_vars=init_vars)
    return self.execute_command('init', *cmd_args).out

  def tg_init(self, all=False, input=False, no_color=True, plugin_dir=None,
              init_vars=None, backend=True, tg_non_interactive=True,
              tg_source_update=False, tg_config=None, tg_working_dir=None, **kw):
    """Run Terragrunt init command."""
    cmd_args = parse_args(input=input, no_color=no_color,
                          backend=backend, plugin_dir=plugin_dir,
                          init_vars=init_vars, tg_non_interactive=tg_non_interactive,
                          tg_source_update=tg_source_update, tg_config=tg_config,
                          tg_working_dir=tg_working_dir, **kw)
    if all:
      return self.execute_command('run-all', 'init', *cmd_args).out
    else:
      return self.execute_command('init', *cmd_args).out

  def validate(self, no_color=True, json=None):
    """Run Terraform or Terragrunt validate command."""
    cmd_args = parse_args(no_color=True, json=None)
    return self.execute_command('validate', *cmd_args).out

  def tg_validate(self, no_color=True, json=None, tg_non_interactive=True,
                  tg_source_update=False, tg_config=None, tg_working_dir=None, **kw):
    """Run Terragrunt validate command."""
    cmd_args = parse_args(no_color=no_color, json=json, tg_non_interactive=tg_non_interactive,
                          tg_source_update=tg_source_update, tg_config=tg_config, tg_working_dir=tg_working_dir, **kw)
    if all:
      return self.execute_command('run-all', 'validate', *cmd_args).out
    else:
      return self.execute_command('validate', *cmd_args).out

  def plan(self, input=False, no_color=True, refresh=True, tf_vars=None,
           targets=None, output=False, tf_var_file=None):
    """
    Run Terraform plan command, optionally returning parsed plan output.

    Args:
      input: Ask for input for variables if not directly set.
      no_color: If specified, output won't contain any color.
      refresh: Update state prior to checking for differences.
      tf_vars: Dict of variables in the Terraform configuration.
      targets: List of resources to target. Operation will be limited to this resource
        and its dependencies
      output: Determines if output will be returned.
      tf_var_file: Path to terraform variable configuration file relative to `self.tfdir`.
    """
    result = self._plan('plan', input=input, no_color=no_color, refresh=refresh,
                        tf_vars=tf_vars, targets=targets, output=output, tf_var_file=tf_var_file)

    try:
      return TerraformPlanOutput(json.loads(result.out))
    except json.JSONDecodeError as e:
      raise TerraformTestError('Error decoding plan output: {}'.format(e))

  def tg_plan(self, all=False, input=False, no_color=True, refresh=True,
              tf_vars=None, targets=None, output=False, tf_var_file=None,
              tg_non_interactive=True, tg_source_update=False, tg_config=None,
              tg_working_dir=None, **kw):
    """
    Run Terragrunt plan command, optionally returning parsed plan output.

    Args:
      input: Ask for input for variables if not directly set.
      no_color: If specified, output won't contain any color.
      refresh: Update state prior to checking for differences.
      tf_vars: Dict of variables in the Terraform configuration.
      targets: List of resources to target. Operation will be limited to this resource
        and its dependencies
      output: Determines if output will be returned.
      tf_var_file: Path to terraform variable configuration file relative to `self.tfdir`.
    """
    result = self._plan(all=all, output=output,
                        input=input, no_color=no_color,
                        refresh=refresh, tf_vars=tf_vars,
                        targets=targets, tf_var_file=tf_var_file,
                        tg_non_interactive=tg_non_interactive, tg_source_update=tg_source_update,
                        tg_config=tg_config, tg_working_dir=tg_working_dir, **kw)
    if not output:
      return result

    if all:
      # TODO: Find better way to parse result other than regex
      plans = re.split('\n(?=\\{"format_version"\\:)', result.out)
      plan_output = []
      for plan in plans:
        try:
          out = TerraformPlanOutput(json.loads(plan))
          # TODO: Find a way to distinguish each plan from each other (couldn't find an attr in `out` to use as a key to pair with `out` value)
          # for now returns list of tftest.TerraformPlanModule objects
          plan_output.append(out)
        except json.JSONDecodeError as e:
          raise TerraformTestError('Error decoding plan output: {}'.format(e))
      return plan_output
    else:
      try:
        return TerraformPlanOutput(json.loads(result.out))
      except json.JSONDecodeError as e:
        raise TerraformTestError('Error decoding plan output: {}'.format(e))

  def apply(self, input=False, no_color=True, auto_approve=True,
            tf_vars=None, targets=None, tf_var_file=None):
    """
    Run Terraform apply command.

    Args:
      input: Ask for input for variables if not directly set.
      no_color: If specified, output won't contain any color.
      auto_approve: Skip interactive approval of plan before applying.
      tf_vars: Dict of variables in the Terraform configuration.
      targets: List of resources to target. Operation will be limited to this resource
        and its dependencies
      tf_var_file: Path to terraform variable configuration file relative to `self.tfdir`.
    """
    cmd_args = parse_args(input=input, no_color=no_color,
                          auto_approve=auto_approve, tf_vars=tf_vars,
                          targets=targets, tf_var_file=tf_var_file)
    return self.execute_command('apply', *cmd_args).out

  def tg_apply(self, all=False, input=False, no_color=True, auto_approve=True, tf_vars=None,
               targets=None, tf_var_file=None, tg_non_interactive=True,
               tg_source_update=False, tg_config=None, tg_working_dir=None, **kw):
    """
    Run Terragrunt apply command.

    Args:
      input: Ask for input for variables if not directly set.
      no_color: If specified, output won't contain any color.
      auto_approve: Skip interactive approval of plan before applying.
      tf_vars: Dict of variables in the Terraform configuration.
      targets: List of resources to target. Operation will be limited to this resource
        and its dependencies
      tf_var_file: Path to terraform variable configuration file relative to `self.tfdir`.
    """
    cmd_args = parse_args(input=input, no_color=no_color,
                          auto_approve=auto_approve, tf_vars=tf_vars,
                          targets=targets, tf_var_file=tf_var_file,
                          tg_non_interactive=tg_non_interactive, tg_source_update=tg_source_update,
                          tg_config=tg_config, tg_working_dir=tg_working_dir, **kw)

    if all:
      return self.execute_command('run-all', 'apply', *cmd_args).out
    else:
      return self.execute_command('apply', *cmd_args).out

  def _output(self, all=False, name=None, **kw):
    cmd_args = parse_args(**kw)
    if name:
      cmd_args.append(name)

    if all:
      output = self.execute_command('run-all', 'output', *cmd_args).out
    else:
      output = self.execute_command('output', *cmd_args).out
    return output

  def output(self, name=None, no_color=True, json_format=True):
    """Run Terraform output command."""
    output = self._output(name=name, no_color=no_color,
                          json_format=json_format)
    _LOGGER.debug('output %s', output)
    if json_format:
      try:
        output = TerraformValueDict(json.loads(output))
      except json.JSONDecodeError as e:
        _LOGGER.warning('error decoding output: {}'.format(e))
    return output

  def tg_output(self, all=False, name=None, no_color=True, json_format=True,
                tg_non_interactive=True, tg_source_update=False, tg_config=None,
                tg_working_dir=None, **kw):
    """Run Terragrunt output command."""
    output = self._output(all=all, name=name, no_color=no_color, json_format=json_format,
                          tg_non_interactive=tg_non_interactive, tg_source_update=tg_source_update,
                          tg_config=tg_config, tg_working_dir=tg_working_dir, **kw)

    # TODO: Figure out how to parse terragrunt run-all output command to return
    #       dict of {directory: output}
    _LOGGER.debug('output %s', output)
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
