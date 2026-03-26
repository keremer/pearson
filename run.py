import click

from portal import create_app

app = create_app()

@click.group()
def cli():
    """crminaec Platform - Global Entry Point"""
    pass

@cli.command()
@click.option('--port', default=5000, help="Port for the Portal")
@click.option('--debug/--no-debug', default=True)
def web(port, debug):
    """Start the Unified Web Portal (Pearson + Arkhon)"""
    click.echo(f"🚀 Starting Portal on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=debug)

@cli.command()
@click.argument('platform', type=click.Choice(['pearson', 'arkhon', 'all']))
def sync(platform):
    """Run background sync sequences (Google Drive / Order Parsing)"""
    if platform in ['pearson', 'all']:
        click.echo("🔄 Syncing Pearson HND5 Markdown specs...")
        # Call your specific sync logic here
    if platform in ['arkhon', 'all']:
        click.echo("📐 Parsing Arkhon order.htm files...")
        # Call your order.htm parser here
    click.echo("✅ Sync complete.")

if __name__ == "__main__":
    cli()