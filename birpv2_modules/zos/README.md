# z/OS Module

z/OS-specific helpers for parsing and interacting with mainframe subsystems.

## Overview

The `zos` module provides specialized parsers and helpers for:
- **CICS** - Customer Information Control System transactions
- **TSO** - Time Sharing Option and ISPF
- **RACF** - Resource Access Control Facility security
- **JES** - Job Entry Subsystem job management

## CICSHelper

Helper for CICS transaction processing and screen parsing.

### Detection and Parsing

```python
from birpv2_modules.zos.cics_helper import CICSHelper

cics = CICSHelper()

# Detect if screen is CICS
if cics.detect_cics_screen(screen_text):
    print("CICS screen detected")

# Extract transaction ID
trans_id = cics.extract_transaction_id(screen_text)  # e.g., "CESN"

# Parse CICS messages (DFH prefixed)
messages = cics.parse_cics_message(screen_text)
for msg in messages:
    print(f"{msg['code']}: {msg['text']}")
```

### CEMT (Master Terminal) Parsing

```python
# Parse CEMT INQUIRE output
resources = cics.parse_cemt_output(screen_text)
for res in resources:
    print(f"{res['type']}: {res['name']} - {res['status']}")
    # TRANSACTION: CESN - ENABLED
```

### CEDF (Debug) Parsing

```python
# Parse CEDF execution diagnostic output
debug_info = cics.parse_cedf_screen(screen_text)
print(f"Transaction: {debug_info['transaction']}")
print(f"Program: {debug_info['program']}")
print(f"Command: {debug_info['command']}")
print(f"Response: {debug_info['response']}")
print(f"EIB Fields: {debug_info['eib_fields']}")
```

### Sign-on Screen

```python
# Parse CESN sign-on screen
sign_on = cics.parse_sign_on_screen(screen_text)
print(f"APPLID: {sign_on['applid']}")
```

### Error Detection

```python
# Check for CICS errors
errors = cics.check_cics_error(screen_text)
if errors:
    print(f"CICS Errors: {errors}")
    # ['NOTAUTH', 'PGMIDERR']
```

### Command Suggestions

```python
# Get suggested commands
suggestions = cics.suggest_cics_commands('user')
for cmd in suggestions:
    print(cmd)
```

## TSOHelper

Helper for TSO/ISPF operations.

### Detection

```python
from birpv2_modules.zos.tso_helper import TSOHelper

tso = TSOHelper()

# Detect TSO screen
if tso.detect_tso_screen(screen_text):
    print("TSO/ISPF detected")

# Detect specific ISPF panel
panel = tso.detect_ispf_panel(screen_text)
# Returns: 'PRIMARY', 'DSLIST', 'EDIT', 'BROWSE', etc.
```

### Dataset Operations

```python
# Parse dataset list (DSLIST / 3.4)
datasets = tso.parse_dataset_list(screen_text)
for ds in datasets:
    print(f"{ds['name']} - Vol: {ds['volume']} DSORG: {ds['dsorg']}")

# Parse PDS member list
members = tso.parse_member_list(screen_text)
for member in members:
    print(f"{member['name']} - Changed: {member['changed']} by {member['id']}")

# Parse allocation screen
alloc = tso.parse_allocation_screen(screen_text)
print(f"Dataset: {alloc['dsname']}, RECFM: {alloc['recfm']}, LRECL: {alloc['lrecl']}")

# Check if dataset exists
if tso.check_dataset_exists(screen_text):
    print("Dataset found")
```

### TSO Messages

```python
# Parse TSO system messages (IKJ, IEF, etc.)
messages = tso.parse_tso_messages(screen_text)
for msg in messages:
    print(msg)

# Extract command result
result = tso.extract_command_result(screen_text)
print(f"Command: {result['command']}")
print(f"Return Code: {result['return_code']}")
```

### Command Suggestions

```python
suggestions = tso.suggest_tso_commands('dataset')
for cmd in suggestions:
    print(cmd)
```

## RACFHelper

Helper for RACF security operations.

### User Profile Parsing

```python
from birpv2_modules.zos.racf_helper import RACFHelper

racf = RACFHelper()

# Parse LISTUSER output
profile = racf.parse_listuser_output(screen_text)
print(f"User: {profile['userid']}")
print(f"Name: {profile['name']}")
print(f"Groups: {profile['groups']}")
print(f"Attributes: {profile['attributes']}")
print(f"Special: {profile['special']}")
print(f"Operations: {profile['operations']}")
print(f"Revoked: {profile['revoked']}")
```

### Group Parsing

```python
# Parse LISTGRP output
group = racf.parse_listgrp_output(screen_text)
print(f"Group: {group['groupid']}")
print(f"Owner: {group['owner']}")
print(f"Members: {group['members']}")
```

