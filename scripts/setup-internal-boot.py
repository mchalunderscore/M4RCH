#!/usr/bin/env python3
"""Enroll the built internal-only NVMe bridge using the existing Recovery flow."""
import os
from pathlib import Path
import sys
PROJECT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(PROJECT/'sdboot'),str(PROJECT/'lib')]
import enrollment
if os.geteuid()!=0:raise SystemExit('Run sudo make boot-internal')
if not (PROJECT/'out/internal-layout-extension.json').exists():
    raise SystemExit('Stage and verify the internal ESP first: sudo make internal-esp')
enrollment.prepare(PROJECT,PROJECT/'out/sdboot',nvme='internal')
