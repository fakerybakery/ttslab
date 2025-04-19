"""
Install a model.
"""

import click
import os
import json
import shutil
import rich
from ttslab.utils.storage import get_model_dir
from ttslab.utils.environment import create_venv, install_packages

@click.command()
@click.argument("model")
@click.option("--local", is_flag=True, help="Install from a local directory.")
def install(model, local):
    """Installs a model."""
    if local:
        click.echo(f"Installing {model} from a local directory...")
        if not os.path.exists(model):
            raise click.ClickException(f"Local model directory {model} does not exist.")
        MODEL_DIR = model  # model directory to install from
    else:
        raise NotImplementedError(
            "Installing from a remote URL is not yet supported. Git cloning is coming soon. For now just clone the repo manually and install locally."
        )

    # ensure manifest.json exists

    manifest_path = os.path.join(MODEL_DIR, "manifest.json")
    if not os.path.exists(manifest_path):
        raise click.ClickException(f"Manifest file {manifest_path} does not exist.")
    # read manifest
    with open(manifest_path, "r") as f:
        manifest = json.load(f)
    
    rich.print(json.dumps(manifest, indent=4))
    
    if os.path.exists(os.path.join(get_model_dir(), manifest["id"])):
        raise click.ClickException(
            f"Model {manifest['id']} already exists. You already installed it!"
        )


    # create venv
    print("🌱 Creating environment...")
    python_path = create_venv(manifest["id"])

    # install dependencies
    print("📦 Installing dependencies...")
    install_packages(python_path, manifest["dependencies"], uv=manifest["use_uv"] if "use_uv" in manifest else False)

    # copy it over to the model directory
    print("📂 Copying model...")
    shutil.copytree(MODEL_DIR, os.path.join(get_model_dir(), manifest["id"]))

    print("✅ Installed!")
