#!/usr/bin/env python3
"""Script to start the FastAPI server and log output."""
import subprocess
import sys
import os

log_file = open("logs/server.log", "w")

process = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "api.main:app", "--reload", "--port", "8000"],
    stdout=log_file,
    stderr=subprocess.STDOUT,
    cwd=os.path.dirname(os.path.abspath(__file__))
)

print(f"Server started with PID: {process.pid}")
print(f"Logs written to: logs/server.log")
print(f"API available at: http://127.0.0.1:8000")
print(f"Press Ctrl+C to stop")

try:
    process.wait()
except KeyboardInterrupt:
    print("\nStopping server...")
    process.terminate()
    process.wait()
    log_file.close()
