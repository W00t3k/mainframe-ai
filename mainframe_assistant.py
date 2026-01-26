#!/usr/bin/env python3
"""
Mainframe AI Assistant - Natural language interface for z/OS operations

Combines Claude AI with TN3270 connectivity for intelligent mainframe interaction.
"""

import os
import sys
import json
from typing import Optional
from dataclasses import dataclass, field

# Add BIRP to path if available
BIRP_PATH = os.path.expanduser("~/Desktop/STuFF /birp")
if os.path.exists(BIRP_PATH):
    sys.path.insert(0, BIRP_PATH)

try:
    from anthropic import Anthropic
except ImportError:
    print("Run: pip install anthropic")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    from rich.table import Table
    from prompt_toolkit import prompt
    from prompt_toolkit.history import FileHistory
except ImportError:
    print("Run: pip install rich prompt_toolkit")
    sys.exit(1)


# Try to import BIRP modules
BIRP_AVAILABLE = False
try:
    from birpv2_modules.emulator.wrapper import WrappedEmulator
    from birpv2_modules.core.models import Screen, History
    BIRP_AVAILABLE = True
except ImportError:
    pass


SYSTEM_PROMPT = """You are an expert mainframe systems programmer and z/OS administrator assistant.

## Your Capabilities
- Explain z/OS concepts, JCL, COBOL, REXX, CLIST, Assembler
- Help navigate TSO/ISPF, CICS, JES2/JES3
- Interpret ABEND codes and system messages
- Generate JCL for common tasks
- Explain screen output from 3270 terminals
- Assist with RACF security, SMS, catalog management
- Debug batch jobs and analyze SYSOUT

## When Connected to a Mainframe
You can execute commands via the TN3270 connection. Available actions:
- SEND_KEYS: Send text/commands to the terminal
- SEND_ENTER: Press Enter key
- SEND_PF: Press PF key (PF1-PF24)
- SEND_PA: Press PA key (PA1-PA3)
- SEND_CLEAR: Clear screen
- READ_SCREEN: Get current screen content
- GET_CURSOR: Get cursor position

Format commands as JSON:
{"action": "SEND_KEYS", "value": "TSO"}
{"action": "SEND_PF", "value": 3}

## Response Guidelines
- Be concise but thorough
- For JCL/code, always explain key parameters
- Warn about potentially destructive operations
- When unsure, ask clarifying questions
- Reference IBM documentation when appropriate

## Common ABEND Codes Reference
- S0C1: Operation exception (invalid instruction)
- S0C4: Protection exception (storage violation)
- S0C7: Data exception (invalid packed decimal)
- S0CB: Division by zero
- S222: Job cancelled by operator
- S322: CPU time limit exceeded
- S722: SYSOUT limit exceeded
- S806: Module not found
- S913: RACF authorization failure
- SB37: Dataset out of space

You are helpful, accurate, and safety-conscious about mainframe operations."""


@dataclass
class MainframeConnection:
    """Manages TN3270 connection state"""
    host: str = ""
    port: int = 23
    connected: bool = False
    emulator: Optional[object] = None
    history: list = field(default_factory=list)
    current_screen: str = ""


