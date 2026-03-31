import tempfile
from pathlib import Path
import tftest

def test_tfdir_as_path():
  with tempfile.TemporaryDirectory() as tmpdir:
    tmpdir_path = Path(tmpdir).resolve()
    tf = tftest.TerraformTest(tmpdir_path)
    # The regression: tf.tfdir / 'something' throws TypeError
    # if tf.tfdir is converted to a string.
    assert (tf.tfdir / 'something') == tmpdir_path / 'something'

def test_tfdir_as_str():
  with tempfile.TemporaryDirectory() as tmpdir:
    tf = tftest.TerraformTest(tmpdir)
    assert isinstance(tf.tfdir, str)

