import subprocess
import json

def parse_devices_output(output: str) -> list[dict]:
    devices = []
    lines = output.strip().splitlines()
    # Skip the "List of devices attached" header
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            device_id = parts[0]
            state = parts[1]
            model = ""
            for part in parts[2:]:
                if part.startswith("model:"):
                    model = part.split(":")[1]
            devices.append({"id": device_id, "state": state, "model": model})
    return devices

def check_devices():
    try:
        result = subprocess.run(["adb", "devices", "-l"], capture_output=True, text=True)
        devices = parse_devices_output(result.stdout)
        print("Connected Devices:")
        for dev in devices:
            print(f"- ID: {dev['id']}, State: {dev['state']}, Model: {dev['model']}")
            
        # WPD check (Windows Portable Devices)
        print("\nChecking WPD via PowerShell...")
        ps_result = subprocess.run(["powershell", "-Command", "Get-PnpDevice -Class WPD"], capture_output=True, text=True)
        print(ps_result.stdout.strip())
        
    except Exception as e:
        print(f"Error checking devices: {e}")

if __name__ == "__main__":
    check_devices()
