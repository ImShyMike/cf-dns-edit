"""Main entry point for cf-dns-edit."""

import logging
import os
import sys
from typing import List

import click
from cloudflare import Cloudflare
from cloudflare.types.zones.zone import Zone
from dotenv import load_dotenv
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.validation import ValidationResult, Validator
from textual.widgets import Button, Footer, Input, Link, OptionList, Static
from textual.widgets.option_list import Option

from cf_dns_edit.__about__ import __version__

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

MIN_SCREEN_SIZE = (71, 30)  # magic numbers :D
TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")


def pluralize(count: int, word: str) -> str:
    """Return the pluralized form of a word based on count."""
    return f"{count} {word}{'s' if count != 1 else ''}"


def get_dns_records(cloudflare: Cloudflare, zone_id: str) -> List:
    """Get DNS records for a specific zone."""
    try:
        logger.info("Loading DNS records...")
        records = []

        for record in cloudflare.dns.records.list(zone_id=zone_id):
            records.append(record)

        logger.info("Found %s.", pluralize(len(records), "DNS record"))
        return records
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Failed to get DNS records: %s", e)
        return []


def load_all_domains(
    cloudflare: Cloudflare,
) -> List[Zone]:
    """Load all domains from Cloudflare."""
    try:
        logger.info("Loading domains from Cloudflare...")
        zones = []

        for zone in cloudflare.zones.list():
            zones.append(zone)

        if not zones:
            logger.info("No domains found in your Cloudflare account.")
        else:
            logger.info("Found %s.", pluralize(len(zones), "domain"))
        return zones
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Failed to load domains: %s", e)
        return []


class ApiTokenValidator(Validator):
    """Validator for the Cloudflare API token input."""

    def __init__(self) -> None:
        """Initialize the validator."""
        super().__init__()

    def describe_failure(self, failure) -> str:
        """Return description of the failure."""
        return "API Token is invalid!"

    def validate(self, value: str) -> ValidationResult:
        """Check if the API token is not empty."""
        if value.strip():
            return self.success()
        return self.failure("API Token cannot be empty.")

    def error_message(self) -> str:
        """Return the error message for invalid input."""
        return "API Token cannot be empty."


