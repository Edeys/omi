import argparse
import re
import subprocess
import sys
from pathlib import Path

ADB = Path(r"C:\Omi\toolchain\android-sdk\platform-tools\adb.exe")

def fetch_logcat(package: str | None = None, filters: list[str] | None = None, since_seconds: int = 60) -> str:
    cmd = [str(ADB) if ADB.exists() else "adb", "logcat", "-d", "-v", "time"]
    result = subprocess.run(cmd, capture_output=True, timeout=30)
    text = result.stdout.decode(errors="replace")
    lines = text.splitlines()
    if package:
        lines = [line for line in lines if package in line or "flutter" in line.lower()]
    if filters:
        pat = re.compile("|".join(re.escape(f) for f in filters), re.I)
        lines = [line for line in lines if pat.search(line)]
    return "\n".join(lines[-500:])

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Fetch and filter ADB logcat from device.")
    p.add_argument("--package", default="com.friend.ios.dev")
    p.add_argument("--filter", nargs="*", default=["Auth", "flutter", "ApiException"])
    p.add_argument("--since", type=int, default=60)
    args = p.parse_args()
    print(fetch_logcat(package=args.package, filters=args.filter, since_seconds=args.since))
