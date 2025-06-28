import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from cloudflare import Client, Cloudflare
from simple_term_menu import TerminalMenu

__version__ = "0.1.0"
CONFIG_FILE = "config.json"
HOME_DIR = os.path.expanduser("~")
CONFIG_FOLDER = "AppData/Roaming" if os.name == "nt" else ".config"
CONFIG_PATH = Path(HOME_DIR) / CONFIG_FOLDER / "cf-dns-edit.json"


def show_menu(title: str, items: List[str]) -> Optional[Tuple[int, str]]:
    """Display a menu with the given title and items."""
    modified_items = []
    for i, item in enumerate(items, 1):
        if i > 9:
            i = chr(65 + (i - 10))
        if item in ("Exit", "Back", "Add Record", "Save", "Delete"):
            modified_items.append(f"{item}")
        else:
            modified_items.append(f"[{i}] {item}")
    terminal_menu = TerminalMenu(
        modified_items,
        title=title,
    )
    menu_entry_index: int = terminal_menu.show()  # type: ignore
    return (
        None
        if menu_entry_index is None
        else (menu_entry_index, items[menu_entry_index])
    )


def save_config(config: Dict[str, Any]) -> None:
    """Save the configuration to a JSON file."""
    try:
        if not CONFIG_PATH.parent.exists():
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
        print(f"Configuration saved to {CONFIG_PATH}")
    except Exception as e:  # pylint: disable=broad-except
        print(f"Failed to save configuration: {e}")
        sys.exit(1)


def load_config() -> Dict[str, Any]:
    """Load the configuration from a JSON file."""
    if not CONFIG_PATH.exists():
        return {}

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Invalid configuration file: {e}")
        return {}
    except Exception as e:  # pylint: disable=broad-except
        print(f"Failed to load configuration: {e}")
        return {}


def cloudflare_login(config: Dict[str, Any]) -> Client:
    """Prompt the user for Cloudflare credentials and return a Cloudflare client."""
    if "token" in config:
        token = config["token"]
    else:
        token = str(input("Enter your Cloudflare API token: ")).strip()

    try:
        if not token:
            print("API token is required.")
            sys.exit(1)

        if "token" not in config:
            config["token"] = token
            save_config(config)

        cf = Cloudflare(api_token=token)
        # Test the connection by making a simple API call
        cf.user.tokens.verify()
        print("Successfully connected to Cloudflare API")
        return cf
    except Exception as e:  # pylint: disable=broad-except
        print(f"Failed to log into Cloudflare: {e}")
        # If authentication failed, remove the token from config
        if "token" in config:
            del config["token"]
            save_config(config)
        sys.exit(1)


def load_all_domains(cf: Client) -> List:
    """Load all domains from Cloudflare."""
    try:
        print("Loading domains from Cloudflare...")
        zones = []
        page = cf.zones.list()
        zones.extend(page)
        while page.has_next_page():
            page = page.get_next_page()
            zones.extend(page)

        if not zones:
            print("No domains found in your Cloudflare account.")
        else:
            print(f"Found {len(zones)} domain{'s' if len(zones) > 1 else ''}.")
        return zones
    except Exception as e:  # pylint: disable=broad-except
        print(f"Failed to load domains: {e}")
        return []

def get_dns_records(cf: Client, zone_id: str) -> List:
    """Get DNS records for a specific zone."""
    try:
        print("Loading DNS records...")
        records = []
        page = cf.dns.records.list(zone_id=zone_id)
        records.extend(page)
        while page.has_next_page():
            page = page.get_next_page()
            records.extend(page)

        print(f"Found {len(records)} DNS record{'s' if len(records) > 1 else ''}")
        return records
    except Exception as e:  # pylint: disable=broad-except
        print(f"Failed to get DNS records: {e}")
        return []


def validate_record_input(
    field_name: str, value: str, required: bool = True
) -> Optional[str]:
    """Validate user input for DNS record fields."""
    if required and not value:
        print(f"{field_name} cannot be empty.")
        return None
    return value


def add_dns_record(cf: Client, zone_id: str) -> bool:
    """Add a new DNS record."""
    new_type = validate_record_input(
        "Type", input("Enter record type (A, AAAA, CNAME, etc.): ").strip().upper()
    )
    if new_type is None:
        return False

    new_name = validate_record_input("Name", input("Enter record name: ").strip())
    if new_name is None:
        return False

    new_content = validate_record_input(
        "Content", input("Enter record content: ").strip()
    )
    if new_content is None:
        return False

    new_proxied = input("Proxied (yes/no): ").strip().lower() == "yes"
    new_comment = input("Enter record comment (optional): ").strip()

    ttl_input = input("Enter TTL (seconds) or 'Auto': ").strip()
    if ttl_input.lower() == "auto":
        new_ttl = 1
    else:
        try:
            new_ttl = int(ttl_input)
            if new_ttl < 1:
                print("TTL must be at least 1 second, using Auto (1).")
                new_ttl = 1
        except ValueError:
            print("Invalid TTL value, using Auto (1).")
            new_ttl = 1

    try:
        cf.dns.records.create(
            zone_id=zone_id,
            type=new_type,
            name=new_name,
            content=new_content,
            proxied=new_proxied,
            comment=new_comment,
            ttl=new_ttl,
        )
        print(f"✅ Added new DNS record for {new_name}")
        return True
    except Exception as e:  # pylint: disable=broad-except
        print(f"❌ Failed to add DNS record: {e}")
        return False


