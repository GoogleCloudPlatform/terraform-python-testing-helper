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
"""Simple Python wrapper for Terraform and OpenTofu test fixtures.

See documentation in the TerraformTest class for usage. Terraform wrapping
inspired by https://github.com/beelit94/python-terraform
"""

import collections
import collections.abc
import itertools
import json
import logging
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import weakref

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

__version__ = '2.0.0'

_LOGGER = logging.getLogger('tftest')

PathType = Union[str, os.PathLike]

TerraformCommandOutput = collections.namedtuple('TerraformCommandOutput',
                                                'retcode out err')


def _rmtree(path: Path) -> None:
  """Remove a directory tree, clearing read-only bits if needed."""

  def remove_readonly(func: Any, fpath: str, exc: Any) -> None:
    _LOGGER.warning('Issue deleting file %s, caused by %s', fpath, exc)
    os.chmod(fpath, stat.S_IWRITE)
    func(fpath)

  if sys.version_info >= (3, 12):
    shutil.rmtree(path, onexc=remove_readonly)
  else:
    shutil.rmtree(path, onerror=remove_readonly)


class TerraformTestError(Exception):

  @property
  def cmd_error(self) -> Optional[str]:
    return self.args[1] if len(self.args) > 1 else None


def parse_args(init_vars: Optional[Union[Dict[str, Any], PathType]] = None,
               tf_vars: Optional[Dict[str, Any]] = None,
               targets: Optional[Iterable[str]] = None, **kw: Any) -> List[str]:
  """Convert method arguments for use in Terraform commands.

  Args:
    init_vars: dict of key/values converted to -backend-config=k=v form, or
      string/path argument converted to -backend-config arg.
    tf_vars: dict of key/values converted to -var k=v form.
    targets: iterable of resource addresses converted to -target=addr.
    **kw: converted to the appropriate Terraform flag.

  Returns:
    A list of command arguments for use with subprocess.
  """
  cmd_args: List[str] = []

  bool_flags = {
      'auto_approve': '-auto-approve',
      'force_copy': '-force-copy',
      'json_format': '-json',
      'upgrade': '-upgrade',
  }
  for kwarg, flag in bool_flags.items():
    if kw.get(kwarg):
      cmd_args.append(flag)

  inverse_bool_flags = {
      'backend': '-backend=false',
      'color': '-no-color',
      'input': '-input=false',
      'lock': '-lock=false',
      'refresh': '-refresh=false',
  }
  for kwarg, flag in inverse_bool_flags.items():
    if kw.get(kwarg) is False:
      cmd_args.append(flag)

  kv_flags = {
      'parallelism': '-parallelism',
      'plugin_dir': '-plugin-dir',
      'state': '-state',
  }
  for kwarg, flag in kv_flags.items():
    val = kw.get(kwarg)
    if val is not None and val != '':
      cmd_args.extend([flag, str(val)])

  if isinstance(init_vars, dict):
    cmd_args += [f'-backend-config={k}={v}' for k, v in init_vars.items()]
  elif isinstance(init_vars, (str, os.PathLike)):
    cmd_args += ['-backend-config', str(init_vars)]

  if tf_vars:
    cmd_args += list(
        itertools.chain.from_iterable((
            '-var',
            f'{k}={json.dumps(v) if isinstance(v, (dict, list, tuple, bool)) else v}',
        ) for k, v in tf_vars.items()))

  if targets:
    cmd_args += [f'-target={t}' for t in targets]

  if kw.get('tf_var_file'):
    tf_var_file = kw['tf_var_file']
    if isinstance(tf_var_file, (list, tuple)):
      cmd_args += [f'-var-file={v}' for v in tf_var_file]
    else:
      cmd_args.append(f'-var-file={tf_var_file}')

  if kw.get('plan_out'):
    cmd_args.append(f"-out={kw['plan_out']}")

  return cmd_args