class LoginScreen(Screen):
    """Login screen for the application."""

    CSS = """
    LoginScreen {
        align: center middle;
        layers: base overlay;
    }
    
    #login-container {
        width: 60;
        height: 25;
        background: $surface;
        border: solid $primary;
        padding: 2;
    }
    
    #login-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 2;
        text-align: center;
    }
    
    #token-link {
        text-align: center;
        width: 100%;
    }

    Button {
        width: 100%;
        margin: 1 0;
    }
    
    Input {
        width: 100%;
        margin: 1 0;
    }
    """

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("ctrl+c", "app.quit", "Quit"),
        ("enter", "login", "Login"),
        ("right", "click_focused_button", "Click Button"),
    ]

    def compose(self) -> ComposeResult:
        with Container(id="login-container"):
            with Vertical():
                yield Static("🔐 Login with Cloudflare", id="login-title")
                yield Static("API Token:")
                yield Input(
                    placeholder="Enter your Cloudflare API token",
                    password=True,
                    validate_on=["changed"],
                    validators=[ApiTokenValidator()],
                    id="token-input",
                )
                yield Static("")
                yield Button("Login", id="login-btn", variant="primary")
                yield Static("")
                yield Static(
                    "Grab an API token with scopes Zone.Zone:Read,", classes="help-text"
                )
                yield Static(
                    "Zone.DNS:Read and Zone.DNS:Write from Cloudflare",
                    classes="help-text",
                )
                yield Link(
                    "Get your API token here",
                    url="https://dash.cloudflare.com/profile/api-tokens",
                    id="token-link",
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Button handling for the login screen."""
        if event.button.id == "login-btn":
            self.call_next(self.handle_login)
        elif event.button.id == "guest-btn":
            self.app.push_screen("manage")
        elif event.button.id == "about-btn":
            self.app.push_screen("about")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission (Enter key)."""
        if event.input.id == "token-input":
            self.call_next(self.handle_login)

    async def handle_login(self) -> None:
        """Handle the login process."""
        token_input = self.query_one("#token-input", Input)

        if (
            ApiTokenValidator().validate(token_input.value)
            != ValidationResult.success()
        ):
            self.app.notify("❌ Please enter a valid token", severity="error")
            return

        success = await self.verify_token(token_input.value)

        if success:
            self.app.notify("✅ Login successful!", timeout=1)
            self.app.push_screen("manage")
        else:
            self.app.notify(
                "❌ Invalid api key, please try again.", severity="error", timeout=2
            )

    def action_login(self) -> None:
        """Handle login action."""
        self.call_next(self.handle_login)

    def action_click_focused_button(self) -> None:
        """Click the currently focused button."""
        focused = self.focused
        if isinstance(focused, Button):
            focused.press()

    async def verify_token(self, token: str) -> bool:
        """Verify the API token asynchronously."""
        try:
            cf_instance = Cloudflare(api_token=token)
            cf_instance.user.tokens.verify()
            app = self.app
            if hasattr(app, "cf_instance"):
                app.cf_instance = cf_instance  # type: ignore # pylint: disable=attribute-defined-outside-init
            return True
        except Exception:  # pylint: disable=broad-except
            app = self.app
            if hasattr(app, "cf_instance"):
                app.cf_instance = None  # type: ignore # pylint: disable=attribute-defined-outside-init
            return False


class DomainManagementScreen(Screen):
    """Main DNS management screen."""

    CSS = """
    DomainManagementScreen {
        layout: horizontal;
    }
    
    #main-container {
        layout: horizontal;
        height: 100%;
    }
    
    #button-panel {
        width: 50%;
        align: center middle;
        padding: 2;
    }
    
    #info-panel {
        width: 45%;
        background: $surface;
        border: solid $primary;
        margin: 2;
        padding: 2;
    }
    
    #info-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    
    #domains-list {
        height: 100%;
        margin-top: 1;
    }
    
    Button {
        width: 95%;
        margin: 1;
    }
    """

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("ctrl+c", "app.quit", "Quit"),
        ("a", "about", "About"),
        ("l", "logout", "Logout"),
        ("e", "edit_domain", "Edit Domain"),
        ("r", "refresh_domains", "Refresh Domains"),
        ("right", "move_to_list", "Move to List"),
        ("left", "move_to_buttons", "Move to Buttons"),
        ("enter", "click_focused_button", "Click Button"),
    ]

    def compose(self) -> ComposeResult:
        with Container(id="main-container"):
            with Container(id="button-panel"):
                with Vertical():
                    yield Static("📚 DNS Records Manager", id="title")
                    yield Static("")
                    yield Button("✏️  Manage Selected Domain", id="edit")
                    yield Static("")
                    yield Button("ℹ️  About", id="about-btn")
                    yield Button("🚪 Logout", id="logout-btn")
            with Container(id="info-panel"):
                with Vertical():
                    yield Static("🌐 Your Cloudflare Domains", id="info-title")
                    yield Static("")
                    yield OptionList(id="domains-list")

    def on_mount(self) -> None:
        """Load domains when the screen is mounted."""
        self.load_domains()

    def load_domains(self) -> None:
        """Load and display domains in the OptionList."""
        cloudflare: Cloudflare | None = self.app.cf_instance  # type: ignore

        if cloudflare is None:
            self.app.notify("❌ Unknown error, please log back in.", severity="error")
            self.app.push_screen("login")
            return

        domains = load_all_domains(cloudflare)
        domains_list = self.query_one("#domains-list", OptionList)
        domains_list.clear_options()

        if domains:
            domain_count = len(domains)
            for i, domain in enumerate(domains):
                domains_list.add_option(Option(domain.name, id=domain.id))
                if i < domain_count - 1:
                    domains_list.add_option(None)
            domains_list.highlighted = 0
        else:
            domains_list.add_option(Option("No domains found", disabled=True))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Button handling for the DNS management screen."""
        cloudflare: Cloudflare | None = self.app.cf_instance  # type: ignore

        if event.button.id == "about-btn":
            self.app.push_screen("about")
        elif event.button.id == "logout-btn":
            self.action_logout()

        if cloudflare is None:
            self.app.notify("❌ Unknown error, please log back in.", severity="error")
            self.app.push_screen("login")
            return

        if event.button.id == "edit":
            domains_list = self.query_one("#domains-list", OptionList)
            selected_index = domains_list.highlighted

            if selected_index is not None and selected_index >= 0:
                try:
                    selected_option = domains_list.get_option_at_index(selected_index)
                    if selected_option and selected_option.id is not None:
                        domain_name = str(selected_option.prompt)
                        domain_id = str(selected_option.id)
                        dns_screen = DnsManagementScreen(domain_id, domain_name)
                        self.app.push_screen(dns_screen)
                    else:
                        self.app.notify(
                            "❌ Invalid domain selection", severity="warning"
                        )
                except Exception:  # pylint: disable=broad-except
                    self.app.notify(
                        "❌ Error getting selected domain", severity="error"
                    )
            else:
                self.app.notify("❌ Please select a domain first", severity="warning")

    def action_about(self) -> None:
        """Show about screen."""
        self.app.push_screen("about")

    def action_logout(self) -> None:
        """Logout and return to login screen."""
        self.app.notify("👋 Logged out")
        while len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        if not isinstance(self.app.screen, LoginScreen):
            self.app.push_screen("login")

    def action_edit_domain(self) -> None:
        """Edit the selected domain via keyboard shortcut."""
        domains_list = self.query_one("#domains-list", OptionList)
        selected_index = domains_list.highlighted

        if selected_index is not None and selected_index >= 0:
            try:
                selected_option = domains_list.get_option_at_index(selected_index)
                if selected_option and selected_option.id is not None:
                    domain_name = str(selected_option.prompt)
                    domain_id = str(selected_option.id)
                    dns_screen = DnsManagementScreen(domain_id, domain_name)
                    self.app.push_screen(dns_screen)
                else:
                    self.app.notify("❌ Invalid domain selection", severity="warning")
            except Exception:  # pylint: disable=broad-except
                self.app.notify("❌ Error getting selected domain", severity="error")
        else:
            self.app.notify("❌ Please select a domain first", severity="warning")

    def action_refresh_domains(self) -> None:
        """Refresh the domain list."""
        self.load_domains()

    def action_click_focused_button(self) -> None:
        """Click the currently focused button."""
        focused = self.focused
        if isinstance(focused, Button):
            focused.press()

    def action_move_to_list(self) -> None:
        """Move focus to the domains list."""
        domains_list = self.query_one("#domains-list", OptionList)
        domains_list.focus()

    def action_move_to_buttons(self) -> None:
        """Move focus to the buttons panel."""
        edit_btn = self.query_one("#edit", Button)
        edit_btn.focus()


class DnsManagementScreen(Screen):
    """DNS records management screen for a specific domain."""

    CSS = """
    DnsManagementScreen {
        layout: horizontal;
    }
    
    #main-container {
        layout: horizontal;
        height: 100%;
    }
    
    #button-panel {
        width: 35%;
        align: center middle;
        padding: 2;
    }

    #records-list {
        width: 60%;
        background: $surface;
        border: solid $primary;
        margin: 2;
        padding: 2;
        height: 100%;
        margin-top: 1;
    }
    
    #records-list > .option-list--option {
        color: $text;
    }
    
    #records-list > .option-list--option-highlighted {
        color: $text;
    }
    
    Button {
        width: 95%;
        margin: 1;
    }
    
    .record-info {
        color: $text-muted;
        text-style: italic;
    }
    """

    BINDINGS = [
        ("escape", "back_to_domains", "Back to Domains"),
        ("ctrl+c", "app.quit", "Quit"),
        ("a", "add_record", "Add Record"),
        ("e", "edit_record", "Edit Record"),
        ("d", "delete_record", "Delete Record"),
        ("r", "refresh_records", "Refresh Records"),
        ("right", "move_to_list", "Move to List"),
        ("left", "move_to_buttons", "Move to Buttons"),
        ("enter", "click_focused_button", "Click Button"),
    ]

    def __init__(self, domain_id: str, domain_name: str) -> None:
        """Initialize the DNS management screen."""
        super().__init__()
        self.domain_id = domain_id
        self.domain_name = domain_name

    def compose(self) -> ComposeResult:
        with Container(id="main-container"):
            with Container(id="button-panel"):
                with Vertical():
                    yield Static("📝 DNS Records", id="title")
                    yield Static(f"Domain: {self.domain_name}", classes="record-info")
                    yield Static("")
                    yield Button("➕ Add DNS Record", id="add-record")
                    yield Button("✏️  Edit Selected Record", id="edit-record")
                    yield Button("🗑️  Delete Selected Record", id="delete-record")
                    yield Static("")
                    yield Button("⬅️  Back to Domains", id="back-btn")
            yield OptionList(id="records-list")

    def on_mount(self) -> None:
        """Load DNS records when the screen is mounted."""
        self.load_dns_records()

    def load_dns_records(self) -> None:
        """Load and display DNS records in the OptionList."""
        cloudflare: Cloudflare | None = self.app.cf_instance  # type: ignore

        if cloudflare is None:
            self.app.notify("❌ Unknown error, please log back in.", severity="error")
            self.app.push_screen("login")
            return

        records = get_dns_records(cloudflare, self.domain_id)
        records_list = self.query_one("#records-list", OptionList)
        records_list.clear_options()

        if records:
            record_count = len(records)
            for i, record in enumerate(records):
                divider = "[dim cyan]|[/dim cyan]"

                record_type = record.type
                type_color = {
                    "A": "green",
                    "AAAA": "green",
                    "CNAME": "blue",
                    "MX": "magenta",
                    "TXT": "yellow",
                    "NS": "cyan",
                    "SRV": "red",
                }.get(record_type, "[white]")

                record_text = (
                    f"[{type_color}]{record.type}[/{type_color}] {divider} "
                    f"[bold]{record.name}[/bold] {divider} {record.content}"
                )

                if hasattr(record, "ttl") and record.ttl:
                    ttl_value = record.ttl if record.ttl != 1 else "Auto"
                    record_text += (
                        f" {divider} [dim yellow]TTL:[/dim yellow] {ttl_value}"
                    )

                records_list.add_option(Option(record_text, id=record.id))
                if i < record_count - 1:
                    records_list.add_option(None)
            records_list.highlighted = 0
        else:
            records_list.add_option(Option("No DNS records found", disabled=True))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Button handling for the DNS management screen."""
        cloudflare: Cloudflare | None = self.app.cf_instance  # type: ignore

        if cloudflare is None:
            self.app.notify("❌ Unknown error, please log back in.", severity="error")
            self.app.push_screen("login")
            return

        if event.button.id == "back-btn":
            self.action_back_to_domains()
        elif event.button.id == "add-record":
            self.action_add_record()
        elif event.button.id == "edit-record":
            self.action_edit_record()
        elif event.button.id == "delete-record":
            self.action_delete_record()
        elif event.button.id == "refresh-records":
            self.action_refresh_records()

    def action_back_to_domains(self) -> None:
        """Go back to domain management screen."""
        self.app.pop_screen()

    def action_add_record(self) -> None:
        """Add a new DNS record."""
        self.app.notify(f"➕ Adding DNS record for {self.domain_name}...")
        # TODO: add record

    def action_edit_record(self) -> None:
        """Edit the selected DNS record."""
        records_list = self.query_one("#records-list", OptionList)
        selected_index = records_list.highlighted

        if selected_index is not None and selected_index >= 0:
            try:
                selected_option = records_list.get_option_at_index(selected_index)
                if selected_option and selected_option.id is not None:
                    pass
                    # TODO: edit record
                else:
                    self.app.notify("❌ Invalid record selection", severity="warning")
            except Exception:  # pylint: disable=broad-except
                self.app.notify("❌ Error getting selected record", severity="error")
        else:
            self.app.notify("❌ Please select a record first", severity="warning")

    def action_delete_record(self) -> None:
        """Delete the selected DNS record."""
        records_list = self.query_one("#records-list", OptionList)
        selected_index = records_list.highlighted

        if selected_index is not None and selected_index >= 0:
            try:
                selected_option = records_list.get_option_at_index(selected_index)
                if selected_option and selected_option.id is not None:
                    pass
                    # TODO: delete record
                else:
                    self.app.notify("❌ Invalid record selection", severity="warning")
            except Exception:  # pylint: disable=broad-except
                self.app.notify("❌ Error getting selected record", severity="error")
        else:
            self.app.notify("❌ Please select a record first", severity="warning")

    def action_refresh_records(self) -> None:
        """Refresh the DNS records list."""
        self.load_dns_records()

    def action_click_focused_button(self) -> None:
        """Click the currently focused button."""
        focused = self.focused
        if isinstance(focused, Button):
            focused.press()

    def action_move_to_list(self) -> None:
        """Move focus to the records list."""
        records_list = self.query_one("#records-list", OptionList)
        records_list.focus()

    def action_move_to_buttons(self) -> None:
        """Move focus to the buttons panel."""
        add_btn = self.query_one("#add-record", Button)
        add_btn.focus()


