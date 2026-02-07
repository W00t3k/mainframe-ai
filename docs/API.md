# API Reference

Complete API documentation for TN3270 v2 modules.

## Table of Contents

- [Core Models](#core-models)
- [Emulator](#emulator)
- [Security](#security)
- [I/O](#io)
- [z/OS Helpers](#zos-helpers)
- [Utilities](#utilities)

---

## Core Models

### Field

```python
class Field:
    """Represents a single 3270 screen field"""

    def __init__(
        self,
        contents: str,        # Field text content
        row: int,             # Row position (0-indexed)
        col: int,             # Column position (0-indexed)
        rawstatus: str,       # Raw x3270 field status
        printable: int = 0,   # Is printable
        protected: int = 0,   # Is read-only
        numeric: int = 0,     # Numeric-only input
        hidden: int = 0,      # Is hidden/password
        normnsel: int = 0,    # Normal, non-selectable
        normsel: int = 0,     # Normal, selectable
        highsel: int = 0,     # Intensified, selectable
        zeronsel: int = 0,    # Non-display
        reserved: int = 0,    # Reserved
        modify: int = 0       # Was modified
    )

    def __str__(self) -> str: ...
    def __len__(self) -> int: ...
    def __repr__(self) -> str: ...
```

### Screen

```python
class Screen:
    """Represents a complete 3270 terminal screen"""

    def __init__(self, rawbuff: list): ...

    @property
    def rows(self) -> int: ...
    @property
    def cols(self) -> int: ...
    @property
    def rawbuffer(self) -> list: ...
    @property
    def plainbuffer(self) -> list: ...
    @property
    def stringbuffer(self) -> list[str]: ...
    @property
    def colorbuffer(self) -> str: ...
    @property
    def emubuffer(self) -> str: ...
    @property
    def fields(self) -> list[Field]: ...
    @property
    def protected_fields(self) -> list[Field]: ...
    @property
    def input_fields(self) -> list[Field]: ...
    @property
    def hidden_fields(self) -> list[Field]: ...
    @property
    def modified_fields(self) -> list[Field]: ...

    def __str__(self) -> str: ...
    def __repr__(self) -> str: ...
```

### Transaction

```python
class Transaction:
    """Represents a TN3270 request/response pair"""

    def __init__(
        self,
        request: Screen,      # Screen before action
        response: Screen,     # Screen after action
        data: list[Field],    # Modified fields
        key: str = 'enter',   # Triggering key
        host: str = '',       # Target host
        comment: str = ''     # Optional comment
    )

    timestamp: datetime       # When recorded
```

### History

```python
class History:
    """Container for transaction history"""

    def __init__(self): ...
    def __getitem__(self, index: int) -> Transaction: ...
    def __len__(self) -> int: ...
    def __iter__(self) -> Iterator[Transaction]: ...
    def append(self, transaction: Transaction) -> None: ...
    def last(self) -> Transaction: ...
    def count(self) -> int: ...
```

---

## Emulator

### WrappedEmulator

```python
class WrappedEmulator(Emulator):
    """TN3270 emulator with timeout protection"""

    def __init__(
        self,
        visible: bool = True,           # GUI vs headless
        delay: float = 0,               # Command delay
        window_title: str = "TN3270 v2",  # Window title
        command_timeout: int = 10       # Default timeout
    )

    # Connection
    def connect(self, host_port: str, timeout: int = 30) -> None: ...
    def is_connected(self, timeout: int = 2) -> bool: ...
    def get_hostinfo(self, timeout: int = 2) -> list: ...

    # Commands
    def exec_command(self, command: bytes) -> Result: ...
    def exec_command_with_timeout(
        self, command: bytes, timeout: int = None
    ) -> Result: ...
    def safe_exec_command(
        self, command: bytes, timeout: int = None, default: Any = None
    ) -> Result: ...

    # Input
    def send_string(self, text: str) -> None: ...
    def safe_send_string(self, text: str, timeout: int = 5) -> bool: ...
    def send_enter(self) -> None: ...
    def safe_send_pf(self, key_num: int, timeout: int = 5) -> bool: ...
    def safe_send(self, text: str) -> bool: ...
    def safe_fieldfill(
        self, ypos: int, xpos: int, tosend: str, length: int
    ) -> bool: ...

    # Screen
    def screen_get(self, timeout: int = 5) -> list: ...
    def find_response(self, response: str) -> bool: ...
    def get_pos(self, timeout: int = 2) -> tuple[int, int]: ...
    def take_screenshot(self, filename: str = None) -> str: ...

    # Utility
    def move_to(self, row: int, col: int) -> None: ...
    def delete_field(self) -> None: ...
    def set_window_title(self, title: str) -> None: ...
```

### TimeoutError

```python
class TimeoutError(Exception):
    """Raised when a command times out"""
    pass
```

---

## Security

### SecurityScanner

```python
class SecurityScanner:
    """Automated security scanner"""

    def __init__(self, emulator: WrappedEmulator, history: History): ...

    patterns: dict[str, list[str]]  # Detection patterns
    findings: list[dict]            # Scan results

    def scan_screen(self, screen: Screen) -> list[dict]: ...
    def scan_history(self) -> list[dict]: ...
    def detect_credentials(self) -> list[dict]: ...
    def check_access_control(self) -> list[dict]: ...
    def generate_report(self) -> dict: ...
```

### AutomatedCrawler

```python
class AutomatedCrawler:
    """Application crawler"""

    def __init__(self, emulator: WrappedEmulator, history: History): ...

    visited_screens: set
    screen_map: dict

    def get_screen_hash(self, screen: Screen) -> int: ...
    def crawl_menu(self, max_depth: int = 3, current_depth: int = 0) -> None: ...
    def map_application(self) -> dict: ...
```

### FieldFuzzer

```python
class FieldFuzzer:
    """Input field fuzzer"""

    def __init__(self, emulator: WrappedEmulator): ...

    payloads: dict[str, list[str]]  # Fuzzing payloads
    results: list[dict]             # Fuzzing results

    def fuzz_field(
        self, row: int, col: int, payloads: dict
    ) -> list[dict]: ...
    def fuzz_screen(self, screen: Screen) -> list[dict]: ...
```

### SessionReplay

```python
class SessionReplay:
    """Session replay engine"""

    def __init__(self, emulator: WrappedEmulator, history: History): ...

    replay_log: list[dict]

    def replay_transaction(
        self, transaction: Transaction, verify: bool = True
    ) -> dict: ...
    def replay_session(
        self, start_idx: int = 0, end_idx: int = None, verify: bool = True
    ) -> list[dict]: ...
    def replay_with_modifications(
        self, transaction: Transaction, field_modifications: dict
    ) -> dict: ...
    def automated_login(
        self,
        userid: str,
        password: str,
        userid_field: tuple = None,
        password_field: tuple = None
    ) -> dict: ...
    def brute_force_login(
        self, userids: list, passwords: list, delay: int = 1
    ) -> list[dict]: ...
```

### SecurityReporter

```python
class SecurityReporter:
    """Security report generator"""

    def __init__(self, history: History, findings: list = None): ...

    def generate_html_report(self, filename: str = 'security_report.html') -> str: ...
    def generate_json_report(self, filename: str = 'security_report.json') -> str: ...
    def generate_markdown_report(self, filename: str = 'security_report.md') -> str: ...
```

---

## I/O

### Exporters

```python
def export_to_json(
    history: History, filename: str, pretty: bool = True
) -> bool: ...

def export_to_csv(history: History, filename: str) -> bool: ...

def export_to_html(history: History, filename: str) -> bool: ...

def export_to_xml(history: History, filename: str) -> bool: ...

def auto_export(history: History, filename: str) -> bool: ...
```

### File Operations

```python
def save_history(history: History, filename: str) -> None: ...
def load_history(filename: str) -> History: ...
```

---

## z/OS Helpers

### CICSHelper

```python
class CICSHelper:
    """CICS transaction helper"""

    def detect_cics_screen(self, screen_text: str) -> bool: ...
    def parse_cics_message(self, screen_text: str) -> list[dict]: ...
    def extract_transaction_id(self, screen_text: str) -> str: ...
    def parse_cemt_output(self, screen_text: str) -> list[dict]: ...
    def parse_cedf_screen(self, screen_text: str) -> dict: ...
    def parse_sign_on_screen(self, screen_text: str) -> dict: ...
    def suggest_cics_commands(self, context: str) -> list[str]: ...
    def check_cics_error(self, screen_text: str) -> list[str]: ...
```

### TSOHelper

```python
class TSOHelper:
    """TSO/ISPF helper"""

    def detect_tso_screen(self, screen_text: str) -> bool: ...
    def detect_ispf_panel(self, screen_text: str) -> str: ...
    def parse_dataset_list(self, screen_text: str) -> list[dict]: ...
    def parse_member_list(self, screen_text: str) -> list[dict]: ...
    def parse_tso_messages(self, screen_text: str) -> list[str]: ...
    def extract_command_result(self, screen_text: str) -> dict: ...
    def suggest_tso_commands(self, context: str) -> list[str]: ...
    def parse_allocation_screen(self, screen_text: str) -> dict: ...
    def check_dataset_exists(self, screen_text: str) -> bool: ...
```

### RACFHelper

```python
class RACFHelper:
    """RACF security helper"""

    def parse_listuser_output(self, screen_text: str) -> dict: ...
    def parse_listgrp_output(self, screen_text: str) -> dict: ...
    def parse_listdsd_output(self, screen_text: str) -> dict: ...
    def detect_racf_screen(self, screen_text: str) -> bool: ...
    def extract_racf_messages(self, screen_text: str) -> list[str]: ...
    def check_access_denied(self, screen_text: str) -> bool: ...
    def suggest_racf_commands(self, context: str) -> list[str]: ...
```

### JESParser

```python
class JESParser:
    """JES job parser"""

    def parse_job_list(self, screen_text: str) -> list[dict]: ...
    def find_jobid(self, screen_text: str) -> str: ...
    def parse_job_output(self, screen_text: str) -> dict: ...
    def create_jcl(
        self, jobname: str, stepname: str, program: str, params: str = None
    ) -> str: ...
    def parse_allocation_messages(self, screen_text: str) -> list[dict]: ...
    def detect_jes_screen(self, screen_text: str) -> bool: ...
    def extract_spool_info(self, screen_text: str) -> list[dict]: ...
```

---

## Utilities

### Logger

```python
class TN3270Logger:
    """Colored console logger"""

    def __init__(
        self,
        quiet: bool = False,
        log_file: str = None,
        log_level: int = logging.INFO
    ): ...

    def log(self, text: str, kind: str = 'clear', level: int = 0) -> None: ...
    def debug(self, message: str, level: int = 0) -> None: ...
    def info(self, message: str, level: int = 0) -> None: ...
    def warning(self, message: str, level: int = 0) -> None: ...
    def error(self, message: str, level: int = 0) -> None: ...
    def success(self, message: str, level: int = 0) -> None: ...

# Global functions
def setup_logger(log_file: str = None, log_level: str = 'INFO') -> None: ...
def get_logger() -> TN3270Logger: ...
def log_info(message: str, level: int = 0) -> None: ...
def log_warning(message: str, level: int = 0) -> None: ...
def log_error(message: str, level: int = 0) -> None: ...
def log_debug(message: str, level: int = 0) -> None: ...
def log_success(message: str, level: int = 0) -> None: ...
def create_logger(
    quiet: bool = False, log_file: str = None, log_level: int = logging.INFO
) -> TN3270Logger: ...
```

### Search

```python
def find_first(
    history: History, text: str
) -> tuple[int, int, int, int]: ...
# Returns: (trans_id, req/resp, row, col) or (-1, -1, -1, -1)

def find_all(
    history: History,
    text: str,
    case_sensitive: bool = True,
    use_regex: bool = False
) -> list[tuple[int, int, int, int]]: ...
# Returns: [(trans_id, req/resp, row, col), ...]
```

### Getch

```python
def getch() -> str:
    """Read single character from keyboard"""
    ...
```

---

## Integrations

### MainframedIntegration

```python
class MainframedIntegration:
    """Mainframed tools integration"""

    def __init__(self, tools_path: str = None): ...

    tools: dict              # Tool definitions
    attribution: dict        # Attribution info

    def print_attribution(self) -> None: ...
    def list_tools(self) -> None: ...
    def check_tool_installed(self, tool_id: str) -> bool: ...
    def install_tool(self, tool_id: str) -> bool: ...
    def install_all_tools(self) -> None: ...
    def generate_tool_report(self) -> dict: ...

    # Tool launchers
    def launch_hack3270(
        self, target: str = None, proxy_port: int = 2323, args: list = None
    ) -> bool: ...
    def run_nmap_script(
        self, script_name: str, target: str, args: list = None
    ) -> bool: ...
    def tso_enumerate(
        self, target: str, userlist: str = None, commands: str = ''
    ) -> bool: ...
    def tso_brute_force(
        self, target: str, userlist: str = None,
        passlist: str = None, commands: str = ''
    ) -> bool: ...
    def cics_enumerate(self, target: str, commands: str = 'cics') -> bool: ...
    def grab_screen(self, target: str) -> bool: ...
    def find_hidden_fields(self, target: str) -> bool: ...
    def launch_setn3270(
        self, listen_port: int = 3270, target: str = None
    ) -> bool: ...
    def launch_mfsniffer(
        self, interface: str = 'eth0', ip_address: str = None, port: str = '23'
    ) -> bool: ...
    def show_privesc_examples(self) -> None: ...
```
