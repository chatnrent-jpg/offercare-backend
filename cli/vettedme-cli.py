#!/usr/bin/env python3
"""
VettedMe CLI - Command-line tool for developers

Install: pip install vettedme-cli
Usage: vettedme --help
"""

import os
import sys
import json
import click
import httpx
from datetime import datetime
from typing import Optional, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress

console = Console()

# ==================== CONFIGURATION ====================

class Config:
    def __init__(self):
        self.api_key = os.getenv("VETTEDME_API_KEY", "")
        self.base_url = os.getenv("VETTEDME_BASE_URL", "https://api.vettedme.ai")
        self.config_file = os.path.expanduser("~/.vettedme/config.json")
    
    def load(self):
        """Load config from file"""
        if os.path.exists(self.config_file):
            with open(self.config_file, "r") as f:
                data = json.load(f)
                self.api_key = data.get("api_key", self.api_key)
                self.base_url = data.get("base_url", self.base_url)
    
    def save(self):
        """Save config to file"""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, "w") as f:
            json.dump({
                "api_key": self.api_key,
                "base_url": self.base_url,
            }, f, indent=2)

config = Config()
config.load()

# ==================== API CLIENT ====================

def api_request(method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
    """Make API request"""
    if not config.api_key:
        console.print("[red]❌ API key not configured. Run: vettedme init[/red]")
        sys.exit(1)
    
    url = f"{config.base_url}{endpoint}"
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "User-Agent": "vettedme-cli/1.0.0",
        "Content-Type": "application/json",
    }
    
    try:
        response = httpx.request(method, url, headers=headers, **kwargs)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            console.print("[red]❌ Invalid API key[/red]")
            sys.exit(1)
        elif response.status_code == 404:
            console.print("[red]❌ Resource not found[/red]")
            sys.exit(1)
        else:
            console.print(f"[red]❌ Error {response.status_code}: {response.text}[/red]")
            sys.exit(1)
    except httpx.RequestError as e:
        console.print(f"[red]❌ Request failed: {e}[/red]")
        sys.exit(1)

# ==================== COMMANDS ====================

@click.group()
@click.version_option(version="1.0.0")
def cli():
    """VettedMe CLI - The universal trust layer for digital identity"""
    pass

@cli.command()
@click.option("--api-key", prompt="Enter your VettedMe API key", help="Your VettedMe API key")
@click.option("--base-url", default="https://api.vettedme.ai", help="API base URL")
def init(api_key: str, base_url: str):
    """Initialize VettedMe CLI with your API key"""
    config.api_key = api_key
    config.base_url = base_url
    config.save()
    
    console.print(Panel.fit(
        "[green]✅ VettedMe CLI initialized successfully![/green]\n\n"
        "Try these commands:\n"
        "  • vettedme verify PASS-ABC-123\n"
        "  • vettedme passports list\n"
        "  • vettedme webhooks list",
        title="🎉 Setup Complete"
    ))

@cli.command()
@click.argument("passport_id")
@click.option("--badge-type", help="Verify specific badge type")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def verify(passport_id: str, badge_type: Optional[str], output_json: bool):
    """Verify a passport credential"""
    with console.status("[bold cyan]Verifying credential..."):
        data = {"passport_id": passport_id}
        if badge_type:
            data["badge_type"] = badge_type
        
        result = api_request("POST", "/api/v1/passport/verify", json=data)
    
    if output_json:
        console.print_json(data=result)
        return
    
    # Rich formatted output
    if result.get("valid"):
        console.print(f"\n[green]✅ VERIFICATION SUCCESSFUL[/green]\n")
        console.print(f"[bold]Name:[/bold] {result.get('full_name')}")
        console.print(f"[bold]Trust Score:[/bold] {result.get('trust_score')}%")
        console.print(f"[bold]Passport ID:[/bold] {result.get('passport_id')}")
        
        if result.get("badges"):
            console.print(f"\n[bold]Active Badges:[/bold]")
            for badge in result["badges"]:
                status_color = "green" if badge["status"] == "active" else "yellow"
                console.print(f"  • [{status_color}]{badge['type']}[/{status_color}] ({badge['status']})")
    else:
        console.print(f"\n[red]❌ VERIFICATION FAILED[/red]\n")
        if result.get("warnings"):
            for warning in result["warnings"]:
                console.print(f"  ⚠️  {warning}")

@cli.group()
def passports():
    """Manage passports"""
    pass

@passports.command("list")
@click.option("--limit", default=20, help="Number of results")
@click.option("--status", help="Filter by status")
def list_passports(limit: int, status: Optional[str]):
    """List all passports"""
    params = {"limit": limit}
    if status:
        params["status"] = status
    
    result = api_request("GET", "/api/v1/passport", params=params)
    passports = result.get("passports", [])
    
    if not passports:
        console.print("[yellow]No passports found[/yellow]")
        return
    
    table = Table(title="Passports")
    table.add_column("Passport ID", style="cyan")
    table.add_column("Full Name", style="bold")
    table.add_column("Trust Score", justify="right")
    table.add_column("Status", style="green")
    table.add_column("Verifications", justify="right")
    
    for p in passports:
        table.add_row(
            p.get("passport_number", ""),
            p.get("full_name", ""),
            f"{p.get('trust_score', 0)}%",
            p.get("status", ""),
            str(p.get("verification_count", 0))
        )
    
    console.print(table)