class TerraformJSONBase(collections.abc.Mapping):
  """Base class for JSON wrappers."""

  def __init__(self, raw: Dict[str, Any]):
    self._raw = raw

  def __getitem__(self, index: str) -> Any:
    return self._raw[index]

  def __iter__(self):
    return iter(self._raw)

  def __len__(self) -> int:
    return len(self._raw)

  def __str__(self) -> str:
    return str(self._raw)


class TerraformValueDict(TerraformJSONBase):
  """Minimal wrapper to directly expose outputs or variables."""

  def __init__(self, raw: Optional[Dict[str, Any]]):
    raw = raw or {}
    super().__init__(raw)
    # only matters for outputs
    self.sensitive = tuple(
        k for k, v in raw.items() if isinstance(v, dict) and v.get('sensitive'))

  def __getattr__(self, name: str) -> Any:
    if isinstance(name, str) and name.startswith('__') and name.endswith('__'):
      raise AttributeError(name)
    return getattr(self._raw, name)

  def __getitem__(self, name: str) -> Any:
    return self._raw[name].get('value')


class TerraformPlanModule(TerraformJSONBase):
  """Minimal wrapper for parsed plan output modules."""

  def __init__(self, raw: Optional[Dict[str, Any]]):
    raw = raw or {}
    super().__init__(raw)
    prefix = raw.get('address', '')
    self._strip = 0 if not prefix else len(prefix) + 1
    self._modules: Optional[Dict[str, 'TerraformPlanModule']] = None
    self._resources: Optional[Dict[str, Dict[str, Any]]] = None

  @property
  def child_modules(self) -> Dict[str, 'TerraformPlanModule']:
    if self._modules is None:
      self._modules = {
          mod['address'][self._strip:]: TerraformPlanModule(mod)
          for mod in (self._raw.get('child_modules') or [])
      }
    return self._modules

  @property
  def resources(self) -> Dict[str, Dict[str, Any]]:
    if self._resources is None:
      self._resources = {
          res['address'][self._strip:]: res
          for res in (self._raw.get('resources') or [])
      }
    return self._resources


class TerraformPlanOutput(TerraformJSONBase):
  """Minimal wrapper for Terraform plan JSON output."""

  def __init__(self, raw: Optional[Dict[str, Any]]):
    raw = raw or {}
    super().__init__(raw)
    planned_values = raw.get('planned_values') or {}
    self.root_module = TerraformPlanModule(
        planned_values.get('root_module') or {})
    self.outputs = TerraformValueDict(planned_values.get('outputs') or {})
    self.resource_changes = {
        v['address']: v for v in (self._raw.get('resource_changes') or [])
    }
    # there might be no variables defined
    self.variables = TerraformValueDict(raw.get('variables') or {})
    prior_values = (raw.get('prior_state') or {}).get('values') or {}
    self.prior_root_module = TerraformPlanModule(
        prior_values.get('root_module') or {})

  @property
  def resources(self) -> Dict[str, Dict[str, Any]]:
    return self.root_module.resources

  @property
  def modules(self) -> Dict[str, TerraformPlanModule]:
    return self.root_module.child_modules

  @property
  def prior_resources(self) -> Dict[str, Dict[str, Any]]:
    return self.prior_root_module.resources

  def __getattr__(self, name: str) -> Any:
    if isinstance(name, str) and name.startswith('__') and name.endswith('__'):
      raise AttributeError(name)
    try:
      return self._raw[name]
    except KeyError as e:
      raise AttributeError(name) from e


class TerraformState(TerraformJSONBase):
  """Minimal wrapper for Terraform state JSON format."""

  def __init__(self, raw: Optional[Dict[str, Any]]):
    raw = raw or {}
    super().__init__(raw)
    self.outputs = TerraformValueDict(raw.get('outputs') or {})
    self._resources: Optional[Dict[str, Dict[str, Any]]] = None

  @property
  def resources(self) -> Dict[str, Dict[str, Any]]:
    if self._resources is None:
      resources: Dict[str, Dict[str, Any]] = {}
      for res in (self._raw.get('resources') or []):
        parts = [
            res.get('module'),
            'data' if res.get('mode') == 'data' else None,
            res.get('type'),
            res.get('name'),
        ]
        name = '.'.join(p for p in parts if p)
        resources[name] = res
      self._resources = resources
    return self._resources

  def __getattr__(self, name: str) -> Any:
    if isinstance(name, str) and name.startswith('__') and name.endswith('__'):
      raise AttributeError(name)
    try:
      return self._raw[name]
    except KeyError as e:
      raise AttributeError(name) from e


