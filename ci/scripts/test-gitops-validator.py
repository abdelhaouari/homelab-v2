#!/usr/bin/env python3
"""Check that manifest validation rejects invalid and unknown resources."""

import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = os.environ.get("KUBECONFORM_BIN", "kubeconform")

BASE_COMMAND = [
    VALIDATOR,
    "-strict",
    "-summary",
    "-kubernetes-version", "1.36.0",
    "-schema-location",
    str(ROOT / "ci/schemas/custom")
    + "/{{.Group}}-{{.ResourceKind}}_{{.ResourceAPIVersion}}.json",
    "-schema-location",
    str(ROOT / "ci/schemas/native")
    + "/{{.ResourceKind}}{{.KindSuffix}}.json",
]

cases = [
    (
        "unknown-service-field",
        {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": "invalid-service"},
            "spec": {
                "ports": [{"port": 80}],
                "unexpectedField": True,
            },
        },
        "unexpectedField",
    ),
    (
        "invalid-gateway-type",
        {
            "apiVersion": "gateway.networking.k8s.io/v1",
            "kind": "Gateway",
            "metadata": {"name": "invalid-gateway"},
            "spec": {
                "gatewayClassName": 123,
                "listeners": [
                    {"name": "http", "protocol": "HTTP", "port": 80}
                ],
            },
        },
        "gatewayClassName",
    ),
    (
        "missing-schema",
        {
            "apiVersion": "validation.example.com/v1",
            "kind": "UnknownResource",
            "metadata": {"name": "missing-schema"},
        },
        "could not find schema",
    ),
]

with tempfile.TemporaryDirectory(prefix="homelab-validator-tests.") as directory:
    for name, resource, expected_message in cases:
        path = Path(directory) / f"{name}.json"
        path.write_text(json.dumps(resource), encoding="utf-8")

        result = subprocess.run(
            [*BASE_COMMAND, str(path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        output = result.stdout + result.stderr

        if result.returncode != 1 or expected_message not in output:
            print(output)
            raise SystemExit(
                f"FAIL: {name}: expected rejection with "
                f"{expected_message!r}, exit code={result.returncode}"
            )

        print(f"PASS: {name} rejected for the expected reason.")

print("All validator rejection checks passed.")
