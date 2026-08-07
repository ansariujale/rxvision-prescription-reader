"""Check that Tesseract and AWS are reachable before running a real evaluation.

    python -m eval.check_setup

Reports each dependency separately so a failure points at one thing rather
than leaving you guessing which of them is wrong.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

OK, BAD, WARN = "  [ok]  ", "  [--]  ", "  [??]  "


def check_tesseract() -> bool:
    print("Tesseract")

    env_cmd = os.environ.get("TESSERACT_CMD")
    if env_cmd:
        print(f"{OK}TESSERACT_CMD is set: {env_cmd}")
        p = Path(env_cmd)
        if not p.exists():
            print(f"{BAD}...but nothing exists at that path")
            return False
        if p.is_dir():
            print(f"{BAD}...but that's a directory. It must be the .exe itself:")
            guess = p / "tesseract.exe"
            print(f"        try: {guess}")
            return False
        print(f"{OK}the path exists and is a file")
    else:
        print(f"{WARN}TESSERACT_CMD is not set in this process")
        if os.name == "nt":
            print("        PowerShell:  $env:TESSERACT_CMD = \"C:\\Program Files\\Tesseract-OCR\\tesseract.exe\"")
            print("        cmd.exe:     set TESSERACT_CMD=C:\\Program Files\\Tesseract-OCR\\tesseract.exe")
            print("        ('set' in PowerShell does not work - that's cmd syntax)")

    on_path = shutil.which("tesseract")
    if on_path:
        print(f"{OK}tesseract is on PATH: {on_path}")
    elif not env_cmd:
        print(f"{BAD}tesseract is not on PATH and TESSERACT_CMD is not set")
        return False

    try:
        import pytesseract

        if env_cmd:
            pytesseract.pytesseract.tesseract_cmd = env_cmd
        version = pytesseract.get_tesseract_version()
        print(f"{OK}pytesseract can run it - version {version}")
        return True
    except Exception as e:
        print(f"{BAD}pytesseract could not run it: {type(e).__name__}: {e}")
        return False


def check_aws() -> bool:
    print("\nAWS")
    try:
        import boto3
    except ImportError:
        print(f"{BAD}boto3 is not installed  (pip install -r requirements.txt)")
        return False

    creds = boto3.Session().get_credentials()
    if creds is None:
        print(f"{BAD}no credentials found")
        print("        configure with:  aws configure")
        print("        or set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY")
        return False
    print(f"{OK}credentials resolved (source: {creds.method})")

    try:
        ident = boto3.client("sts", region_name="ap-south-1").get_caller_identity()
        print(f"{OK}authenticated as {ident['Arn'].split('/')[-1]}")
    except Exception as e:
        print(f"{BAD}credentials exist but were rejected: {type(e).__name__}")
        return False

    # Not calling Textract here - that would cost money. This only confirms the
    # client can be constructed and the region is valid.
    try:
        boto3.client("textract", region_name="ap-south-1")
        print(f"{OK}textract client builds for ap-south-1")
        print("        (no Textract call made - the first real call is billed)")
        return True
    except Exception as e:
        print(f"{BAD}could not build a textract client: {type(e).__name__}: {e}")
        return False


def check_dataset() -> bool:
    print("\nMedicine dataset")
    path = Path("resource/medicine_names.csv")
    if not path.exists():
        print(f"{BAD}missing: {path}")
        print("        the matcher needs this; see the README")
        return False
    size_mb = path.stat().st_size / 1_048_576
    print(f"{OK}{path} present ({size_mb:.0f} MB)")
    return True


def main() -> int:
    print()
    results = [check_tesseract(), check_aws(), check_dataset()]
    print()
    if all(results):
        print("All good - ready to run: python -m eval.ocr_runner --images eval/images")
        return 0
    print("Not ready. Fix the [--] items above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
