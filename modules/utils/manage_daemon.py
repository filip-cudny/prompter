#!/usr/bin/env python3
"""
Daemon management script for notification daemon.

This script helps start, stop, and check the status of the notification daemon.
"""

import os
import sys
import time
import signal
import tempfile
import subprocess
from pathlib import Path


def get_daemon_info():
    """Get daemon script path and pipe path."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    daemon_script = os.path.join(current_dir, "notification_daemon.py")
    temp_dir = tempfile.gettempdir()
    pipe_path = os.path.join(temp_dir, "prompt_store_notifications")
    pid_file = os.path.join(temp_dir, "prompt_store_daemon.pid")
    
    return daemon_script, pipe_path, pid_file


def is_daemon_running():
    """Check if daemon is running."""
    daemon_script, pipe_path, pid_file = get_daemon_info()
    
    # Check if pipe exists
    if not os.path.exists(pipe_path):
        return False
    
    # Check if PID file exists and process is running
    if os.path.exists(pid_file):
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process is running
            try:
                os.kill(pid, 0)  # Signal 0 doesn't kill, just checks if process exists
                return True
            except OSError:
                # Process doesn't exist, clean up stale files
                os.unlink(pid_file)
                if os.path.exists(pipe_path):
                    os.unlink(pipe_path)
                return False
        except (ValueError, IOError):
            return False
    
    return False


def start_daemon():
    """Start the notification daemon."""
    if is_daemon_running():
        print("Daemon is already running")
        return True
    
    daemon_script, pipe_path, pid_file = get_daemon_info()
    
    if not os.path.exists(daemon_script):
        print(f"Daemon script not found: {daemon_script}")
        return False
    
    try:
        # Start daemon process
        process = subprocess.Popen(
            [sys.executable, daemon_script],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        
        # Save PID
        with open(pid_file, 'w') as f:
            f.write(str(process.pid))
        
        # Wait a moment for daemon to start
        time.sleep(0.5)
        
        # Check if it started successfully
        if is_daemon_running():
            print(f"Daemon started successfully (PID: {process.pid})")
            return True
        else:
            print("Daemon failed to start")
            return False
            
    except Exception as e:
        print(f"Failed to start daemon: {e}")
        return False


def stop_daemon():
    """Stop the notification daemon."""
    if not is_daemon_running():
        print("Daemon is not running")
        return True
    
    daemon_script, pipe_path, pid_file = get_daemon_info()
    
    if os.path.exists(pid_file):
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Send SIGTERM to daemon
            os.kill(pid, signal.SIGTERM)
            
            # Wait for daemon to shut down
            for _ in range(10):  # Wait up to 1 second
                try:
                    os.kill(pid, 0)
                    time.sleep(0.1)
                except OSError:
                    break
            
            # Clean up files
            if os.path.exists(pid_file):
                os.unlink(pid_file)
            if os.path.exists(pipe_path):
                os.unlink(pipe_path)
            
            print(f"Daemon stopped (PID: {pid})")
            return True
            
        except (ValueError, IOError, OSError) as e:
            print(f"Error stopping daemon: {e}")
            return False
    
    return False


def restart_daemon():
    """Restart the notification daemon."""
    print("Restarting daemon...")
    stop_daemon()
    time.sleep(0.5)
    return start_daemon()


def daemon_status():
    """Show daemon status."""
    daemon_script, pipe_path, pid_file = get_daemon_info()
    
    if is_daemon_running():
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            print(f"Daemon is running (PID: {pid})")
            print(f"Pipe: {pipe_path}")
        except (ValueError, IOError):
            print("Daemon is running (PID unknown)")
    else:
        print("Daemon is not running")
    
    print(f"Daemon script: {daemon_script}")


def test_notification():
    """Send a test notification."""
    if not is_daemon_running():
        print("Daemon is not running. Starting daemon...")
        if not start_daemon():
            return False
    
    daemon_script, pipe_path, pid_file = get_daemon_info()
    
    try:
        # Send test notification
        result = subprocess.run([
            sys.executable, daemon_script, "send",
            "Test Notification", "This is a test message", "🧪"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("Test notification sent successfully")
            return True
        else:
            print(f"Failed to send test notification: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"Error sending test notification: {e}")
        return False


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: manage_daemon.py <command>")
        print("Commands:")
        print("  start    - Start the daemon")
        print("  stop     - Stop the daemon")
        print("  restart  - Restart the daemon")
        print("  status   - Show daemon status")
        print("  test     - Send a test notification")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "start":
        success = start_daemon()
        sys.exit(0 if success else 1)
    elif command == "stop":
        success = stop_daemon()
        sys.exit(0 if success else 1)
    elif command == "restart":
        success = restart_daemon()
        sys.exit(0 if success else 1)
    elif command == "status":
        daemon_status()
        sys.exit(0)
    elif command == "test":
        success = test_notification()
        sys.exit(0 if success else 1)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()