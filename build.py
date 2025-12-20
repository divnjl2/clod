#!/usr/bin/env python3
"""
Cross-platform build script for Claude Agent Manager
Builds standalone executables using PyInstaller
"""

import subprocess
import sys
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"


def check_dependencies():
    """Check and install required build dependencies."""
    print("Checking dependencies...")

    # Check PyInstaller
    try:
        import PyInstaller
        print(f"  PyInstaller: {PyInstaller.__version__}")
    except ImportError:
        print("  Installing PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    # Check Pillow (for icon conversion)
    try:
        from PIL import Image
        print("  Pillow: OK")
    except ImportError:
        print("  Installing Pillow...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pillow"], check=True)


def create_ico():
    """Create .ico file from PNG for Windows."""
    from PIL import Image

    assets_dir = PROJECT_ROOT / "assets"
    icon_png = assets_dir / "icon.png"
    icon_ico = assets_dir / "icon.ico"

    if icon_ico.exists():
        print("  icon.ico already exists")
        return

    if not icon_png.exists():
        print("  ERROR: icon.png not found")
        return

    print("  Creating icon.ico...")
    img = Image.open(icon_png)
    if img.mode != 'RGBA':
        img = img.convert('RGBA')

    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    icons = [img.resize(size, Image.Resampling.LANCZOS) for size in sizes]

    icons[0].save(
        icon_ico,
        format='ICO',
        sizes=[(i.width, i.height) for i in icons],
        append_images=icons[1:]
    )
    print(f"  Created: {icon_ico}")


def clean():
    """Clean build artifacts."""
    print("Cleaning build artifacts...")

    for dir_path in [DIST_DIR, BUILD_DIR]:
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"  Removed: {dir_path}")


def build():
    """Build the application."""
    spec_file = PROJECT_ROOT / "cam-gui.spec"

    if not spec_file.exists():
        print(f"ERROR: {spec_file} not found")
        sys.exit(1)

    print(f"Building from {spec_file}...")

    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", str(spec_file), "--clean"],
        cwd=PROJECT_ROOT,
    )

    if result.returncode != 0:
        print("Build FAILED")
        sys.exit(1)

    print("\nBuild completed successfully!")

    # Show output
    if sys.platform == "win32":
        exe_path = DIST_DIR / "Claude Agent Manager.exe"
    elif sys.platform == "darwin":
        exe_path = DIST_DIR / "Claude Agent Manager.app"
    else:
        exe_path = DIST_DIR / "Claude Agent Manager"

    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024) if exe_path.is_file() else sum(
            f.stat().st_size for f in exe_path.rglob("*") if f.is_file()
        ) / (1024 * 1024)
        print(f"  Output: {exe_path}")
        print(f"  Size: {size_mb:.1f} MB")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Build Claude Agent Manager")
    parser.add_argument("--clean", action="store_true", help="Clean build artifacts only")
    parser.add_argument("--no-clean", action="store_true", help="Don't clean before building")
    args = parser.parse_args()

    if args.clean:
        clean()
        return

    check_dependencies()
    create_ico()

    if not args.no_clean:
        clean()

    build()


if __name__ == "__main__":
    main()
