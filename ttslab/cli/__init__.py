"""
TTSLab CLI.
"""

import click
import os
import json

from ttslab.cli.install import install
from ttslab.cli.prune import prune
from ttslab.cli.uninstall import uninstall
from ttslab.cli.serve import serve
from ttslab.cli.list import list_models

@click.group()
def app():
    """TTSLab: Run TTS models."""
    pass

app.add_command(install)
app.add_command(prune)
app.add_command(uninstall)
app.add_command(serve)
app.add_command(list_models)