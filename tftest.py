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
import glob
import inspect
import itertools
import json
import logging
import os
import pickle
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import weakref

from functools import partial
from hashlib import sha1
from pathlib import Path
from typing import List

__version__ = '1.7.5'

_LOGGER = logging.getLogger('tftest')

TerraformCommandOutput = collections.namedtuple('TerraformCommandOutput',
                                                'retcode out err')

TerraformStateResource = collections.namedtuple(
    'TerraformStateResource', 'key provider type attributes depends_on raw')


class TerraformTestError(Exception):

  @property
  def cmd_error(self):
    return self.args[1] if len(self.args) > 1 else None


_TG_BOOL_ARGS = [
    "no_auto_init",
    "no_auto_retry",
    "source_update",
    "ignore_dependency_errors",
    "ignore_dependency_order",
    "include_external_dependencies",
    "check",
    "debug",
    'non_interactive',
    'ignore_external_dependencies',
]

_TG_KV_ARGS = [
    "iam_role",
    "config",
    "tfpath",
    "working_dir",
    "download_dir",
    "source",
    "exclude_dir",
    "include_dir",
    "hclfmt_file",
]


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

  cmd_args += [
      f'--terragrunt-{arg.replace("_", "-")}' for arg in _TG_BOOL_ARGS
      if kw.get(f"tg_{arg}")
  ]
  for arg in _TG_KV_ARGS:
    if kw.get(f"tg_{arg}"):
      cmd_args += [f'--terragrunt-{arg.replace("_", "-")}',
                   kw[f"tg_{arg}"]]
  if kw.get('tg_parallelism'):
    cmd_args.append(f'--terragrunt-parallelism {kw["tg_parallelism"]}')
  if isinstance(kw.get('tg_override_attr'), dict):
    cmd_args += [
        '--terragrunt-override-attr={}={}'.format(k, v)
        for k, v in kw.get('tg_override_attr').items()
    ]

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
  if kw.get('upgrade'):
    cmd_args.append('-upgrade')
  if isinstance(init_vars, dict):
    cmd_args += [
        '-backend-config={}={}'.format(k, v) for k, v in init_vars.items()
    ]
  elif isinstance(init_vars, str):
    cmd_args += ['-backend-config', '{}'.format(init_vars)]
  if tf_vars:
    cmd_args += list(
        itertools.chain.from_iterable(
            ("-var", "{}={}".format(k, v)) for k, v in tf_vars.items()))
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
    if isinstance(name, str) and name[:2] == name[-2:] == '__':
      # skip non-existing dunder method lookups
      raise AttributeError(name)
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
      self._modules = dict(
          (mod['address'][self._strip:], TerraformPlanModule(mod))
          for mod in self._raw.get('child_modules', {}))
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
    self.root_module = TerraformPlanModule(planned_values.get(
        'root_module', {}))
    self.outputs = TerraformValueDict(planned_values.get('outputs', {}))
    self.resource_changes = dict(
        (v['address'], v) for v in self._raw.get('resource_changes', {}))
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

  def __getstate__(self):
    return self.__dict__

  def __setstate__(self, d):
    self.__dict__.update(d)


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
        name = '%s.%s.%s' % (res.get('module'), res.get('type'),
                             res.get('name'))
        resources[name] = res
      self._resources = resources
    return self._resources

  def __getattr__(self, name):
    return self._raw[name]

  def __getstate__(self):
    return self.__dict__

  def __setstate__(self, d):
    self.__dict__.update(d)


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
    binary: path to the Terraform command.
    env: a dict with custom environment variables to pass to terraform.
    enable_cache: Determines if the caching enabled for specific methods
    cache_dir: optional base directory to use for caching, defaults to
      the directory of the python file that instantiates this class
  """

  def __init__(self, tfdir, basedir=None, binary='terraform', env=None,
               enable_cache=False, cache_dir=None):
    """Set Terraform folder to operate on, and optional base directory."""
    self._basedir = basedir or os.getcwd()
    self.binary = binary
    self.tfdir = self._abspath(tfdir)
    self._env = env or {}
    self.env = os.environ.copy()
    self.tg_run_all = False
    self._plan_formatter = lambda out: TerraformPlanOutput(json.loads(out))
    self._output_formatter = lambda out: TerraformValueDict(
        json.loads(out))
    self.enable_cache = enable_cache
    if not cache_dir:
      self.cache_dir = Path(os.path.dirname(
          inspect.stack()[1].filename)) / ".tftest-cache"
    else:
      self.cache_dir = Path(cache_dir)
    if env is not None:
      self.env.update(env)

  @classmethod
  def _cleanup(cls, tfdir, filenames, deep=True, restore_files=False):
    """Remove linked files, .terraform and/or .terragrunt-cache folder at instance deletion."""

    def remove_readonly(func, path, excinfo):
      _LOGGER.warning(f'Issue deleting file {path}, caused by {excinfo}')
      os.chmod(path, stat.S_IWRITE)
      func(path)

    _LOGGER.debug('cleaning up %s %s', tfdir, filenames)
    for filename in filenames:
      path = os.path.join(tfdir, filename)
      os.unlink(path)
    if not deep:
      return
    path = os.path.join(tfdir, '.terraform')
    if os.path.isdir(path):
      shutil.rmtree(path, onerror=remove_readonly)
    path = os.path.join(tfdir, 'terraform.tfstate')
    if os.path.isfile(path):
      os.unlink(path)
    path = os.path.join(tfdir, '**', '.terragrunt-cache*')
    for tg_dir in glob.glob(path, recursive=True):
      if os.path.isdir(tg_dir):
        shutil.rmtree(tg_dir, onerror=remove_readonly)
    _LOGGER.debug(
        'Restoring original TF files after prevent destroy changes')
    if restore_files:
      for bkp_file in Path(tfdir).rglob('*.bkp'):
        try:
          shutil.copy(str(bkp_file),
                      f'{str(bkp_file).strip(".bkp")}')
        except (IOError, OSError):
          _LOGGER.exception(
              f'Unable to restore terraform file {bkp_file.resolve()}')
          raise TerraformTestError(
              f'Restore of terraform file ({bkp_file.resolve()}) failed')
        else:
          bkp_file.unlink(True)

  def _abspath(self, path):
    """Make relative path absolute from base dir."""
    return path if os.path.isabs(path) else os.path.join(self._basedir, path)

  def _dirhash(self, directory, hash, ignore_hidden=False, excluded_extensions=[]):
    assert Path(directory).is_dir()
    for path in sorted(Path(directory).iterdir(), key=lambda p: str(p).lower()):
      if path.is_file():
        if not ignore_hidden and path.basename().startswith("."):
          continue
        if path.suffix in excluded_extensions:
          continue
        with open(path, "rb") as f:
          for chunk in iter(lambda: f.read(4096), b""):
            hash.update(chunk)
      elif path.is_dir():
        hash = self._dirhash(path, hash)
    return hash

  def _cache(func):

    def cache(self, **kwargs):
      """
      Runs the tftest instance method or retreives the cache value if it exists

      Args:
          kwargs: Keyword argument that are passed to the decorated method
      Returns:
          Output of the tftest instance method
      """
      _LOGGER.info("Cache decorated method: %s", func.__name__)

      if not self.enable_cache:
        return func(self, **kwargs)
      elif not kwargs.get("use_cache", False):
        return func(self, **kwargs)

      cache_dir = self.cache_dir / \
          Path(self.tfdir.strip("/")) / Path(func.__name__)
      # creates cache dir if not exists
      cache_dir.mkdir(parents=True, exist_ok=True)

      params = {
          **{
              k: v for k, v in self.__dict__.items()
              # only uses instance attributes that are involved in the results of
              # the decorated method
              if k in ["binary", "_basedir", "tfdir", "_env"]
          },
          **kwargs,
      }

      # creates hash of file contents
      for path_param in ["extra_files", "tf_var_file"]:
        if path_param in kwargs:
          if isinstance(kwargs[path_param], list):
            params[path_param] = [
                sha1(open(fp, 'rb').read()).hexdigest() for fp in kwargs[path_param]]
          else:
            params[path_param] = sha1(
                open(kwargs[path_param], 'rb').read()).hexdigest()

      # creates hash of all file content within tfdir
      # excludes hidden files from being used within hash (ignores .terraform/ or .terragrunt-cache/)
      # and excludes any local tfstate files

      params["tfdir"] = self._dirhash(
          self.tfdir, sha1(), ignore_hidden=True, excluded_extensions=['.backup', '.tfstate']).hexdigest()

      hash_filename = sha1(
          json.dumps(params, sort_keys=True,
                     default=str).encode("cp037")).hexdigest() + ".pickle"
      cache_key = cache_dir / hash_filename
      _LOGGER.debug("Cache key: %s", cache_key)

      try:
        f = cache_key.open("rb")
      except OSError:
        _LOGGER.debug("Could not read cache path")
      else:
        _LOGGER.info("Getting output from cache")
        return pickle.load(f)

      _LOGGER.info("Running command")
      out = func(self, **kwargs)

      if out:
        _LOGGER.info("Writing command to cache")
        try:
          f = cache_key.open("wb")
        except OSError as e:
          _LOGGER.error("Cache could not write path")
        else:
          with f:
            pickle.dump(out, f, pickle.HIGHEST_PROTOCOL)

      return out

    return cache

  @_cache
  def setup(self, extra_files=None, plugin_dir=None, init_vars=None,
            backend=True, cleanup_on_exit=True, disable_prevent_destroy=False,
            workspace_name=None, use_cache=False, **kw):
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
      disable_prevent_destroy: set all prevent destroy to false
      workspace_name: name of workspace to create or select

    Returns:
      Terraform init output.
    """
    # remove lifecycle prevent destroy
    if disable_prevent_destroy:
      min_python = (3, 5)
      if sys.version_info < min_python:
        raise TerraformTestError(
            'The disable_prevent_destroy flag requires at least Python 3.5')
      for tf_file in Path(self.tfdir).rglob('*.tf'):
        try:
          shutil.copy(str(tf_file), f'{str(tf_file)}.bkp')
        # except (OSError, IOError) as exc:
        except (OSError, IOError):
          _LOGGER.exception(
              f'Unable to backup terraform file {tf_file.resolve()}')
          raise TerraformTestError(
              f'Backup of terraform file ({tf_file.resolve()}) failed')
        try:
          with open(tf_file, 'r') as src:
            terraform = src.read()
          with open(tf_file, 'w') as src:
            terraform = re.sub(r'prevent_destroy\s+=\s+true',
                               'prevent_destroy = false', terraform)
            src.write(terraform)
        except (OSError, IOError):
          _LOGGER.exception(
              f'Unable to update prevent_destroy in file {tf_file.resolve()}')
          raise TerraformTestError(
              f'Unable to update prevent_destroy in file ({tf_file.resolve()}) failed'
          )

    # link extra files inside dir
    filenames = []
    for link_src in (extra_files or []):
      link_src = self._abspath(link_src)
      filename = os.path.basename(link_src)
      if os.path.isfile(link_src):
        link_dst = os.path.join(self.tfdir, filename)
        try:
          if os.name == 'nt':
            shutil.copy(link_src, link_dst)
          else:
            os.symlink(link_src, link_dst)
          filenames.append(filename)
        except FileExistsError as e:  # pylint:disable=undefined-variable
          _LOGGER.warning(e)
        else:
          _LOGGER.debug('linked %s', link_src)
      else:
        _LOGGER.warning('no such file {}'.format(link_src))
    self._finalizer = weakref.finalize(self, self._cleanup, self.tfdir,
                                       filenames, deep=cleanup_on_exit,
                                       restore_files=disable_prevent_destroy)
    setup_output = self.init(plugin_dir=plugin_dir, init_vars=init_vars,
                             backend=backend, use_cache=use_cache, **kw)
    if workspace_name:
      setup_output += self.workspace(name=workspace_name)
    return setup_output

  @_cache
  def init(self, input=False, color=False, force_copy=False, plugin_dir=None,
           init_vars=None, backend=True, use_cache=False, **kw):
    """Run Terraform init command."""
    cmd_args = parse_args(input=input, color=color, backend=backend,
                          force_copy=force_copy, plugin_dir=plugin_dir,
                          init_vars=init_vars, **kw)
    return self.execute_command('init', *cmd_args).out

  def workspace(self, name=None):
    """Run Terraform workspace command."""
    raw_ws_out = self.execute_command('workspace', *['list']).out
    cmd_args = ['select', name]
    if name not in [
        ws.replace('*', '').strip()
        for ws in raw_ws_out.split('\n')
        if len(ws) > 0
    ]:
      cmd_args = ['new', name]
    return self.execute_command('workspace', *cmd_args).out

  @_cache
  def plan(self, input=False, color=False, refresh=True, tf_vars=None,
           targets=None, output=False, tf_var_file=None, use_cache=False, **kw):
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
    cmd_args = parse_args(input=input, color=color, refresh=refresh,
                          tf_vars=tf_vars, targets=targets,
                          tf_var_file=tf_var_file, **kw)
    if not output:
      return self.execute_command('plan', *cmd_args).out
    with tempfile.NamedTemporaryFile() as fp:
      fp.close()
    # for tg we need to specify a temp name that is relative for the output to go into each
    # of the .terragrunt-cache, then plan / show would work, otherwise it overwrites each other!
    temp_file = fp.name if len(self._tg_ra()) == 0 else os.path.basename(
        fp.name)
    cmd_args.append('-out={}'.format(temp_file))
    self.execute_command('plan', *cmd_args)
    result = self.execute_command('show', '-no-color', '-json', temp_file)
    try:
      return self._plan_formatter(result.out)
    except json.JSONDecodeError as e:
      raise TerraformTestError(
          'Error decoding plan output: {}'.format(e))

  @_cache
  def apply(self, input=False, color=False, auto_approve=True, tf_vars=None,
            targets=None, tf_var_file=None, use_cache=False, **kw):
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
    cmd_args = parse_args(input=input, color=color, auto_approve=auto_approve,
                          tf_vars=tf_vars, targets=targets,
                          tf_var_file=tf_var_file, **kw)
    return self.execute_command('apply', *cmd_args).out

  @_cache
  def output(self, name=None, color=False, json_format=True, use_cache=False,
             **kw):
    """Run Terraform output command."""
    cmd_args = []
    if name:
      cmd_args.append(name)
    cmd_args += parse_args(color=color, json_format=json_format, **kw)
    output = self.execute_command('output', *cmd_args).out
    _LOGGER.debug('output %s', output)
    if json_format:
      try:
        output = self._output_formatter(output)
      except json.JSONDecodeError as e:
        _LOGGER.warning('error decoding output: {}'.format(e))
    return output

  @_cache
  def destroy(self, color=False, auto_approve=True, tf_vars=None, targets=None,
              tf_var_file=None, use_cache=False, **kw):
    """Run Terraform destroy command."""
    cmd_args = parse_args(color=color, auto_approve=auto_approve,
                          tf_vars=tf_vars, targets=targets,
                          tf_var_file=tf_var_file, **kw)
    return self.execute_command('destroy', *cmd_args).out

  def refresh(self, color=False, lock=False, tf_vars=None, targets=None, **kw):
    """Run Terraform refresh command."""
    cmd_args = parse_args(color=color, lock=lock, tf_vars=tf_vars,
                          targets=targets, **kw)
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
    cmdline = [self.binary, *self._tg_ra(), cmd]
    cmdline += cmd_args
    _LOGGER.info(cmdline)
    retcode = None
    full_output_lines = []
    try:
      p = subprocess.Popen(cmdline, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, cwd=self.tfdir, env=self.env,
                           universal_newlines=True, encoding='utf-8',
                           errors='ignore')
      while True:
        output = p.stdout.readline()
        if output == '' and p.poll() is not None:
          break
        if output:
          _LOGGER.info(output.strip())
          full_output_lines.append(output)
      retcode = p.poll()
      p.wait()
    except FileNotFoundError as e:
      raise TerraformTestError('Terraform executable not found: %s' % e)
    out, err = p.communicate()
    full_output = "".join(full_output_lines)
    if retcode in [1, 11]:
      message = 'Error running command {command}: {retcode} {out} {err}'.format(
          command=cmd, retcode=retcode, out=full_output, err=err)
      _LOGGER.critical(message)
      raise TerraformTestError(message, err)
    return TerraformCommandOutput(retcode, full_output, err)

  def _tg_ra(self) -> List[str]:
    """if run_all return ['run-all'] else [] """
    return ['run-all'] if self._is_tg() and self.tg_run_all else []

  def _is_tg(self) -> bool:
    """based on the binary set determines if we are running terragrunt"""
    return self.binary.endswith('terragrunt')


