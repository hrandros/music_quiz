import os
import subprocess
import sys


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    launcher_path = os.path.join(base_dir, "local_launcher.py")

    if not os.path.exists(launcher_path):
        print("local_launcher.py not found")
        return 1

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        "RockQuizAdmin",
        "--add-data",
        "assets;assets",
        "--add-data",
        "musicquiz;musicquiz",
        "--add-data",
        "songs;songs",
        launcher_path,
    ]

    print("Running:", " ".join(cmd))
    return subprocess.call(cmd, cwd=base_dir)


if __name__ == "__main__":
    raise SystemExit(main())
