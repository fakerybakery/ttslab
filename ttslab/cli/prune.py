"""
Prune venvs for models that are no longer installed.
"""

import click
import os
import json
import shutil

from ttslab.utils.storage import get_model_dir, get_venv_dir

from rich import progress


@click.command()
def prune():
    """Prune venvs for models that are no longer installed."""
    INSTALLED_MODELS = []
    for model in os.listdir(get_model_dir()):
        if os.path.isdir(os.path.join(get_model_dir(), model)):
            # try to find manifest.json
            manifest_path = os.path.join(get_model_dir(), model, "manifest.json")
            if os.path.exists(manifest_path):
                with open(manifest_path, "r") as f:
                    manifest = json.load(f)
                INSTALLED_MODELS.append(manifest["id"])

    # delete venvs for models that are no longer installed
    for venv in progress.track(
        os.listdir(get_venv_dir()), description="Pruning venvs..."
    ):
        if venv not in INSTALLED_MODELS:
            shutil.rmtree(os.path.join(get_venv_dir(), venv))

    print("✅ Pruned!")
