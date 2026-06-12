#!/usr/bin/env python3
# (c) Copyright IBM Corp. 2026

"""
Downgrades any installed packages that were released within the 5-day grace
period to their latest safe version. Run after pip install so that CI tests
only exercise versions that have cleared the supply-chain safety window.

Usage:
    python scripts/pin_safe_versions.py [requirements_file]

If a requirements file is given, only the packages listed there are checked.
Otherwise every installed package is checked (slow).
"""
from typing import Any, Union


import re
import subprocess
import sys
from datetime import datetime, timedelta

import requests
from packaging.specifiers import SpecifierSet
from packaging.version import Version

GRACE_PERIOD_DAYS = 5


def _get_pypi_releases(package_name: str) -> list[Any]:
    try:
        r = requests.get(f"https://pypi.org/pypi/{package_name}/json", timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []

    current_python = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    result = []
    for ver, files in data["releases"].items():
        if not files or re.search(r"(a|b|rc|dev)\d*$", ver, re.I):
            continue
        try:
            Version(ver)
        except Exception:
            continue
        requires_python = next(
            (f["requires_python"] for f in files if f.get("requires_python")), None
        )
        if requires_python:
            try:
                if not SpecifierSet(requires_python).contains(current_python):
                    continue
            except Exception:
                pass
        upload_time = files[-1].get("upload_time_iso_8601", "")
        match = re.search(r"([\d-]+)T", upload_time)
        if not match:
            continue
        date = datetime.strptime(match[1], "%Y-%m-%d").date()
        result.append((ver, date))
    result.sort(key=lambda x: (x[1], Version(x[0])), reverse=True)
    return result


def _get_safe_version(releases: list[Any]) -> Union[tuple[Any, Any], tuple[None, None]]:
    today = datetime.today().date()
    grace_cutoff = today - timedelta(days=GRACE_PERIOD_DAYS)
    for i, (ver, date) in enumerate(releases):
        grace_end = date + timedelta(days=GRACE_PERIOD_DAYS)
        superseded = any(nd < grace_end for _, nd in releases[:i])
        if not superseded and date <= grace_cutoff:
            return ver, date
    return None, None


def _installed_packages() -> dict[Any, Any]:
    result = subprocess.run(["pip", "freeze"], capture_output=True, text=True, check=True)
    packages = {}
    for line in result.stdout.strip().splitlines():
        if "==" in line:
            pkg, ver = line.split("==", 1)
            packages[pkg.lower()] = ver.strip()
    return packages


def _parse_req_file(path: str) -> set[str]:
    names = set()
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("-r "):
                    # Recurse into included requirement files (same directory)
                    import os
                    included = os.path.join(os.path.dirname(path), line[3:].strip())
                    names |= _parse_req_file(included)
                    continue
                if line.startswith("-"):
                    continue
                name = re.split(r"[><=!;[\s]", line)[0].strip().lower()
                if name:
                    names.add(name)
    except FileNotFoundError:
        print(f"Warning: requirements file '{path}' not found.")
    return names


def main() -> None:
    packages_to_check = None
    if len(sys.argv) > 1:
        packages_to_check = _parse_req_file(sys.argv[1])
        print(f"Checking {len(packages_to_check)} packages from {sys.argv[1]}")

    installed = _installed_packages()
    today = datetime.today().date()
    grace_cutoff = today - timedelta(days=GRACE_PERIOD_DAYS)

    to_pin = []
    for pkg, installed_ver in installed.items():
        if packages_to_check is not None and pkg not in packages_to_check:
            continue

        releases = _get_pypi_releases(pkg)
        if not releases:
            continue

        installed_date = next((d for v, d in releases if v == installed_ver), None)
        if installed_date is None or installed_date <= grace_cutoff:
            continue

        safe_ver, safe_date = _get_safe_version(releases)
        if safe_ver is None:
            print(
                f"[grace-period] {pkg}=={installed_ver} (released {installed_date}) "
                f"is within grace period but no safe version exists — skipping"
            )
            continue

        print(
            f"[grace-period] {pkg}: {installed_ver} (released {installed_date}) "
            f"→ pinning to {safe_ver} (released {safe_date})"
        )
        to_pin.append(f"{pkg}=={safe_ver}")

    if to_pin:
        print(f"\nPinning {len(to_pin)} package(s) to grace-period-safe versions...")
        subprocess.run(["pip", "install"] + to_pin, check=True)
        print("Grace period enforcement complete.")
    else:
        print("All checked packages comply with the grace period.")


if __name__ == "__main__":
    main()
