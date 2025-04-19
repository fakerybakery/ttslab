"""
Serve the web UI.
"""

import click

@click.command()
def serve():
    """Serve the web UI."""
    from ttslab.web import app
    # app = create_app()
    app.run(debug=True)
