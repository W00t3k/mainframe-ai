#!/usr/bin/env python3
"""
Generate a professionally formatted PDF whitepaper from markdown.
Uses pandoc with custom styling and adds visualizations.
"""

import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DOCS_DIR = PROJECT_DIR / "docs"
ASSETS_DIR = DOCS_DIR / "assets"
OUTPUT_DIR = DOCS_DIR / "output"

def create_cover_page():
    """Create HTML cover page."""
    return '''
<div class="cover-page">
    <div class="logo">🖥️</div>
    <h1>BigIron-AI</h1>
    <div class="subtitle">Fine-Tuning Large Language Models for<br>Mainframe Domain Expertise on Apple Silicon</div>
    <div class="tagline"><em>"Think of me as that senior mainframer down the hall<br>who actually enjoys helping people learn."</em></div>
    <div class="version">Technical White Paper • Version 2.0</div>
    <div class="authors">BigIron-AI Project Contributors</div>
    <div class="date">July 2026</div>
</div>

<div class="metrics-section">
    <h2 style="text-align: center; color: #1a365d; margin-bottom: 0.5em; margin-top: 0;">At a Glance</h2>
    <div class="metrics">
        <div class="metric">
            <div class="metric-value">7.2B</div>
            <div class="metric-label">Parameters</div>
        </div>
        <div class="metric">
            <div class="metric-value">9,042</div>
            <div class="metric-label">Examples</div>
        </div>
        <div class="metric">
            <div class="metric-value">$0</div>
            <div class="metric-label">Cloud Cost</div>
        </div>
    </div>
    <div class="metrics">
        <div class="metric">
            <div class="metric-value">~2h</div>
            <div class="metric-label">Training</div>
        </div>
        <div class="metric">
            <div class="metric-value">14GB</div>
            <div class="metric-label">Model Size</div>
        </div>
        <div class="metric">
            <div class="metric-value">+32%</div>
            <div class="metric-label">Accuracy</div>
        </div>
    </div>
</div>
'''

def create_architecture_diagram():
    """Create ASCII architecture diagram as HTML."""
    return '''
<div class="diagram">
<h4 style="margin-top: 0; color: #1a365d;">Software Architecture</h4>
<pre style="background: transparent; color: #2d3748; margin: 0;">
┌─────────────────────────────────────────────────────────────┐
│                    BigIron-AI Stack                         │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Ollama    │  │  FastAPI    │  │   Web Interface     │  │
│  │  (Serving)  │  │  (Backend)  │  │   (Chat + Terminal) │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                     │             │
│  ┌──────┴────────────────┴─────────────────────┴──────────┐  │
│  │               GGUF Model (14GB, F16)                   │  │
│  │            bigiron-ai.gguf (Mistral-7B Fine-tuned)     │  │
│  └──────────────────────────┬────────────────────────────┘  │
│                             │                                │
│  ┌──────────────────────────┴────────────────────────────┐  │
│  │                   MLX Framework                        │  │
│  │              (Full Fine-tuning Engine)                 │  │
│  └──────────────────────────┬────────────────────────────┘  │
│                             │                                │
│  ┌──────────────────────────┴────────────────────────────┐  │
│  │              Metal GPU Backend (Apple)                 │  │
│  └──────────────────────────┬────────────────────────────┘  │
│                             │                                │
│  ┌──────────────────────────┴────────────────────────────┐  │
│  │       Apple Silicon (M2/M3/M4/M5, 64GB Unified)        │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
</pre>
</div>
'''

def create_training_pipeline_diagram():
    """Create training pipeline diagram."""
    return '''
<div class="diagram">
<h4 style="margin-top: 0; color: #1a365d;">Training Pipeline</h4>
<pre style="background: transparent; color: #2d3748; margin: 0;">
┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐
│   JSONL    │───▶│   MLX-LM   │───▶│   Fuse     │───▶│   GGUF     │
│  Training  │    │  Full FT   │    │  Weights   │    │  Convert   │
│   Data     │    │ (15 epochs)│    │            │    │            │
└────────────┘    └────────────┘    └────────────┘    └────────────┘
     │                  │                 │                 │
     ▼                  ▼                 ▼                 ▼
  9,042 ex         11,643 iter       HF Format         14GB F16

  ┌─────────────────────────────────────────────────────────────┐
  │                    One Command: ./build_bigiron_ai.sh       │
  └─────────────────────────────────────────────────────────────┘
</pre>
</div>
'''

