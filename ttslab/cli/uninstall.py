"""
Uninstall a model.
"""

import click
import os
import shutil

from ttslab.utils.storage import get_model_dir, get_venv_dir


@click.command()
@click.argument("model")
@click.option("--yes", is_flag=True, help="Skip confirmation.")
def uninstall(model, yes):
    """Uninstall a model."""
    model_dir = os.path.join(get_model_dir(), model)
    if not os.path.exists(model_dir):
        raise click.ClickException(f"Model {model} not found.")
    if not yes and not click.confirm(f"Are you sure you want to uninstall {model}?"):
        return
    shutil.rmtree(model_dir)
    # Get venv path
    venv_path = os.path.join(get_venv_dir(), model)
    if os.path.exists(venv_path):
        shutil.rmtree(venv_path)
    print(f"Uninstalled {model}.")