class AboutScreen(Screen):
    """About screen with application information."""

    CSS = """
    AboutScreen {
        align: center middle;
    }
    
    #about-container {
        width: 60;
        height: 25;
        background: $surface;
        border: solid $primary;
        padding: 2;
    }
    
    #about-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 2;
        text-align: center;
    }
    
    .section-title {
        text-style: bold;
        color: $accent;
        margin-top: 1;
        margin-bottom: 1;
    }
    
    .help-text {
        align: center bottom;
    }
    
    Button {
        width: 100%;
        margin: 1 0;
    }
    """

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("ctrl+c", "app.quit", "Quit"),
        ("b", "manage", "manage"),
        ("l", "login", "Login"),
        ("right", "click_focused_button", "Click Button"),
    ]

    def compose(self) -> ComposeResult:
        with Container(id="about-container"):
            with Vertical():
                yield Static("ℹ️  About CF DNS Edit", id="about-title")
                yield Static("")
                yield Static("Version:", classes="section-title")
                yield Static(f"cf-dns-edit v{__version__}")
                yield Static("")
                yield Static("Description:", classes="section-title")
                yield Static("A Textual-based terminal application to")
                yield Static("easily manage Cloudflare DNS records.")
                yield Static("")
            yield Static("Press ESC to go back", classes="help-text")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Button handling for the about screen."""
        if event.button.id == "book-btn":
            self.app.push_screen("manage")
        elif event.button.id == "login-btn":
            self.app.push_screen("login")

    def action_book(self) -> None:
        """Go to book screen."""
        self.app.push_screen("manage")

    def action_login(self) -> None:
        """Go to login screen."""
        self.app.push_screen("login")

    def action_click_focused_button(self) -> None:
        """Click the currently focused button."""
        focused = self.focused
        if isinstance(focused, Button):
            focused.press()


class ScreenTooSmall(Screen):
    """Screen too small warning screen."""

    CSS = """
    ScreenTooSmall {
        align: center middle;
    }

    #warning-title {
        column-span: 2;
        height: 1fr;
        width: 1fr;
        content-align: center middle;
    }
    """

    BINDINGS = [
        ("escape", "app.quit", "Back"),
        ("ctrl+c", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("⚠️  Terminal too small!", id="warning-title")
        yield Static("Current size is too small for the app to function.")
        yield Static(
            f"Please resize your terminal to at least {MIN_SCREEN_SIZE[0]}x{MIN_SCREEN_SIZE[1]}."
        )


class CFDNSEditApp(App):
    """A multi-screen Textual app for CF DNS editing."""

    CSS = """
    Container {
        align: center middle;
    }
    
    Screen {
        layers: main overlay;
    }
    
    #warning-container {
        layer: overlay;
        align: center middle;
        text-align: center;
        color: red;
        background: black;
        width: 100%;
        height: 100%;
    }
    
    .help-text {
        color: $text-muted;
        text-align: center;
        text-style: italic;
    }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("d", "toggle_dark", "Toggle dark mode"),
        ("left", "app.pop_screen", "Back"),
        ("right", "select_action", "Select"),
        ("up", "navigate_up", "Navigate up"),
        ("down", "navigate_down", "Navigate down"),
    ]

    SCREENS = {
        "login": LoginScreen,
        "manage": DomainManagementScreen,
        "about": AboutScreen,
        "screen_too_small": ScreenTooSmall,
    }

    def __init__(self) -> None:
        """Initialize the app."""
        super().__init__()
        self.title = f"CF DNS Edit v{__version__}"
        self.cf_instance: Cloudflare | None = None

    def on_mount(self) -> None:
        """Initialize the app and show login screen."""
        self._check_screen_size()
        if TOKEN and ApiTokenValidator().validate(TOKEN) == ValidationResult.success():
            try:
                self.cf_instance = Cloudflare(api_token=TOKEN)
                self.cf_instance.user.tokens.verify()
                self.push_screen("manage")
            except Exception:  # pylint: disable=broad-except
                self.notify(
                    "❌ Invalid api key, please login again.",
                    severity="error",
                    timeout=2,
                )
                self.cf_instance = None
                self.push_screen("login")
        else:
            self.push_screen("login")

    def on_resize(self) -> None:
        """Check screen size when app is resized."""
        self._check_screen_size()

    def _check_screen_size(self) -> None:
        """Check if screen size is adequate."""
        size = self.size
        if size.width < MIN_SCREEN_SIZE[0] or size.height < MIN_SCREEN_SIZE[1]:
            if not isinstance(self.screen, ScreenTooSmall):
                self.push_screen("screen_too_small")
        else:
            if isinstance(self.screen, ScreenTooSmall):
                self.pop_screen()

    def compose(self) -> ComposeResult:
        """Compose the main app."""
        yield Footer()

    async def action_quit(self) -> None:
        """Exit the application."""
        self.exit()

    def action_select_action(self) -> None:
        """Handle right arrow key."""
        focused = self.focused
        if isinstance(focused, Button):
            focused.press()
        elif isinstance(focused, Link):
            focused.action_open_link()

    def action_navigate_up(self) -> None:
        """Handle up arrow key."""
        self.action_focus_previous()

    def action_navigate_down(self) -> None:
        """Handle down arrow key."""
        self.action_focus_next()

    def on_screen_resume(self, _) -> None:
        """Called when a screen is resumed (becomes the active screen)."""
        if len(self.screen_stack) == 0:
            self.exit()

    async def action_pop_screen(self) -> None:
        """Override pop screen to exit on specific conditions."""
        if isinstance(self.screen, (LoginScreen, DomainManagementScreen)):
            self.exit()
            return

        if len(self.screen_stack) <= 1:
            self.exit()
        else:
            await super().action_pop_screen()


@click.group(invoke_without_command=True)
@click.option("--version", is_flag=True, help="Show the version of the application")
@click.pass_context
def cli(ctx, version=None):
    """CLI entrypoint."""
    if version:
        click.echo(f"cf-dns-edit version {__version__}")
        sys.exit(0)
    elif ctx.invoked_subcommand is None:
        app = CFDNSEditApp()
        app.run()


if __name__ == "__main__":
    cli()  # pylint: disable=no-value-for-parameter
