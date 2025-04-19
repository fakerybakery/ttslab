"""
Environment utilities.

- Create venvs
- Install dependencies
"""

import os
import venv

from ttslab.utils.storage import get_venv_dir


def create_venv(name):
    """Create or get a venv."""
    path = os.path.join(get_venv_dir(), name)
    if not os.path.exists(path):
        venv.create(path, with_pip=True)
    # get path to python in venv
    python_path = os.path.join(path, "Scripts" if os.name == "nt" else "bin", "python")
    return python_path


def install_packages(python_path: str, packages: list[str], uv: bool = False):
    """Install packages."""
    import subprocess

    if uv:
        subprocess.run([python_path, "-m", "pip", "install", "uv"])
        subprocess.run([python_path, "-m", "uv", "pip", "install", *packages])
    else:
        subprocess.run([python_path, "-m", "pip", "install", *packages])
