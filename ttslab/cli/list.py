"""
List installed models.
"""

import click
import os
import json
import rich
from rich.table import Table
from rich.console import Console
from ttslab.utils.storage import get_model_dir

@click.command('list')
def list_models():
    """List installed models."""
    console = Console()
    model_dir = get_model_dir()
    
    if not os.path.exists(model_dir):
        console.print("[yellow]No models directory found. Install a model first.[/yellow]")
        return
    
    models = os.listdir(model_dir)
    
    if not models:
        console.print("[yellow]No models installed. Use 'ttslab install' to install a model.[/yellow]")
        return
    
    table = Table(title="Installed Models")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Version", style="blue")
    table.add_column("Description")
    
    for model in models:
        model_path = os.path.join(model_dir, model)
        manifest_path = os.path.join(model_path, "manifest.json")
        
        if not os.path.exists(manifest_path):
            console.print(f"[yellow]Warning: Model '{model}' has no manifest.json. Consider uninstalling with 'ttslab uninstall {model}'.[/yellow]")
            continue
        
        try:
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
            
            table.add_row(
                manifest.get("id", model),
                manifest.get("name", "Unknown"),
                manifest.get("version", "Unknown"),
                manifest.get("description", "")
            )
        except json.JSONDecodeError:
            console.print(f"[yellow]Warning: Model '{model}' has an invalid manifest.json. Consider uninstalling with 'ttslab uninstall {model}'.[/yellow]")
        except Exception as e:
            console.print(f"[yellow]Warning: Error reading manifest for model '{model}': {str(e)}[/yellow]")
    
    console.print(table)