### Dataset Security

```python
# Parse LISTDSD output
dataset = racf.parse_listdsd_output(screen_text)
print(f"Dataset: {dataset['name']}")
print(f"Owner: {dataset['owner']}")
print(f"UACC: {dataset['universal_access']}")
for access in dataset['access_list']:
    print(f"  {access['id']}: {access['access']}")
```

### Security Messages

```python
# Extract RACF messages (ICH prefixed)
messages = racf.extract_racf_messages(screen_text)

# Check for access denied
if racf.check_access_denied(screen_text):
    print("Access denied!")
```

### Command Suggestions

```python
suggestions = racf.suggest_racf_commands('user')
# ['LISTUSER userid', 'SEARCH CLASS(USER) MASK(pattern*)']
```

## JESParser

Parser for JES job management.

### Job List Parsing

```python
from birpv2_modules.zos.jes_parser import JESParser

jes = JESParser()

# Parse job queue display
jobs = jes.parse_job_list(screen_text)
for job in jobs:
    print(f"{job['jobname']} ({job['jobid']}) - Status: {job['status']}")

# Find job ID in screen
jobid = jes.find_jobid(screen_text)  # e.g., "JOB00123"
```

### Job Output Parsing

```python
# Parse job output (SDSF)
output = jes.parse_job_output(screen_text)
print(f"Job: {output['jobname']} ({output['jobid']})")
print(f"Return Code: {output['return_code']}")
for step in output['steps']:
    print(f"  Step: {step['name']} RC={step['return_code']}")
for msg in output['messages']:
    print(f"  {msg}")
```

### SPOOL Files

```python
# Extract SPOOL file info
spool_files = jes.extract_spool_info(screen_text)
for f in spool_files:
    print(f"{f['ddname']} ({f['stepname']}): {f['records']} records")

# Parse allocation messages
allocations = jes.parse_allocation_messages(screen_text)
for a in allocations:
    print(f"{a['type']}: {a['dataset']}")
```

### JCL Generation

```python
# Generate basic JCL
jcl = jes.create_jcl(
    jobname='TESTJOB',
    stepname='STEP01',
    program='IEBCOPY',
    params='LIST=NO'
)
print(jcl)
```

### Screen Detection

```python
if jes.detect_jes_screen(screen_text):
    print("JES/SDSF screen detected")
```

## Complete Example

```python
from birpv2_modules.zos.cics_helper import CICSHelper
from birpv2_modules.zos.tso_helper import TSOHelper
from birpv2_modules.zos.racf_helper import RACFHelper
from birpv2_modules.zos.jes_parser import JESParser

# Initialize helpers
cics = CICSHelper()
tso = TSOHelper()
racf = RACFHelper()
jes = JESParser()

def analyze_screen(screen_text):
    """Analyze mainframe screen and return context"""

    # Detect screen type
    if cics.detect_cics_screen(screen_text):
        trans_id = cics.extract_transaction_id(screen_text)
        errors = cics.check_cics_error(screen_text)
        return {
            'type': 'CICS',
            'transaction': trans_id,
            'errors': errors,
            'suggestions': cics.suggest_cics_commands('')
        }

    elif tso.detect_tso_screen(screen_text):
        panel = tso.detect_ispf_panel(screen_text)
        messages = tso.parse_tso_messages(screen_text)
        return {
            'type': 'TSO',
            'panel': panel,
            'messages': messages,
            'suggestions': tso.suggest_tso_commands('')
        }

    elif racf.detect_racf_screen(screen_text):
        messages = racf.extract_racf_messages(screen_text)
        denied = racf.check_access_denied(screen_text)
        return {
            'type': 'RACF',
            'messages': messages,
            'access_denied': denied,
            'suggestions': racf.suggest_racf_commands('')
        }

    elif jes.detect_jes_screen(screen_text):
        jobs = jes.parse_job_list(screen_text)
        return {
            'type': 'JES',
            'jobs': jobs
        }

    return {'type': 'UNKNOWN'}
```

## Module Contents

### cics_helper.py

| Class | Description |
|-------|-------------|
| `CICSHelper` | CICS transaction parsing |

### tso_helper.py

| Class | Description |
|-------|-------------|
| `TSOHelper` | TSO/ISPF parsing |

### racf_helper.py

| Class | Description |
|-------|-------------|
| `RACFHelper` | RACF security parsing |

### jes_parser.py

| Class | Description |
|-------|-------------|
| `JESParser` | JES job parsing |

## See Also

- [Core README](../core/README.md) - Screen class
- [Security README](../security/README.md) - Security scanning
- [Emulator README](../emulator/README.md) - TN3270 connection