def _parse_run_all_out(output: str, formatter: TerraformJSONBase) -> str:
  """
    run-all output a bunch of jsons back to back in one string(no comma),
    this convert the output to a valid json (put b2b jsons into a list)
  Args:
    output: the back to back jsons in a string
    formatter: output format, could be TerraformValueDict or TerraformPlanOutput
  Returns:
    convert the input into a list that is a valid json
  """
  dicts = json.loads("[" + re.sub(r"\}\s*\{", "}, {", output) + "]")
  return [formatter(d) for d in dicts]


class TerragruntTest(TerraformTest):

  def __init__(self, tfdir, basedir=None, binary='terragrunt', env=None,
               tg_run_all=False, enable_cache=False, cache_dir=None):
    """A helper class that could be used for testing terragrunt

    Most operations that apply to :func:`~TerraformTest` also apply to this class.
    Notice that to use this class for Terragrunt run-all, `tg_run_all` needs to be set to
    True.  The class would then only be used just for run-all.  If you need individual
    Terragrunt module testing, create another instance of this helper with
    tg_run_all=False (default)

    Args:
      tfdir: the Terraform module directory to test, either an absolute path, or
             relative to basedir.
      basedir: optional base directory to use for relative paths, defaults to the
               directory above the one this module lives in.
      binary: (Optional) path to terragrunt command.
      env: a dict with custom environment variables to pass to terraform.
      tg_run_all: whether the test is for terragrunt run-all, default to False
      enable_cache: Determines if the caching enabled for specific methods
      cache_dir: optional base directory to use for caching, defaults to
        the directory of the python file that instantiates this class
    """
    TerraformTest.__init__(self, tfdir, basedir, binary, env, enable_cache,
                           cache_dir)
    self.tg_run_all = tg_run_all
    if self.tg_run_all:
      self._plan_formatter = partial(_parse_run_all_out,
                                     formatter=TerraformPlanOutput)
      self._output_formatter = partial(_parse_run_all_out,
                                       formatter=TerraformValueDict)
