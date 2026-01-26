# Security Module

Automated security scanning, vulnerability detection, and session replay for mainframe penetration testing.

## Overview

The `security` module provides:
- **SecurityScanner** - Automated vulnerability and sensitive data detection
- **SecurityReporter** - Generate HTML/JSON/Markdown security reports
- **AutomatedCrawler** - Crawl and map mainframe applications
- **FieldFuzzer** - Input validation testing
- **SessionReplay** - Replay recorded sessions with modifications

## Quick Start

```python
from birpv2_modules.security.scanner import SecurityScanner
from birpv2_modules.security.reporter import SecurityReporter

# Scan transaction history for issues
scanner = SecurityScanner(emulator, history)
findings = scanner.scan_history()

# Generate report
reporter = SecurityReporter(history, findings)
reporter.generate_html_report('security_report.html')
```

## SecurityScanner

Automated scanning for security issues in captured transactions.

### Usage

```python
from birpv2_modules.security.scanner import SecurityScanner

scanner = SecurityScanner(emulator, history)

# Scan all transactions
findings = scanner.scan_history()

# Scan single screen
screen_findings = scanner.scan_screen(screen)

# Detect credentials in modified fields
credentials = scanner.detect_credentials()

# Check access control issues
access_issues = scanner.check_access_control()

# Generate comprehensive report
report = scanner.generate_report()
```

### Detection Patterns

The scanner looks for:

| Type | Description | Severity |
|------|-------------|----------|
| `hidden_field` | Hidden fields containing data | High |
| `unprotected_password` | Password field not marked hidden | Critical |
| `sensitive_data_password` | Password patterns in text | High |
| `sensitive_data_ssn` | Social Security Number patterns | High |
| `sensitive_data_credit_card` | Credit card number patterns | High |
| `sensitive_data_api_key` | API key/token patterns | High |

### Finding Structure

```python
{
    'type': 'hidden_field',
    'severity': 'high',
    'location': '[12,20]',
    'content': 'secretdata',
    'message': 'Hidden field contains data',
    'transaction': 5,
    'screen_type': 'response'
}
```

## SecurityReporter

Generate professional security assessment reports.

### Usage

```python
from birpv2_modules.security.reporter import SecurityReporter

reporter = SecurityReporter(history, findings)

# Generate different formats
reporter.generate_html_report('report.html')   # Styled HTML
reporter.generate_json_report('report.json')   # Machine-readable
reporter.generate_markdown_report('report.md') # Documentation
```

### HTML Report Features

- Executive summary with severity counts
- Color-coded findings by severity
- Hidden field listing
- Transaction analysis
- Recommendations section
- Dark theme styling

## AutomatedCrawler

Automatically explore and map mainframe applications.

### Usage

```python
from birpv2_modules.security.scanner import AutomatedCrawler

crawler = AutomatedCrawler(emulator, history)

# Map application structure
app_map = crawler.map_application()

print(f"Discovered {app_map['total_screens']} screens")
for screen_hash, info in app_map['screen_map'].items():
    print(f"Depth {info['depth']}: {info['screen']}")
```

### Crawling Strategy

The crawler:
1. Reads current screen
2. Hashes screen to detect duplicates
3. Tries numeric menu options (1-9)
4. Recursively explores sub-menus
5. Uses PF3 to go back
6. Builds a map of discovered screens

```python
# Customize crawl depth
crawler.crawl_menu(max_depth=5)  # Explore up to 5 levels deep
```

## FieldFuzzer

Test input field validation with various payloads.

### Usage

```python
from birpv2_modules.security.scanner import FieldFuzzer

fuzzer = FieldFuzzer(emulator)

# Fuzz all input fields on screen
results = fuzzer.fuzz_screen(screen)

# Fuzz specific field
field_results = fuzzer.fuzz_field(
    row=10,
    col=15,
    payloads=fuzzer.payloads
)
```

### Built-in Payloads

| Category | Examples |
|----------|----------|
| `overflow` | A*100, A*500, A*1000, A*5000 |
| `special_chars` | `!@#$%^&*()`, `<>?:"{}|` |
| `sql_injection` | `' OR '1'='1`, `'; DROP TABLE` |
| `command_injection` | `; ls -la`, `| cat /etc/passwd` |
| `format_string` | `%s%s%s%s`, `%n%n%n%n` |
| `null_bytes` | `\x00`, `test\x00test` |
| `unicode` | `\u0000`, `\uffff`, `\u202e` |

### Custom Payloads

```python
custom_payloads = {
    'cics_injection': ['CEMT I TASK', 'CEDA DISPLAY'],
    'jcl_injection': ['//BADSTEP EXEC PGM=IEFBR14']
}
fuzzer.fuzz_field(10, 15, custom_payloads)
```

## SessionReplay

Replay recorded transactions for automation and testing.

### Usage

```python
from birpv2_modules.security.replay import SessionReplay

replay = SessionReplay(emulator, history)

# Replay single transaction
result = replay.replay_transaction(history[0], verify=True)

# Replay session range
results = replay.replay_session(start_idx=0, end_idx=5)

# Replay with modified values
modifications = {
    '10,15': 'NEWUSER',     # row,col: new_value
    '12,20': 'NEWPASSWORD'
}
result = replay.replay_with_modifications(history[0], modifications)
```

### Automated Login

```python
# Single login attempt
result = replay.automated_login(
    userid='TESTUSER',
    password='TESTPASS',
    userid_field=(10, 15),    # Optional - auto-detected if not provided
    password_field=(12, 20)
)

if result['success']:
    print("Login successful!")
```

### Brute Force Testing

```python
# Test credential lists (authorized testing only!)
userids = ['USER1', 'USER2', 'ADMIN']
passwords = ['PASS1', 'PASS2', 'PASSWORD']

results = replay.brute_force_login(
    userids=userids,
    passwords=passwords,
    delay=1  # Delay between attempts in seconds
)
```

## Complete Example

```python
from birpv2_modules.emulator.wrapper import WrappedEmulator
from birpv2_modules.core.models import History
from birpv2_modules.security.scanner import SecurityScanner, AutomatedCrawler
from birpv2_modules.security.reporter import SecurityReporter

# Setup
em = WrappedEmulator(visible=False)
em.connect('localhost:3270')
history = History()

# Crawl application
crawler = AutomatedCrawler(em, history)
app_map = crawler.map_application()

# Scan for vulnerabilities
scanner = SecurityScanner(em, history)
findings = scanner.scan_history()
credentials = scanner.detect_credentials()

# Generate reports
reporter = SecurityReporter(history, findings)
reporter.generate_html_report('assessment.html')
reporter.generate_json_report('findings.json')

# Print summary
print(f"\nSecurity Assessment Summary")
print(f"===========================")
print(f"Screens discovered: {app_map['total_screens']}")
print(f"Transactions analyzed: {len(history)}")
print(f"Findings: {len(findings)}")
print(f"Credentials detected: {len(credentials)}")
```

## Module Contents

### scanner.py

| Class | Description |
|-------|-------------|
| `SecurityScanner` | Vulnerability and data scanning |
| `AutomatedCrawler` | Application mapping |
| `FieldFuzzer` | Input validation testing |

### reporter.py

| Class | Description |
|-------|-------------|
| `SecurityReporter` | Report generation |

### replay.py

| Class | Description |
|-------|-------------|
| `SessionReplay` | Transaction replay and automation |

## See Also

- [Core README](../core/README.md) - Screen and Transaction classes
- [Emulator README](../emulator/README.md) - TN3270 wrapper
- [IO README](../io/README.md) - Additional export options
- [Integrations README](../integrations/README.md) - Mainframed tools
