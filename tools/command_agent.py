#!/usr/bin/env python3
"""
BigIron Command Agent

Translates natural language to mainframe commands, executes them,
and explains the results.

Usage:
    python command_agent.py "show me all active jobs"
    python command_agent.py --interactive

Requires:
    - Ollama running with bigiron-ai model
    - TK5 MVS running (optional, for actual execution)
"""

import argparse
import json
import re
import subprocess
import sys
from typing import Optional, Tuple

try:
    import httpx
except ImportError:
    print("Installing httpx...")
    subprocess.run([sys.executable, "-m", "pip", "install", "httpx"], check=True)
    import httpx

# Configuration
OLLAMA_URL = "http://localhost:11434"
MODEL = "bigiron-ai"
TK5_CONSOLE_PORT = 3270  # TK5 console port


class CommandAgent:
    """Agent that translates natural language to mainframe commands."""

    def __init__(self, model: str = MODEL, execute: bool = False):
        self.model = model
        self.execute = execute
        self.client = httpx.Client(timeout=60.0)

    def _call_llm(self, prompt: str, system: str = None) -> str:
        """Call the LLM and return response."""
        messages = []

        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self.client.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False
                }
            )

            if response.status_code == 200:
                return response.json().get("message", {}).get("content", "")
            else:
                return f"Error: {response.status_code}"
        except Exception as e:
            return f"Error calling LLM: {e}"

    def translate_to_command(self, natural_language: str) -> Tuple[str, str]:
        """
        Translate natural language to mainframe command.
        Returns (command, explanation).
        """
        system_prompt = """You are a mainframe command translator.
Given a natural language request, respond with:
1. The exact JES2/MVS command to execute (in a code block)
2. A brief explanation of what it does

Be precise. Only output commands that are safe to execute.
For JES2 commands, use $ prefix (e.g., $DA, $DJ).
For MVS commands, use the standard format (e.g., D A,L).
"""

        response = self._call_llm(natural_language, system_prompt)

        # Extract command from code block
        command = ""
        code_match = re.search(r'```(?:\w*\n)?(.*?)```', response, re.DOTALL)
        if code_match:
            command = code_match.group(1).strip().split('\n')[0]
        else:
            # Try to find command pattern
            cmd_match = re.search(r'[`]([$D][A-Z,=\'\*\d\w]+)[`]', response)
            if cmd_match:
                command = cmd_match.group(1)

        return command, response

    def explain_output(self, command: str, output: str) -> str:
        """Have the LLM explain command output."""
        prompt = f"""I ran this mainframe command:
{command}

And got this output:
{output}

Please explain what this output means in plain English.
"""
        return self._call_llm(prompt)

    def execute_command(self, command: str) -> str:
        """
        Execute command on TK5 MVS.
        This is a placeholder - actual implementation depends on your TK5 setup.
        """
        if not self.execute:
            return "[Execution disabled - use --execute to enable]"

        # Option 1: Use x3270/c3270 scripting
        # Option 2: Use Hercules console interface
        # Option 3: Use custom 3270 library

        # For now, simulate with a message
        return f"[Would execute: {command}]\n[Connect TK5 integration for real execution]"

    def process(self, request: str) -> dict:
        """
        Process a natural language request end-to-end.
        Returns dict with command, explanation, output, and analysis.
        """
        result = {
            "request": request,
            "command": "",
            "explanation": "",
            "output": "",
            "analysis": ""
        }

        # Step 1: Translate to command
        print(f"\n🔄 Translating: {request}")
        command, explanation = self.translate_to_command(request)
        result["command"] = command
        result["explanation"] = explanation

        if not command:
            result["explanation"] = "Could not determine the appropriate command."
            return result

        print(f"📋 Command: {command}")

        # Step 2: Execute (if enabled)
        if self.execute:
            print(f"⚡ Executing...")
            output = self.execute_command(command)
            result["output"] = output

            # Step 3: Explain output
            if output and not output.startswith("["):
                print(f"🔍 Analyzing output...")
                analysis = self.explain_output(command, output)
                result["analysis"] = analysis

        return result

    def interactive(self):
        """Run interactive command session."""
        print("""
╔══════════════════════════════════════════════════════════╗
║           BigIron Command Agent - Interactive            ║
╠══════════════════════════════════════════════════════════╣
║  Ask questions in plain English. I'll translate them     ║
║  to mainframe commands and explain the results.          ║
║                                                          ║
║  Examples:                                               ║
║    - "show me all active jobs"                           ║
║    - "cancel job ABC123"                                 ║
║    - "what jobs are waiting for tape"                    ║
║    - "display spool usage"                               ║
║                                                          ║
║  Type 'quit' or 'exit' to leave.                         ║
╚══════════════════════════════════════════════════════════╝
""")

        while True:
            try:
                request = input("\n🖥️  You: ").strip()

                if not request:
                    continue

                if request.lower() in ('quit', 'exit', 'q'):
                    print("Goodbye!")
                    break

                if request.lower() == 'help':
                    print("""
Commands:
  quit/exit  - Exit the agent
  help       - Show this help
  execute on - Enable command execution
  execute off- Disable command execution

Just type your question in plain English!
""")
                    continue

                if request.lower() == 'execute on':
                    self.execute = True
                    print("✓ Command execution enabled")
                    continue

                if request.lower() == 'execute off':
                    self.execute = False
                    print("✓ Command execution disabled")
                    continue

                result = self.process(request)

                print(f"\n{'─'*60}")
                print(f"📋 Command: {result['command']}")
                print(f"\n{result['explanation']}")

                if result['output']:
                    print(f"\n📤 Output:\n{result['output']}")

                if result['analysis']:
                    print(f"\n🔍 Analysis:\n{result['analysis']}")

            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="BigIron Command Agent - Natural language to mainframe commands"
    )
    parser.add_argument(
        "request",
        nargs="?",
        help="Natural language request (e.g., 'show me active jobs')"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode"
    )
    parser.add_argument(
        "--execute", "-x",
        action="store_true",
        help="Actually execute commands on TK5"
    )
    parser.add_argument(
        "--model", "-m",
        default=MODEL,
        help=f"Ollama model to use (default: {MODEL})"
    )

    args = parser.parse_args()

    agent = CommandAgent(model=args.model, execute=args.execute)

    if args.interactive or not args.request:
        agent.interactive()
    else:
        result = agent.process(args.request)

        print(f"\n{'═'*60}")
        print(f"Request: {result['request']}")
        print(f"Command: {result['command']}")
        print(f"\n{result['explanation']}")

        if result['output']:
            print(f"\nOutput:\n{result['output']}")
        if result['analysis']:
            print(f"\nAnalysis:\n{result['analysis']}")


if __name__ == "__main__":
    main()