class TerraformTest:
  """Helper class for use in testing Terraform and OpenTofu modules.

  This helper class can be used to set up fixtures in Terraform tests, so that
  the usual commands (init, plan, apply, output, destroy) can be run on a
  module. Configuration is done at instantiation first, by passing in the
  Terraform root module path, and then in the setup method through files or
  directories that will be temporarily linked in the module, and Terraform
  variables.

  Instances can be used as a context manager (`with TerraformTest(...) as tf:`)
  for deterministic cleanup, or cleaned up via `cleanup()`. If neither is used,
  the local .terraform directory (including local state) and any linked files
  are removed when the instance is garbage collected. Cloud resource teardown
  still needs to be called explicitly using `destroy()`.

  Args:
    tfdir: the Terraform module directory to test, either an absolute path, or
      relative to basedir. Stored on `self.tfdir` as an absolute `pathlib.Path`.
    basedir: optional base directory to use for relative paths, defaults to the
      current working directory.
    binary: path or name of the Terraform/OpenTofu command.
    env: a dict with custom environment variables to pass to terraform.
  """

  def __init__(self, tfdir: PathType, basedir: Optional[PathType] = None,
               binary: PathType = 'terraform',
               env: Optional[Dict[str, str]] = None) -> None:
    """Set Terraform folder to operate on, and optional base directory."""
    self._basedir: Path = (Path(basedir).resolve()
                           if basedir is not None else Path.cwd())
    self.binary: PathType = binary
    self.tfdir: Path = self._abspath(tfdir)
    self.env: Dict[str, str] = {
        k: v for k, v in os.environ.items() if k != 'TF_LOG'
    }
    if env is not None:
      self.env.update(env)
    self._plan_formatter = lambda out: TerraformPlanOutput(json.loads(out))
    self._output_formatter = lambda out: TerraformValueDict(json.loads(out))
    self._finalizer: Optional[weakref.finalize] = None
    self._linked_files: List[str] = []
    self._remove_lockfile: Optional[bool] = None
    self._restore_files: bool = False

  def __enter__(self) -> 'TerraformTest':
    return self

  def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
    self.cleanup()

  def cleanup(self) -> None:
    """Run registered cleanup immediately if present."""
    if self._finalizer is not None and self._finalizer.alive:
      self._finalizer()
    self._linked_files.clear()
    self._remove_lockfile = None
    self._restore_files = False

  @classmethod
  def _cleanup(cls, tfdir: Path, filenames: Sequence[str], deep: bool = True,
               restore_files: bool = False,
               remove_lockfile: bool = True) -> None:
    """Remove linked files and Terraform runtime artifacts."""
    _LOGGER.debug('cleaning up %s %s', tfdir, filenames)
    tf_path = Path(tfdir)
    for filename in filenames:
      target = tf_path / filename
      if target.is_symlink() or target.is_file():
        target.unlink(missing_ok=True)
      elif target.is_dir():
        _rmtree(target)

    if not deep:
      return

    terraform_dir = tf_path / '.terraform'
    if terraform_dir.is_dir():
      _rmtree(terraform_dir)

    if remove_lockfile:
      lock_file = tf_path / '.terraform.lock.hcl'
      if lock_file.is_file():
        lock_file.unlink()

    state_file = tf_path / 'terraform.tfstate'
    if state_file.is_file():
      state_file.unlink()

    state_dir = tf_path / 'terraform.tfstate.d'
    if state_dir.is_dir():
      _rmtree(state_dir)

    for backup_path in tf_path.glob('terraform.tfstate.backup*'):
      if backup_path.is_file():
        backup_path.unlink()

    if restore_files and tf_path.is_dir():
      _LOGGER.debug('Restoring original TF files after prevent destroy changes')
      for bkp_file in tf_path.rglob('*.bkp'):
        if '.terraform' in bkp_file.parts:
          continue
        try:
          shutil.copy(str(bkp_file), str(bkp_file.with_suffix('')))
        except OSError as e:
          _LOGGER.exception(
              f'Unable to restore terraform file {bkp_file.resolve()}')
          raise TerraformTestError(
              f'Restore of terraform file ({bkp_file.resolve()}) failed') from e
        else:
          bkp_file.unlink(missing_ok=True)

  def _abspath(self, path: PathType) -> Path:
    """Make relative path absolute from base dir."""
    path_obj = Path(path)
    if path_obj.is_absolute():
      return path_obj
    return self._basedir / path_obj

  def setup(self, extra_files: Optional[Sequence[PathType]] = None,
            plugin_dir: Optional[PathType] = None,
            init_vars: Optional[Union[Dict[str, Any],
                                      PathType]] = None, backend: bool = True,
            cleanup_on_exit: bool = True, disable_prevent_destroy: bool = False,
            workspace_name: Optional[str] = None, **kw: Any) -> str:
    """Setup method to use in test fixtures.

    This method prepares a new Terraform environment for testing the module
    specified at init time, and returns init output.

    Args:
      extra_files: list of absolute or relative to base file or directory paths
        to be linked in the root module folder.
      plugin_dir: path to a plugin directory to be used for Terraform init, eg
        built with terraform-bundle.
      init_vars: Terraform backend configuration variables.
      backend: Terraform backend argument.
      cleanup_on_exit: remove .terraform and terraform.tfstate files on exit.
      disable_prevent_destroy: set all prevent_destroy to false.
      workspace_name: name of workspace to create or select.

    Returns:
      Terraform init output.
    """
    if self._remove_lockfile is None:
      self._remove_lockfile = not (self.tfdir / '.terraform.lock.hcl').is_file()

    if disable_prevent_destroy:
      self._restore_files = True
      if self.tfdir.is_dir():
        for tf_file in self.tfdir.rglob('*.tf'):
          if '.terraform' in tf_file.parts:
            continue
          bkp_file = Path(f'{tf_file}.bkp')
          if not bkp_file.exists():
            try:
              shutil.copy(str(tf_file), str(bkp_file))
            except OSError as e:
              _LOGGER.exception(
                  f'Unable to backup terraform file {tf_file.resolve()}')
              raise TerraformTestError(
                  f'Backup of terraform file ({tf_file.resolve()}) failed'
              ) from e
          try:
            with open(tf_file, 'r', encoding='utf-8') as src:
              terraform = src.read()
            with open(tf_file, 'w', encoding='utf-8') as src:
              terraform = re.sub(r'prevent_destroy\s*=\s*true',
                                 'prevent_destroy = false', terraform)
              src.write(terraform)
          except OSError as e:
            _LOGGER.exception(
                f'Unable to update prevent_destroy in file {tf_file.resolve()}')
            raise TerraformTestError(
                f'Unable to update prevent_destroy in file ({tf_file.resolve()}) failed'
            ) from e

    for link_src in (extra_files or []):
      link_src_path = self._abspath(link_src)
      filename = link_src_path.name
      if link_src_path.exists():
        link_dst = self.tfdir / filename
        try:
          if os.name == 'nt':
            if link_src_path.is_dir():
              shutil.copytree(link_src_path, link_dst)
            else:
              shutil.copy(link_src_path, link_dst)
          else:
            os.symlink(link_src_path, link_dst)
          if filename not in self._linked_files:
            self._linked_files.append(filename)
        except FileExistsError as e:
          _LOGGER.warning(e)
        else:
          _LOGGER.debug('linked %s', link_src_path)
      else:
        _LOGGER.warning('no such file or directory %s', link_src_path)

    if self._finalizer is not None and self._finalizer.alive:
      self._finalizer.detach()
    self._finalizer = weakref.finalize(self, self._cleanup, self.tfdir,
                                       list(self._linked_files),
                                       deep=cleanup_on_exit,
                                       restore_files=self._restore_files,
                                       remove_lockfile=self._remove_lockfile)
    setup_output = self.init(plugin_dir=plugin_dir, init_vars=init_vars,
                             backend=backend, **kw)
    if workspace_name:
      setup_output += self.workspace(name=workspace_name)
    return setup_output

  def init(self, input: bool = False, color: bool = False,
           force_copy: bool = False, plugin_dir: Optional[PathType] = None,
           init_vars: Optional[Union[Dict[str, Any], PathType]] = None,
           backend: bool = True, **kw: Any) -> str:
    """Run Terraform init command."""
    cmd_args = parse_args(input=input, color=color, backend=backend,
                          force_copy=force_copy, plugin_dir=plugin_dir,
                          init_vars=init_vars, **kw)
    return self.execute_command('init', *cmd_args).out

  def workspace(self, name: str) -> str:
    """Run Terraform workspace command."""
    raw_ws_out = self.execute_command('workspace', 'list').out
    cmd_args = ['select', name]
    if name not in [
        ws.replace('*', '').strip()
        for ws in raw_ws_out.split('\n')
        if len(ws) > 0
    ]:
      cmd_args = ['new', name]
    return self.execute_command('workspace', *cmd_args).out

  def plan(self, input: bool = False, color: bool = False, refresh: bool = True,
           tf_vars: Optional[Dict[str, Any]] = None,
           targets: Optional[Sequence[str]] = None, output: bool = False,
           tf_var_file: Optional[Union[PathType, Sequence[PathType]]] = None,
           state: Optional[PathType] = None,
           plan_out: Optional[PathType] = None,
           **kw: Any) -> Union[str, TerraformPlanOutput]:
    """Run Terraform plan command, optionally returning parsed plan output.

    Args:
      input: Ask for input for variables if not directly set.
      color: Include color escape sequences in output.
      refresh: Update state prior to checking for differences.
      tf_vars: Dict of variables in the Terraform configuration.
      targets: List of resources to target. Operation will be limited to this
        resource and its dependencies.
      output: Determines if parsed `TerraformPlanOutput` will be returned.
      tf_var_file: Path (or sequence of paths) to terraform variable
        configuration files relative to `self.tfdir` or absolute.
      state: Path to state file to use when reading the prior state snapshot.
      plan_out: Optional path where the generated binary plan file should be
        saved (`-out`). When provided, the plan file is kept on disk; when
        omitted and `output=True`, a temporary plan file is used and unlinked.
    """
    cmd_args = parse_args(input=input, color=color, refresh=refresh,
                          tf_vars=tf_vars, targets=targets,
                          tf_var_file=tf_var_file, state=state,
                          plan_out=plan_out, **kw)
    if not output:
      return self.execute_command('plan', *cmd_args).out
    if plan_out is not None:
      self.execute_command('plan', *cmd_args)
      result = self.execute_command('show', '-no-color', '-json', str(plan_out))
    else:
      with tempfile.NamedTemporaryFile() as fp:
        temp_file = fp.name
      cmd_args.append(f'-out={temp_file}')
      try:
        self.execute_command('plan', *cmd_args)
        result = self.execute_command('show', '-no-color', '-json', temp_file)
      finally:
        Path(temp_file).unlink(missing_ok=True)
    try:
      return self._plan_formatter(result.out)
    except json.JSONDecodeError as e:
      raise TerraformTestError(f'Error decoding plan output: {e}') from e

  def apply(self, input: bool = False, color: bool = False,
            auto_approve: bool = True, tf_vars: Optional[Dict[str, Any]] = None,
            targets: Optional[Sequence[str]] = None,
            tf_var_file: Optional[Union[PathType, Sequence[PathType]]] = None,
            plan_file: Optional[PathType] = None, **kw: Any) -> str:
    """Run Terraform apply command.

    Args:
      input: Ask for input for variables if not directly set.
      color: Include color escape sequences in output.
      auto_approve: Skip interactive approval of plan before applying.
      tf_vars: Dict of variables in the Terraform configuration.
      targets: List of resources to target. Operation will be limited to this
        resource and its dependencies.
      tf_var_file: Path (or sequence of paths) to terraform variable
        configuration files relative to `self.tfdir` or absolute.
      plan_file: Optional saved binary plan file (created with `plan_out`) to
        apply directly.
    """
    cmd_args = parse_args(input=input, color=color, auto_approve=auto_approve,
                          tf_vars=tf_vars, targets=targets,
                          tf_var_file=tf_var_file, **kw)
    if plan_file is not None:
      cmd_args.append(str(plan_file))
    return self.execute_command('apply', *cmd_args).out

  def output(self, name: Optional[str] = None, color: bool = False,
             json_format: bool = True,
             **kw: Any) -> Union[str, TerraformValueDict]:
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
        _LOGGER.warning('error decoding output: %s', e)
    return output

  def destroy(self, input: bool = False, color: bool = False,
              auto_approve: bool = True, tf_vars: Optional[Dict[str,
                                                                Any]] = None,
              targets: Optional[Sequence[str]] = None,
              tf_var_file: Optional[Union[PathType, Sequence[PathType]]] = None,
              **kw: Any) -> str:
    """Run Terraform destroy command."""
    cmd_args = parse_args(input=input, color=color, auto_approve=auto_approve,
                          tf_vars=tf_vars, targets=targets,
                          tf_var_file=tf_var_file, **kw)
    return self.execute_command('destroy', *cmd_args).out

  def refresh(self, color: bool = False, lock: bool = False,
              tf_vars: Optional[Dict[str, Any]] = None,
              targets: Optional[Sequence[str]] = None, **kw: Any) -> str:
    """Run Terraform refresh command."""
    cmd_args = parse_args(color=color, lock=lock, tf_vars=tf_vars,
                          targets=targets, **kw)
    return self.execute_command('refresh', *cmd_args).out

  def state_pull(self) -> Union[str, TerraformState]:
    """Pull state."""
    state = self.execute_command('state', 'pull')
    try:
      return TerraformState(json.loads(state.out))
    except json.JSONDecodeError as e:
      _LOGGER.warning('error decoding state: %s', e)
      return state.out

  def execute_command(self, cmd: str, *cmd_args: Any) -> TerraformCommandOutput:
    """Run arbitrary Terraform command."""
    _LOGGER.debug([cmd, cmd_args])
    cmdline = [str(self.binary), cmd, *(str(a) for a in cmd_args)]
    _LOGGER.info(cmdline)
    full_output_lines: List[str] = []
    err_chunks: List[str] = []
    try:
      p = subprocess.Popen(cmdline, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, cwd=self.tfdir, env=self.env,
                           universal_newlines=True, encoding='utf-8',
                           errors='ignore')
    except FileNotFoundError as e:
      if not self.tfdir.is_dir():
        raise TerraformTestError(
            f'Terraform directory not found: {self.tfdir}') from e
      raise TerraformTestError(f'Terraform executable not found: {e}') from e

    def _drain_stderr(pipe: Any) -> None:
      try:
        for line in pipe:
          err_chunks.append(line)
      finally:
        pipe.close()

    stderr_thread = threading.Thread(target=_drain_stderr, args=(p.stderr,),
                                     daemon=True)
    stderr_thread.start()
    assert p.stdout is not None
    try:
      for output in p.stdout:
        _LOGGER.info(output.strip())
        full_output_lines.append(output)
    finally:
      p.stdout.close()
    retcode = p.wait()
    stderr_thread.join()
    full_output = ''.join(full_output_lines)
    err = ''.join(err_chunks)
    allowed_codes = (0, 2) if (cmd == 'plan' and
                               '-detailed-exitcode' in cmdline[2:]) else (0,)
    if retcode not in allowed_codes:
      message = f'Error running command {cmd}: {retcode} {full_output} {err}'
      _LOGGER.critical(message)
      raise TerraformTestError(message, err)
    return TerraformCommandOutput(retcode, full_output, err)