def update_dns_record(cf: Client, record, zone_id: str) -> bool:
    """Update an existing DNS record."""
    try:
        cf.dns.records.update(
            record.id,
            zone_id=zone_id,
            type=record.type,
            name=record.name,
            content=record.content,
            proxied=record.proxied,
            comment=record.comment,
            ttl=record.ttl,
        )
        print(f"✅ Updated DNS record for {record.name}")
        return True
    except Exception as e:  # pylint: disable=broad-except
        print(f"❌ Failed to update DNS record: {e}")
        return False


def delete_dns_record(cf: Client, record, zone_id: str) -> bool:
    """Delete a DNS record."""
    confirm = (
        input(f"Are you sure you want to delete the DNS record {record.name}? (y/N): ")
        .strip()
        .lower()
    )
    if confirm != "y":
        print("Deletion cancelled.")
        return False

    try:
        cf.dns.records.delete(record.id, zone_id=zone_id)
        print(f"✅ Deleted DNS record {record.name}")
        return True
    except Exception as e:  # pylint: disable=broad-except
        print(f"❌ Failed to delete DNS record: {e}")
        return False


def edit_dns_record(cf: Client, record, zone_id: str) -> None:
    """Edit a DNS record's properties."""
    while True:
        # Format record properties for display
        keys = [
            f"Type: {record.type or 'N/A'}",
            f"Name: {record.name or 'N/A'}",
            f"Content: {record.content or 'N/A'}",
            f"Proxied: {'Yes' if record.proxied else 'No'}",
            f"Comment: {record.comment or 'N/A'}",
            f"TTL: {'Auto' if record.ttl == 1 else str(record.ttl)}",
            "Save",
            "Delete",
            "Back",
            "Exit",
        ]

        selected_property = show_menu("DNS Record Properties", keys)
        if selected_property is None:
            print("No property selected. Going back.")
            return

        option = selected_property[1]

        if option == "Exit":
            sys.exit(0)
        elif option == "Back":
            return
        elif option == "Delete":
            if delete_dns_record(cf, record, zone_id):
                return
        elif option == "Save":
            if update_dns_record(cf, record, zone_id):
                return
        elif option.startswith("Type: "):
            new_value = validate_record_input(
                "Type", input("Enter new type (A, AAAA, CNAME, etc.): ").strip().upper()
            )
            if new_value:
                record.type = new_value
        elif option.startswith("Name: "):
            new_value = validate_record_input("Name", input("Enter new name: ").strip())
            if new_value:
                record.name = new_value
        elif option.startswith("Content: "):
            new_value = validate_record_input(
                "Content", input("Enter new content: ").strip()
            )
            if new_value:
                record.content = new_value
        elif option.startswith("Proxied: "):
            record.proxied = input("Proxied (yes/no): ").strip().lower() == "yes"
        elif option.startswith("Comment: "):
            record.comment = input("Enter new comment: ").strip()
        elif option.startswith("TTL: "):
            ttl_input = input("Enter new TTL (or 'Auto' for automatic): ").strip()
            if ttl_input.lower() == "auto":
                record.ttl = 1
            else:
                try:
                    ttl_value = int(ttl_input)
                    if ttl_value < 1:
                        print("TTL must be at least 1 second. Setting to Auto (1).")
                        record.ttl = 1
                    else:
                        record.ttl = ttl_value
                except ValueError:
                    print("Invalid TTL value. Please enter a number or 'Auto'.")


def manage_dns_records(cf: Client, domain_name: str, zone_id: str) -> None:
    """Manage DNS records for a specific domain."""
    while True:
        print(f"Managing DNS records for: {domain_name}")

        dns_records = get_dns_records(cf, zone_id)

        record_options = [f"({record.type}) {record.name}" for record in dns_records]
        options = record_options + ["Add Record", "Back", "Exit"]

        selected = show_menu("Choose a DNS record to edit", options)

        if selected is None:
            print("No selection made. Going back.")
            return

        option = selected[1]

        if option == "Exit":
            sys.exit(0)
        elif option == "Back":
            return
        elif option == "Add Record":
            add_dns_record(cf, zone_id)
        else:
            # User selected a DNS record
            selected_dns_record = dns_records[selected[0]]
            edit_dns_record(cf, selected_dns_record, zone_id)


def main() -> None:
    """Main entry point for the application."""

    if len(sys.argv) > 1:
        if sys.argv[1] in ("--version", "-v"):
            print(f"cf-dns-edit version {__version__}")
            sys.exit(0)

    try:
        print("🌐 Cloudflare DNS Editor")
        print("------------------------")

        config = load_config()
        cf = cloudflare_login(config)
        domains = load_all_domains(cf)

        if not domains:
            print("No domains found. Please add domains to your Cloudflare account.")
            sys.exit(1)

        while True:
            domain_options = [domain.name for domain in domains]
            selected = show_menu("Choose a domain", domain_options + ["Exit"])

            if selected is None or selected[1] == "Exit":
                return

            selected_domain_index = selected[0]
            selected_domain = domains[selected_domain_index]
            manage_dns_records(cf, selected_domain.name, selected_domain.id)

    except KeyboardInterrupt:
        print("\nOperation cancelled by user. Exiting.")
    except Exception as e:  # pylint: disable=broad-except
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
