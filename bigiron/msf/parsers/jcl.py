"""Parser for JCL submission output."""
import re
from typing import Any

from .base import OutputParser
from .registry import parser_for


@parser_for("auxiliary/admin/mainframe/tk5_jcl_submit")
@parser_for("auxiliary/scanner/mainframe/ftp_jcl_creds")
@parser_for("*/*jcl*")
class JCLOutputParser(OutputParser):
    """Parses JCL job submission output."""

    JOB_ID_PATTERN = re.compile(r'JOB\s*ID[:\s]+([A-Z0-9]+)', re.IGNORECASE)
    RETURN_CODE_PATTERN = re.compile(r'(?:Return|RC|Condition)\s*code[:\s]*(\d+)', re.IGNORECASE)
    DATASET_PATTERN = re.compile(r'([A-Z][A-Z0-9]*(?:\.[A-Z][A-Z0-9]*)+)', re.IGNORECASE)

    def parse(self, output: str) -> list[dict[str, Any]]:
        """Extract job info and datasets from JCL output."""
        entities = []

        # Find job ID
        job_match = self.JOB_ID_PATTERN.search(output)
        if job_match:
            job_id = job_match.group(1).upper()

            # Find return code if present
            rc_match = self.RETURN_CODE_PATTERN.search(output)
            return_code = rc_match.group(1) if rc_match else None

            entities.append({
                "node_type": "job",
                "label": job_id,
                "properties": {
                    "job_id": job_id,
                    "return_code": return_code,
                    "source": "jcl_submit"
                }
            })

        # Find datasets mentioned
        seen_datasets = set()
        for match in self.DATASET_PATTERN.finditer(output):
            dsn = match.group(1).upper()
            # Filter out common false positives
            if dsn in seen_datasets or len(dsn) < 5:
                continue
            if any(x in dsn for x in ["HTTP", "HTTPS", "FTP"]):
                continue

            seen_datasets.add(dsn)
            entities.append({
                "node_type": "dataset",
                "label": dsn,
                "properties": {
                    "dsn": dsn,
                    "source": "jcl_output"
                }
            })

        return entities