@passports.command("get")
@click.argument("passport_id")
def get_passport(passport_id: str):
    """Get passport details"""
    result = api_request("GET", f"/api/v1/passport/{passport_id}")
    
    console.print(f"\n[bold cyan]Passport Details[/bold cyan]\n")
    console.print(f"[bold]ID:[/bold] {result.get('id')}")
    console.print(f"[bold]Number:[/bold] {result.get('passport_number')}")
    console.print(f"[bold]Name:[/bold] {result.get('full_name')}")
    console.print(f"[bold]Email:[/bold] {result.get('email')}")
    console.print(f"[bold]Trust Score:[/bold] {result.get('trust_score')}%")
    console.print(f"[bold]Status:[/bold] {result.get('status')}")
    console.print(f"[bold]Issued:[/bold] {result.get('issued_at')}")
    console.print(f"[bold]Verifications:[/bold] {result.get('verification_count')}")
    
    if result.get("badges"):
        console.print(f"\n[bold]Badges:[/bold]")
        for badge in result["badges"]:
            console.print(f"  • {badge['type']} ({badge['status']})")

@passports.command("create")
@click.option("--full-name", required=True, help="Full name")
@click.option("--email", required=True, help="Email address")
@click.option("--phone", help="Phone number")
def create_passport(full_name: str, email: str, phone: Optional[str]):
    """Create a new passport"""
    data = {"full_name": full_name, "email": email}
    if phone:
        data["phone"] = phone
    
    with console.status("[bold cyan]Creating passport..."):
        result = api_request("POST", "/api/v1/passport", json=data)
    
    console.print(f"\n[green]✅ Passport created![/green]\n")
    console.print(f"[bold]Passport ID:[/bold] {result.get('passport_number')}")
    console.print(f"[bold]Name:[/bold] {result.get('full_name')}")
    console.print(f"[bold]Trust Score:[/bold] {result.get('trust_score')}%")

@cli.group()
def webhooks():
    """Manage webhooks"""
    pass

@webhooks.command("list")
def list_webhooks():
    """List all webhooks"""
    result = api_request("GET", "/api/v1/webhooks")
    webhooks = result.get("webhooks", [])
    
    if not webhooks:
        console.print("[yellow]No webhooks configured[/yellow]")
        return
    
    table = Table(title="Webhooks")
    table.add_column("ID", style="cyan")
    table.add_column("URL", style="blue")
    table.add_column("Events", style="magenta")
    table.add_column("Status", style="green")
    
    for wh in webhooks:
        table.add_row(
            wh.get("id", ""),
            wh.get("url", ""),
            ", ".join(wh.get("events", [])),
            "Active" if wh.get("active") else "Inactive"
        )
    
    console.print(table)

@webhooks.command("create")
@click.option("--url", required=True, help="Webhook URL")
@click.option("--events", required=True, help="Comma-separated event list")
def create_webhook(url: str, events: str):
    """Create a webhook subscription"""
    event_list = [e.strip() for e in events.split(",")]
    
    with console.status("[bold cyan]Creating webhook..."):
        result = api_request("POST", "/api/v1/webhooks", json={
            "url": url,
            "events": event_list
        })
    
    console.print(f"\n[green]✅ Webhook created![/green]\n")
    console.print(f"[bold]ID:[/bold] {result.get('id')}")
    console.print(f"[bold]URL:[/bold] {result.get('url')}")
    console.print(f"[bold]Secret:[/bold] {result.get('secret')}")
    console.print(f"\n[yellow]⚠️  Save the secret - it won't be shown again![/yellow]")

@webhooks.command("delete")
@click.argument("webhook_id")
@click.confirmation_option(prompt="Are you sure you want to delete this webhook?")
def delete_webhook(webhook_id: str):
    """Delete a webhook subscription"""
    api_request("DELETE", f"/api/v1/webhooks/{webhook_id}")
    console.print("[green]✅ Webhook deleted[/green]")

@cli.group()
def badges():
    """Manage badges"""
    pass

@badges.command("add")
@click.argument("passport_id")
@click.option("--type", "badge_type", required=True, help="Badge type")
@click.option("--data", "credential_data", required=True, help="Credential data (JSON)")
def add_badge(passport_id: str, badge_type: str, credential_data: str):
    """Add a badge to a passport"""
    try:
        data_dict = json.loads(credential_data)
    except json.JSONDecodeError:
        console.print("[red]❌ Invalid JSON for credential data[/red]")
        sys.exit(1)
    
    with console.status("[bold cyan]Adding badge..."):
        result = api_request("POST", f"/api/v1/passport/{passport_id}/badges", json={
            "type": badge_type,
            "credential_data": data_dict
        })
    
    console.print(f"\n[green]✅ Badge added![/green]\n")
    console.print(f"[bold]Badge ID:[/bold] {result.get('id')}")
    console.print(f"[bold]Type:[/bold] {result.get('type')}")
    console.print(f"[bold]Status:[/bold] {result.get('status')}")

@cli.command()
def status():
    """Check VettedMe API status"""
    try:
        response = httpx.get(f"{config.base_url}/health", timeout=5)
        
        if response.status_code == 200:
            console.print("[green]✅ VettedMe API is online[/green]")
            data = response.json()
            console.print(f"[bold]Version:[/bold] {data.get('version', 'unknown')}")
        else:
            console.print("[red]❌ VettedMe API is not responding[/red]")
    except httpx.RequestError:
        console.print("[red]❌ Cannot reach VettedMe API[/red]")

@cli.command()
def docs():
    """Open VettedMe documentation"""
    import webbrowser
    console.print("[cyan]Opening documentation in your browser...[/cyan]")
    webbrowser.open("https://docs.vettedme.ai")

# ==================== MAIN ====================

if __name__ == "__main__":
    cli()
