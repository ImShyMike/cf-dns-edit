"""Main entry point for cf-dns-edit."""

import os
import sys

import click
from cloudflare import Cloudflare
from dotenv import load_dotenv
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.validation import ValidationResult, Validator
from textual.widgets import Button, Footer, Input, Link, LoadingIndicator, Static

from cf_dns_edit.__about__ import __version__

load_dotenv()

MIN_SCREEN_SIZE = (71, 32)  # magic numbers :D
TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")

cf = Cloudflare(api_token=TOKEN)


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
    ]

    def compose(self) -> ComposeResult:
        with Container(id="login-container"):
            with Vertical():
                yield Static("🔐 Login to Cloudflare", id="login-title")
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
            self.app.notify("✅ Login successful!")
            self.app.push_screen("manage")
        else:
            self.app.notify(
                "❌ Invalid api key, please try again.", severity="error", timeout=2
            )


    def action_login(self) -> None:
        """Handle login action."""
        self.call_next(self.handle_login)

    async def verify_token(self, token: str) -> bool:
        """Verify the API token asynchronously."""
        try:
            cf_instance = Cloudflare(api_token=token)
            cf_instance.user.tokens.verify()
            app = self.app
            if hasattr(app, 'cf_instance'):
                app.cf_instance = cf_instance  # type: ignore # pylint: disable=attribute-defined-outside-init
            return True
        except Exception:  # pylint: disable=broad-except
            app = self.app
            if hasattr(app, 'cf_instance'):
                app.cf_instance = None  # type: ignore # pylint: disable=attribute-defined-outside-init
            return False


class DnsManagementScreen(Screen):
    """Main DNS management screen."""

    CSS = """
    DnsManagementScreen {
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
    ]

    def compose(self) -> ComposeResult:
        with Container(id="main-container"):
            with Container(id="button-panel"):
                with Vertical():
                    yield Static("📚 DNS Records Manager", id="title")
                    yield Static("")
                    yield Button("📋 List DNS Records", id="list")
                    yield Button("➕ Add DNS Record", id="add")
                    yield Button("✏️  Update DNS Record", id="update")
                    yield Button("🗑️  Delete DNS Record", id="delete")
                    yield Static("")
                    yield Button("ℹ️  About", id="about-btn")
                    yield Button("🚪 Logout", id="logout-btn")
            with Container(id="info-panel"):
                with Vertical():
                    yield Static("Cloudflare DNS Manager", id="info-title")
                    yield Static("")
                    yield Static("This is a placeholder")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Button handling for the book screen."""
        if event.button.id == "list":
            self.app.notify("📋 Listing DNS records...")
        elif event.button.id == "add":
            self.app.notify("➕ Adding DNS record...")
        elif event.button.id == "update":
            self.app.notify("✏️ Updating DNS record...")
        elif event.button.id == "delete":
            self.app.notify("🗑️ Deleting DNS record...")
        elif event.button.id == "about-btn":
            self.app.push_screen("about")
        elif event.button.id == "logout-btn":
            self.action_logout()

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
        "manage": DnsManagementScreen,
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
        """Compose the main app - screens will handle their own composition."""
        yield Footer()

    async def action_quit(self) -> None:
        """Exit the application."""
        self.exit()

    def action_select_action(self) -> None:
        """Handle right arrow key."""
        current_screen = self.screen
        if isinstance(current_screen, LoginScreen):
            if self.focused is not current_screen.query_one("#token-link", Link):
                current_screen.action_login()
            else:
                focused_link = current_screen.query_one("#token-link", Link)
                focused_link.action_open_link()
        elif isinstance(current_screen, DnsManagementScreen):
            self.notify("Use buttons or keyboard shortcuts for actions")
        elif isinstance(current_screen, AboutScreen):
            self.push_screen("manage")

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
        if isinstance(self.screen, (LoginScreen, DnsManagementScreen)):
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
    cli()
