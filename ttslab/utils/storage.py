"""
Storage utilities.
"""

import os


def get_storage_dir():
    """Get the storage directory."""
    path = os.path.join(os.path.expanduser("~"), ".ttslab")
    os.makedirs(path, exist_ok=True)
    return path


def get_model_dir():
    """Get the model directory."""
    path = os.path.join(get_storage_dir(), "models")
    os.makedirs(path, exist_ok=True)
    return path


def get_venv_dir():
    """Get the venv directory."""
    path = os.path.join(get_storage_dir(), "envs")
    os.makedirs(path, exist_ok=True)
    return path

def list_models():
    """List all models."""
    return os.listdir(get_model_dir())

def list_venvs():
    """List all venvs."""
    return os.listdir(get_venv_dir())