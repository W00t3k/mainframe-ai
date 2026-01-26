#!/usr/bin/env python3
"""
Enhanced Security Reporter for BIRP v2
Generate comprehensive security assessment reports
"""

import json
from datetime import datetime
from ..utils.logger import log_info


class SecurityReporter:
    """Generate detailed security reports"""
    
    def __init__(self, history, findings=None):
        self.history = history
        self.findings = findings or []
    
    def generate_html_report(self, filename='security_report.html'):
        """Generate HTML security report"""
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Big Iron Recon & Pwnage (BIRP) v2 - Security Assessment Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #d32f2f; border-bottom: 3px solid #d32f2f; padding-bottom: 10px; }}
        h2 {{ color: #1976d2; margin-top: 30px; }}
        .summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin: 20px 0; }}
        .summary-box {{ padding: 20px; border-radius: 5px; text-align: center; }}
        .critical {{ background: #ffebee; border-left: 4px solid #d32f2f; }}
        .high {{ background: #fff3e0; border-left: 4px solid #f57c00; }}
        .medium {{ background: #fff9c4; border-left: 4px solid #fbc02d; }}
        .low {{ background: #e8f5e9; border-left: 4px solid #388e3c; }}
        .finding {{ background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #666; }}
        .finding.critical {{ border-left-color: #d32f2f; }}
        .finding.high {{ border-left-color: #f57c00; }}
        .finding.medium {{ border-left-color: #fbc02d; }}
        .finding.low {{ border-left-color: #388e3c; }}
        .credential {{ background: #e3f2fd; padding: 10px; margin: 5px 0; border-radius: 3px; }}
        .hidden-field {{ background: #ffebee; padding: 10px; margin: 5px 0; border-radius: 3px; font-family: monospace; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #1976d2; color: white; }}
        .timestamp {{ color: #666; font-size: 0.9em; }}
        .code {{ background: #263238; color: #aed581; padding: 15px; border-radius: 5px; overflow-x: auto; font-family: monospace; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔒 Big Iron Recon & Pwnage (BIRP) v2 - Security Assessment Report</h1>
        <p class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <h2>Executive Summary</h2>
        <div class="summary">
            <div class="summary-box critical">
                <h3>{len([f for f in self.findings if f.get('severity') == 'critical'])}</h3>
                <p>Critical</p>
            </div>
            <div class="summary-box high">
                <h3>{len([f for f in self.findings if f.get('severity') == 'high'])}</h3>
                <p>High</p>
            </div>
            <div class="summary-box medium">
                <h3>{len([f for f in self.findings if f.get('severity') == 'medium'])}</h3>
                <p>Medium</p>
            </div>
            <div class="summary-box low">
                <h3>{len([f for f in self.findings if f.get('severity') == 'low'])}</h3>
                <p>Low</p>
            </div>
        </div>
        
        <h2>Assessment Details</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Transactions Analyzed</td>
                <td>{len(self.history)}</td>
            </tr>
            <tr>
                <td>Total Findings</td>
                <td>{len(self.findings)}</td>
            </tr>
            <tr>
                <td>Hidden Fields Found</td>
                <td>{len([f for f in self.findings if f.get('type') == 'hidden_field'])}</td>
            </tr>
            <tr>
                <td>Credentials Detected</td>
                <td>{len([f for f in self.findings if 'credential' in f.get('type', '')])}</td>
            </tr>
        </table>
"""
        
        # Add findings
        if self.findings:
            html += "<h2>Security Findings</h2>"
            for finding in self.findings:
                severity = finding.get('severity', 'low')
                html += f"""
        <div class="finding {severity}">
            <strong>{finding.get('type', 'Unknown').replace('_', ' ').title()}</strong> 
            <span style="float: right; color: #666;">Severity: {severity.upper()}</span>
            <p>{finding.get('message', 'No description')}</p>
            <p><small>Location: {finding.get('location', 'N/A')} | Transaction: {finding.get('transaction', 'N/A')}</small></p>
            {f'<div class="code">{finding.get("content", "")}</div>' if finding.get('content') else ''}
        </div>
"""
        
        # Add hidden fields section
        hidden_fields = []
        for trans in self.history:
            for field in trans.response.hidden_fields:
                if field.contents.strip():
                    hidden_fields.append({
                        'content': field.contents,
                        'location': f'[{field.row},{field.col}]',
                        'transaction': self.history.index(trans)
                    })
        
        if hidden_fields:
            html += "<h2>Hidden Fields Detected</h2>"
            html += f"<p>Found {len(hidden_fields)} hidden fields containing data:</p>"
            for hf in hidden_fields[:20]:  # Limit to first 20
                html += f"""
        <div class="hidden-field">
            <strong>Location:</strong> {hf['location']} | 
            <strong>Transaction:</strong> {hf['transaction']}<br>
            <strong>Content:</strong> {hf['content']}
        </div>
"""
        
        html += """
        <h2>Recommendations</h2>
        <ul>
            <li>Review all hidden fields for sensitive data exposure</li>
            <li>Ensure password fields are properly protected</li>
            <li>Implement proper input validation on all fields</li>
            <li>Review access control mechanisms</li>
            <li>Audit credential handling procedures</li>
        </ul>
        
        <hr style="margin: 40px 0;">
        <p style="text-align: center; color: #666;">
            Generated by Big Iron Recon & Pwnage (BIRP) v2<br>
            <a href="https://github.com/W00t3k/birpv2">github.com/W00t3k/birpv2</a>
        </p>
    </div>
</body>
</html>
"""
        
        with open(filename, 'w') as f:
            f.write(html)
        
        log_info(f'HTML report saved to {filename}')
        return filename
    
    def generate_json_report(self, filename='security_report.json'):
        """Generate JSON security report"""
        
        report = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'tool': 'BIRP v2',
                'version': '2.0'
            },
            'summary': {
                'transactions_analyzed': len(self.history),
                'total_findings': len(self.findings),
                'severity_breakdown': {
                    'critical': len([f for f in self.findings if f.get('severity') == 'critical']),
                    'high': len([f for f in self.findings if f.get('severity') == 'high']),
                    'medium': len([f for f in self.findings if f.get('severity') == 'medium']),
                    'low': len([f for f in self.findings if f.get('severity') == 'low']),
                }
            },
            'findings': self.findings,
            'hidden_fields': [],
            'transactions': []
        }
        
        # Add hidden fields
        for idx, trans in enumerate(self.history):
            for field in trans.response.hidden_fields:
                if field.contents.strip():
                    report['hidden_fields'].append({
                        'transaction': idx,
                        'location': f'[{field.row},{field.col}]',
                        'content': field.contents,
                        'length': len(field.contents)
                    })
        
        # Add transaction summary
        for idx, trans in enumerate(self.history):
            report['transactions'].append({
                'index': idx,
                'timestamp': trans.timestamp.isoformat(),
                'key': trans.key,
                'host': trans.host,
                'fields_modified': len(trans.data),
                'hidden_fields': len(trans.response.hidden_fields)
            })
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        log_info(f'JSON report saved to {filename}')
        return filename
    
    def generate_markdown_report(self, filename='security_report.md'):
        """Generate Markdown security report"""
        
        md = f"""# BIRP v2 Security Assessment Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Executive Summary

| Severity | Count |
|----------|-------|
| Critical | {len([f for f in self.findings if f.get('severity') == 'critical'])} |
| High     | {len([f for f in self.findings if f.get('severity') == 'high'])} |
| Medium   | {len([f for f in self.findings if f.get('severity') == 'medium'])} |
| Low      | {len([f for f in self.findings if f.get('severity') == 'low'])} |

## Assessment Details

- **Transactions Analyzed:** {len(self.history)}
- **Total Findings:** {len(self.findings)}
- **Hidden Fields Found:** {len([f for f in self.findings if f.get('type') == 'hidden_field'])}

## Security Findings

"""
        
        for finding in self.findings:
            severity = finding.get('severity', 'low').upper()
            md += f"""### [{severity}] {finding.get('type', 'Unknown').replace('_', ' ').title()}

**Message:** {finding.get('message', 'No description')}  
**Location:** {finding.get('location', 'N/A')}  
**Transaction:** {finding.get('transaction', 'N/A')}

"""
            if finding.get('content'):
                md += f"```\n{finding.get('content')}\n```\n\n"
        
        md += """## Recommendations

1. Review all hidden fields for sensitive data exposure
2. Ensure password fields are properly protected
3. Implement proper input validation on all fields
4. Review access control mechanisms
5. Audit credential handling procedures

---

*Generated by Big Iron Recon & Pwnage (BIRP) v2*  
*https://github.com/W00t3k/birpv2*
"""
        
        with open(filename, 'w') as f:
            f.write(md)
        
        log_info(f'Markdown report saved to {filename}')
        return filename
