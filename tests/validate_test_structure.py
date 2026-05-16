import os
from pathlib import Path

ROOT = Path(r"C:\Shine_L\tests")

print("")
print("TEST STRUCTURE VALIDATION")
print("")

for folder in ROOT.iterdir():

    if folder.is_dir():

        py_tests = list(
            folder.glob("test_*.py")
        )

        print(
            f"{folder.name}: "
            f"{len(py_tests)} tests"
        )

print("")
print("TEST STRUCTURE ONLINE")
