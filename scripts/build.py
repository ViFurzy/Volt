import os
import subprocess
import sys
from pathlib import Path

def main():
    project_root = Path(__file__).parent.parent.absolute()
    
    print(f"Project root: {project_root}")
    print("Building executable with PyInstaller...")
    
    # We use PyInstaller module directly to build the app
    # Running python -m PyInstaller
    args = [
        sys.executable,
        "-m", "PyInstaller",
        "--name", "Volt",
        "--noconsole",
        "--windowed",
        "--onedir",
        "--icon", "src/assets/icon.ico" if (project_root / "src/assets/icon.ico").exists() else "NONE",
        "--add-data", f"{project_root}/src/assets;assets",
        "--paths", str(project_root / "src"),
        str(project_root / "src" / "__main__.py")
    ]
    
    try:
        subprocess.run(args, check=True, cwd=str(project_root))
        print("\nBuild successful! The output is in the 'dist/Volt' directory.")
        print("\nTo build the installer, you need Inno Setup.")
        print("1. Install Inno Setup (https://jrsoftware.org/isinfo.php)")
        print(f"2. Right-click on 'scripts/installer.iss' and select 'Compile', OR run:")
        print(f"   \"%LOCALAPPDATA%\\Programs\\Inno Setup 6\\ISCC.exe\" scripts\\installer.iss")
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed with error code {e.returncode}")
        sys.exit(e.returncode)
    except FileNotFoundError:
        print("\nPyInstaller is not installed. Please install it with 'pip install pyinstaller'")
        sys.exit(1)

if __name__ == "__main__":
    main()
