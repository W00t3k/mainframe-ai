#!/bin/bash
# Download IBM Redbooks for z/OS security training
# These are freely available from IBM

DIR="$(cd "$(dirname "$0")/../.." && pwd)"
OUTDIR="$DIR/data/redbooks/security"
mkdir -p "$OUTDIR"

echo "Downloading z/OS Security Redbooks..."

# Key z/OS Security Redbooks (code|title format)
BOOKS="
sg246249|z/OS Security Server RACF Security Administrator's Guide
sg247850|Security on z/OS
sg248022|IBM RACF Implementation
redp4803|RACF for z/OS Security Administrators
sg248850|ABCs of z/OS System Programming Volume 8 Security
sg247983|Secure Configuration Guide for z/OS
sg248346|z/OS Security Hardening
sg246700|CICS TS Security
sg247258|Securing CICS Web Services
sg248125|DB2 for z/OS Security
sg247810|z/OS Communications Server Security
sg248021|z/OS Cryptographic Services
sg248001|z/OS Audit and Compliance
redp4805|SMF and Compliance
sg247441|Understanding LDAP Design and Implementation
sg248455|z/OS Identity Propagation
"

echo "$BOOKS" | while IFS='|' read -r code title; do
    [ -z "$code" ] && continue

    outfile="$OUTDIR/${code}.pdf"

    if [ -f "$outfile" ]; then
        echo "  [skip] $code - already exists"
        continue
    fi

    echo "  [download] $code - $title"

    # Try IBM's direct download URLs
    for url in \
        "https://www.redbooks.ibm.com/redbooks/pdfs/${code}.pdf" \
        "https://www.redbooks.ibm.com/redpapers/pdfs/${code}.pdf" \
        "https://www.redbooks.ibm.com/abstracts/${code}.pdf"
    do
        if curl -sfL --max-time 30 -o "$outfile" "$url" 2>/dev/null; then
            # Verify it's a PDF (not an error page)
            if file "$outfile" | grep -q PDF; then
                size=$(ls -lh "$outfile" | awk '{print $5}')
                echo "    ✓ Downloaded ($size)"
                break
            else
                rm -f "$outfile"
            fi
        fi
    done

    if [ ! -f "$outfile" ]; then
        echo "    ✗ Not found - try manual download from redbooks.ibm.com"
    fi

    sleep 1
done

echo ""
echo "Downloaded to: $OUTDIR"
ls -la "$OUTDIR"/*.pdf 2>/dev/null | wc -l | xargs echo "Total PDFs:"
