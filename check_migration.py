#!/usr/bin/env python3
"""Migration verification script to check PyQt5 readiness."""

import sys
import os
import importlib
import platform
from typing import List, Tuple, Optional

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check_import(module_name: str, description: str) -> Tuple[bool, str]:
    """Check if a module can be imported."""
    try:
        importlib.import_module(module_name)
        return True, f"✓ {description}"
    except ImportError as e:
        return False, f"✗ {description}: {str(e)}"


def check_file_exists(file_path: str, description: str) -> Tuple[bool, str]:
    """Check if a file exists."""
    if os.path.exists(file_path):
        return True, f"✓ {description}"
    else:
        return False, f"✗ {description}: File not found"


def check_pyqt5_components() -> List[Tuple[bool, str]]:
    """Check PyQt5 component availability."""
    components = [
        ("PyQt5.QtWidgets", "PyQt5 Widgets"),
        ("PyQt5.QtCore", "PyQt5 Core"),
        ("PyQt5.QtGui", "PyQt5 GUI"),
    ]
    
    results = []
    for module, desc in components:
        results.append(check_import(module, desc))
    
    # Test specific classes
    try:
        from PyQt5.QtWidgets import QApplication, QMenu, QAction
        from PyQt5.QtCore import QTimer, pyqtSignal, QObject
        from PyQt5.QtGui import QCursor
        results.append((True, "✓ PyQt5 essential classes"))
    except ImportError as e:
        results.append((False, f"✗ PyQt5 essential classes: {str(e)}"))
    
    return results


def check_migration_files() -> List[Tuple[bool, str]]:
    """Check if PyQt5 migration files exist."""
    files = [
        ("gui/pyqt_hotkey_manager.py", "PyQt5 Hotkey Manager"),
        ("gui/pyqt_context_menu.py", "PyQt5 Context Menu"),
        ("gui/pyqt_menu_coordinator.py", "PyQt5 Menu Coordinator"),
        ("utils/pyqt_notifications.py", "PyQt5 Notifications"),
        ("app/pyqt_application.py", "PyQt5 Application"),
        ("test_pyqt.py", "PyQt5 Test Script"),
    ]
    
    results = []
    for file_path, desc in files:
        results.append(check_file_exists(file_path, desc))
    
    return results


def check_legacy_files() -> List[Tuple[bool, str]]:
    """Check legacy tkinter files (should exist but are deprecated)."""
    files = [
        ("gui/hotkey_manager.py", "Legacy Hotkey Manager (tkinter)"),
        ("gui/context_menu.py", "Legacy Context Menu (tkinter)"),
        ("utils/notifications.py", "Legacy Notifications (tkinter)"),
        ("app/application.py", "Legacy Application (tkinter)"),
    ]
    
    results = []
    for file_path, desc in files:
        exists = os.path.exists(file_path)
        if exists:
            results.append((True, f"⚠ {desc} - Deprecated"))
        else:
            results.append((False, f"? {desc} - Missing (OK if fully migrated)"))
    
    return results


def check_dependencies() -> List[Tuple[bool, str]]:
    """Check other required dependencies."""
    deps = [
        ("pynput", "Global hotkey support"),
        ("requests", "HTTP client"),
        ("dotenv", "Environment variables"),
    ]
    
    results = []
    for module, desc in deps:
        results.append(check_import(module, desc))
    
    return results


def check_platform_specific() -> List[Tuple[bool, str]]:
    """Check platform-specific requirements."""
    results = []
    system = platform.system().lower()
    
    if system == "darwin":  # macOS
        results.append(check_import("objc", "macOS Objective-C bridge (pyobjc)"))
        
        # Check accessibility permissions (can't be done programmatically)
        results.append((True, "⚠ macOS Accessibility permissions (check manually)"))
        
    elif system == "linux":
        results.append(check_import("Xlib", "Linux X11 support"))
        
    elif system == "windows":
        # Windows support is built-in with ctypes
        results.append((True, "✓ Windows support (built-in)"))
    
    return results


def run_quick_import_test() -> Tuple[bool, str]:
    """Try to import and instantiate key PyQt5 components."""
    try:
        from PyQt5.QtWidgets import QApplication
        from gui.pyqt_hotkey_manager import PyQtHotkeyManager
        from gui.pyqt_context_menu import PyQtContextMenu
        from utils.pyqt_notifications import PyQtNotificationManager
        
        # Try to create a QApplication (if one doesn't exist)
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        
        # Try to instantiate key components
        hotkey_manager = PyQtHotkeyManager()
        context_menu = PyQtContextMenu()
        notification_manager = PyQtNotificationManager(app)
        
        return True, "✓ PyQt5 components instantiate successfully"
        
    except Exception as e:
        return False, f"✗ PyQt5 component instantiation failed: {str(e)}"


def print_section(title: str, results: List[Tuple[bool, str]]) -> int:
    """Print a section of results and return failure count."""
    print(f"\n{title}")
    print("=" * len(title))
    
    failures = 0
    for success, message in results:
        print(f"  {message}")
        if not success:
            failures += 1
    
    return failures


def main():
    """Main verification function."""
    print("PyQt5 Migration Verification")
    print("=" * 30)
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version}")
    
    total_failures = 0
    
    # Check PyQt5 availability
    total_failures += print_section(
        "PyQt5 Framework", 
        check_pyqt5_components()
    )
    
    # Check migration files
    total_failures += print_section(
        "Migration Files",
        check_migration_files()
    )
    
    # Check dependencies
    total_failures += print_section(
        "Dependencies",
        check_dependencies()
    )
    
    # Check platform-specific
    total_failures += print_section(
        "Platform Support",
        check_platform_specific()
    )
    
    # Check legacy files
    print_section(
        "Legacy Files (Deprecated)",
        check_legacy_files()
    )
    
    # Run quick import test
    success, message = run_quick_import_test()
    if not success:
        total_failures += 1
    
    print_section(
        "Integration Test",
        [(success, message)]
    )
    
    # Summary
    print(f"\nSummary")
    print("=" * 7)
    
    if total_failures == 0:
        print("✅ Migration verification PASSED")
        print("   - All PyQt5 components are ready")
        print("   - You can safely use the new PyQt5 application")
        print("   - Run: python main.py")
        print("   - Test: python test_pyqt.py")
    else:
        print(f"❌ Migration verification FAILED ({total_failures} issues)")
        print("   - Fix the issues above before using PyQt5 application")
        print("   - Install missing dependencies: pip install -r requirements.txt")
        print("   - Fall back to legacy application if needed: python -m app.application")
    
    print(f"\nNext Steps:")
    print("  1. Install PyQt5: pip install PyQt5>=5.15.0")
    print("  2. Run test: python test_pyqt.py")
    print("  3. Start app: python main.py")
    print("  4. Check system permissions (macOS Accessibility)")
    
    return 0 if total_failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())