def create_comparison_chart():
    """Create before/after comparison."""
    return '''
<div class="diagram">
<h4 style="margin-top: 0; color: #1a365d;">Evaluation Results: Before vs After Fine-Tuning</h4>
<pre style="background: transparent; color: #2d3748; margin: 0;">
Category           Base Mistral    BigIron-AI    Improvement
─────────────────────────────────────────────────────────────
JCL Utilities      ████░░░░░░ 40%  ███████░░░ 75%    +35%
RACF Commands      ███░░░░░░░ 30%  ███████░░░ 70%    +40%
REXX Patterns      ███░░░░░░░ 35%  ██████░░░░ 65%    +30%
Mainframe Concepts █████░░░░░ 50%  ████████░░ 85%    +35%
COBOL Code         ██████░░░░ 60%  ████████░░ 80%    +20%
─────────────────────────────────────────────────────────────
Overall            ████░░░░░░ 43%  ███████░░░ 75%    +32%
</pre>
</div>
'''

def generate_html(markdown_path: Path, output_path: Path):
    """Generate styled HTML from markdown."""

    # Read markdown
    with open(markdown_path) as f:
        content = f.read()

    # Read CSS
    css_path = ASSETS_DIR / "whitepaper-style.css"
    with open(css_path) as f:
        css = f.read()

    # Build HTML
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BigIron-AI Technical White Paper</title>
    <style>
{css}
    </style>
</head>
<body>
{create_cover_page()}

'''

    # Convert markdown to HTML using pandoc
    result = subprocess.run(
        ['pandoc', '-f', 'markdown', '-t', 'html', '--toc', '--toc-depth=3'],
        input=content,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"Pandoc error: {result.stderr}")
        sys.exit(1)

    body_html = result.stdout

    # Insert visualizations after specific sections
    # After "Software Stack" section
    body_html = body_html.replace(
        '<h3 id="software-stack">Software Stack</h3>',
        f'<h3 id="software-stack">Software Stack</h3>\n{create_architecture_diagram()}'
    )

    # After "Training Pipeline" header
    body_html = body_html.replace(
        '<h3 id="training-pipeline">Training Pipeline</h3>',
        f'<h3 id="training-pipeline">Training Pipeline</h3>\n{create_training_pipeline_diagram()}'
    )

    # After "Evaluation and Results" section
    body_html = body_html.replace(
        '<h2 id="evaluation-and-results">7. Evaluation and Results</h2>',
        f'<h2 id="evaluation-and-results">7. Evaluation and Results</h2>\n{create_comparison_chart()}'
    )

    html += body_html
    html += '''
<div class="footer">
    BigIron-AI Project • https://github.com/W00t3k/mainframe-ai • Apache 2.0 License
</div>
</body>
</html>'''

    with open(output_path, 'w') as f:
        f.write(html)

    return output_path

def generate_pdf(html_path: Path, pdf_path: Path):
    """Convert HTML to PDF using wkhtmltopdf or weasyprint."""

    # Try weasyprint first (better CSS support)
    try:
        from weasyprint import HTML
        HTML(filename=str(html_path)).write_pdf(str(pdf_path))
        return True
    except ImportError:
        pass

    # Try wkhtmltopdf
    try:
        subprocess.run(
            ['wkhtmltopdf', '--enable-local-file-access',
             '--margin-top', '20mm', '--margin-bottom', '20mm',
             '--margin-left', '15mm', '--margin-right', '15mm',
             str(html_path), str(pdf_path)],
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Try pandoc with wkhtmltopdf
    try:
        subprocess.run(
            ['pandoc', str(html_path), '-o', str(pdf_path),
             '--pdf-engine=wkhtmltopdf'],
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return False

def main():
    print("🖥️  BigIron-AI Whitepaper Generator")
    print("=" * 50)

    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)

    markdown_path = DOCS_DIR / "WHITEPAPER.md"
    html_path = OUTPUT_DIR / "WHITEPAPER.html"
    pdf_path = OUTPUT_DIR / "BigIron-AI-Whitepaper-v2.0.pdf"

    if not markdown_path.exists():
        print(f"❌ Markdown file not found: {markdown_path}")
        sys.exit(1)

    print(f"📄 Source: {markdown_path}")

    # Generate HTML
    print("📝 Generating styled HTML...")
    generate_html(markdown_path, html_path)
    print(f"✅ HTML created: {html_path}")

    # Generate PDF
    print("📑 Generating PDF...")
    if generate_pdf(html_path, pdf_path):
        print(f"✅ PDF created: {pdf_path}")
    else:
        print("⚠️  PDF generation requires weasyprint or wkhtmltopdf")
        print("   Install with: pip install weasyprint")
        print("   Or: brew install wkhtmltopdf")
        print(f"   HTML file available at: {html_path}")

    print()
    print("Done! Open the HTML file in a browser to print as PDF.")

if __name__ == "__main__":
    main()