class MainframeAssistant:
    """AI-powered mainframe assistant"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY required. Set env var or pass api_key.")

        self.client = Anthropic(api_key=self.api_key)
        self.console = Console()
        self.connection = MainframeConnection()
        self.conversation_history = []
        self.model = "claude-sonnet-4-20250514"

    def connect(self, target: str) -> bool:
        """Connect to mainframe via TN3270"""
        if not BIRP_AVAILABLE:
            self.console.print("[yellow]BIRP not available. Running in offline mode.[/yellow]")
            self.console.print(f"[dim]Would connect to: {target}[/dim]")
            return False

        try:
            # Parse target
            if ":" in target:
                host, port = target.rsplit(":", 1)
                port = int(port)
            else:
                host = target
                port = 23

            self.connection.host = host
            self.connection.port = port

            # Create emulator
            self.connection.emulator = WrappedEmulator(visible=False)
            self.connection.emulator.connect(f"{host}:{port}")
            self.connection.connected = True

            self.console.print(f"[green]Connected to {host}:{port}[/green]")
            return True

        except Exception as e:
            self.console.print(f"[red]Connection failed: {e}[/red]")
            return False

    def read_screen(self) -> str:
        """Read current screen content"""
        if not self.connection.connected or not self.connection.emulator:
            return "[Not connected to mainframe]"

        try:
            buffer = self.connection.emulator.exec_command(b'ReadBuffer(Ascii)').data
            screen = Screen(buffer)
            self.connection.current_screen = str(screen)
            return self.connection.current_screen
        except Exception as e:
            return f"[Error reading screen: {e}]"

    def execute_action(self, action: dict) -> str:
        """Execute a mainframe action"""
        if not self.connection.connected or not self.connection.emulator:
            return "[Not connected - cannot execute]"

        try:
            em = self.connection.emulator
            act = action.get("action", "").upper()
            value = action.get("value", "")

            if act == "SEND_KEYS":
                em.send_string(value)
                return f"Sent: {value}"
            elif act == "SEND_ENTER":
                em.send_enter()
                return "Pressed Enter"
            elif act == "SEND_PF":
                em.send_pf(int(value))
                return f"Pressed PF{value}"
            elif act == "SEND_PA":
                em.send_pa(int(value))
                return f"Pressed PA{value}"
            elif act == "SEND_CLEAR":
                em.send_clear()
                return "Cleared screen"
            elif act == "READ_SCREEN":
                return self.read_screen()
            elif act == "GET_CURSOR":
                row, col = em.get_cursor_position()
                return f"Cursor at row {row}, column {col}"
            else:
                return f"Unknown action: {act}"

        except Exception as e:
            return f"[Action error: {e}]"

    def chat(self, user_message: str) -> str:
        """Send message to Claude and get response"""
        # Add screen context if connected
        context = ""
        if self.connection.connected:
            screen = self.read_screen()
            context = f"\n\n[Current 3270 Screen]\n```\n{screen}\n```\n"

        # Build message with context
        full_message = user_message
        if context and "screen" in user_message.lower():
            full_message = user_message + context

        self.conversation_history.append({
            "role": "user",
            "content": full_message
        })

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=self.conversation_history
            )

            assistant_message = response.content[0].text
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_message
            })

            # Check for action commands in response
            self._process_actions(assistant_message)

            return assistant_message

        except Exception as e:
            return f"[API Error: {e}]"

    def _process_actions(self, response: str):
        """Extract and execute any action commands from response"""
        import re

        # Find JSON action blocks
        pattern = r'\{"action":\s*"[^"]+",\s*"value":\s*[^}]+\}'
        matches = re.findall(pattern, response)

        for match in matches:
            try:
                action = json.loads(match)
                if self.connection.connected:
                    result = self.execute_action(action)
                    self.console.print(f"[dim]Executed: {result}[/dim]")
            except json.JSONDecodeError:
                pass

    def run_interactive(self):
        """Run interactive chat loop"""
        self.console.print(Panel.fit(
            "[bold blue]Mainframe AI Assistant[/bold blue]\n"
            "Natural language interface for z/OS operations\n\n"
            "Commands:\n"
            "  /connect <host:port> - Connect to mainframe\n"
            "  /screen             - Show current screen\n"
            "  /disconnect         - Disconnect\n"
            "  /clear              - Clear conversation\n"
            "  /help               - Show help\n"
            "  /quit               - Exit",
            title="Welcome"
        ))

        history_file = os.path.expanduser("~/.mainframe_assistant_history")

        while True:
            try:
                # Show connection status in prompt
                status = "[green]●[/green]" if self.connection.connected else "[red]○[/red]"
                prompt_text = f"{status} You: "

                user_input = prompt(
                    prompt_text,
                    history=FileHistory(history_file)
                ).strip()

                if not user_input:
                    continue

                # Handle commands
                if user_input.startswith("/"):
                    self._handle_command(user_input)
                    continue

                # Chat with Claude
                self.console.print()
                with self.console.status("[bold blue]Thinking...[/bold blue]"):
                    response = self.chat(user_input)

                self.console.print(Panel(
                    Markdown(response),
                    title="[bold blue]Assistant[/bold blue]",
                    border_style="blue"
                ))
                self.console.print()

            except KeyboardInterrupt:
                self.console.print("\n[yellow]Use /quit to exit[/yellow]")
            except EOFError:
                break

    def _handle_command(self, cmd: str):
        """Handle slash commands"""
        parts = cmd.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if command == "/quit" or command == "/exit":
            if self.connection.connected:
                self.connection.emulator.terminate()
            self.console.print("[yellow]Goodbye![/yellow]")
            sys.exit(0)

        elif command == "/connect":
            if not args:
                self.console.print("[red]Usage: /connect host:port[/red]")
                return
            self.connect(args)

        elif command == "/disconnect":
            if self.connection.connected:
                self.connection.emulator.terminate()
                self.connection.connected = False
                self.console.print("[yellow]Disconnected[/yellow]")
            else:
                self.console.print("[yellow]Not connected[/yellow]")

        elif command == "/screen":
            if self.connection.connected:
                screen = self.read_screen()
                self.console.print(Panel(screen, title="Current Screen"))
            else:
                self.console.print("[yellow]Not connected[/yellow]")

        elif command == "/clear":
            self.conversation_history = []
            self.console.print("[green]Conversation cleared[/green]")

        elif command == "/help":
            self._show_help()

        else:
            self.console.print(f"[red]Unknown command: {command}[/red]")

    def _show_help(self):
        """Show help information"""
        help_table = Table(title="Mainframe AI Assistant Help")
        help_table.add_column("Command", style="cyan")
        help_table.add_column("Description")

        help_table.add_row("/connect <host:port>", "Connect to mainframe via TN3270")
        help_table.add_row("/screen", "Display current 3270 screen")
        help_table.add_row("/disconnect", "Close mainframe connection")
        help_table.add_row("/clear", "Clear conversation history")
        help_table.add_row("/quit", "Exit the assistant")
        help_table.add_row("", "")
        help_table.add_row("[bold]Examples:[/bold]", "")
        help_table.add_row("", "What does ABEND S0C7 mean?")
        help_table.add_row("", "Generate JCL to copy a dataset")
        help_table.add_row("", "Explain the current screen")
        help_table.add_row("", "How do I allocate a new PDS?")

        self.console.print(help_table)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Mainframe AI Assistant")
    parser.add_argument("-t", "--target", help="Connect to mainframe (host:port)")
    parser.add_argument("-k", "--api-key", help="Anthropic API key")
    parser.add_argument("--model", default="claude-sonnet-4-20250514", help="Claude model to use")
    args = parser.parse_args()

    try:
        assistant = MainframeAssistant(api_key=args.api_key)
        assistant.model = args.model

        if args.target:
            assistant.connect(args.target)

        assistant.run_interactive()

    except ValueError as e:
        print(f"Error: {e}")
        print("\nSet your API key:")
        print("  export ANTHROPIC_API_KEY='your-key'")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nGoodbye!")


if __name__ == "__main__":
    main()
