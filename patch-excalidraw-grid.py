#!/usr/bin/env python3
"""
Excalidraw Grid Patch for Obsidian
Scales the grid cell size at 100% zoom to match what it was at 175% zoom (20px * 1.75 = 35px).
Also migrates existing drawings with default 20px grid to 35px.
"""

import sys
import os
import shutil
import argparse

REPLACEMENT_CHAIN = (
    '.replace(",ha=20,", ",ha=35,")'
    '.replace("gridSize:r3(ZA(t.gridSize)?t.gridSize:ha)", "gridSize:r3(ZA(t.gridSize)&&20!==t.gridSize?t.gridSize:ha)")'
)

DEFAULT_PATHS = [
    os.path.expanduser("~/Documents/1/home/.obsidian/plugins/obsidian-excalidraw-plugin/main.js"),
    os.path.expanduser("~/.config/obsidian/plugin-scripts/6e9c9b4f2fe9daf3/.obsidian/plugins/obsidian-excalidraw-plugin/main.js"),
]

def patch_file(filepath: str, revert: bool = False) -> bool:
    if not os.path.isfile(filepath):
        print(f"[-] File not found: {filepath}")
        return False

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Find line 19 with unpackExcalidraw
    line_idx = None
    for i, line in enumerate(lines):
        if "unpackExcalidraw" in line and "unpackBase64Deflate" in line:
            line_idx = i
            break

    if line_idx is None:
        print(f"[-] unpackExcalidraw definition not found in {filepath}")
        return False

    target_line = lines[line_idx]

    if revert:
        if REPLACEMENT_CHAIN not in target_line:
            print(f"[*] File is not patched: {filepath}")
            return True
        lines[line_idx] = target_line.replace(REPLACEMENT_CHAIN, "")
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print(f"[+] Successfully reverted patch in: {filepath}")
        return True

    if REPLACEMENT_CHAIN in target_line:
        print(f"[*] File is already patched: {filepath}")
        return True

    # Backup original before modifying if no backup exists
    backup_path = filepath + ".orig"
    if not os.path.exists(backup_path):
        shutil.copyfile(filepath, backup_path)
        print(f"[+] Backup created at {backup_path}")

    # Patch line 19
    # The line ends with: ...);\n or ...);
    stripped = target_line.rstrip("\r\n")
    ending = target_line[len(stripped):]

    if stripped.endswith(");"):
        new_line = stripped[:-2] + ")" + REPLACEMENT_CHAIN + ";" + ending
    elif stripped.endswith(")"):
        new_line = stripped + REPLACEMENT_CHAIN + ending
    else:
        print(f"[-] Unexpected line ending in line {line_idx + 1}")
        return False

    lines[line_idx] = new_line

    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print(f"[+] Successfully patched: {filepath}")
    return True

def main():
    parser = argparse.ArgumentParser(description="Patch Obsidian Excalidraw grid size (20px -> 35px)")
    parser.add_argument("file", nargs="?", help="Path to main.js (optional)")
    parser.add_argument("--revert", action="store_true", help="Revert the patch")
    args = parser.parse_args()

    targets = [args.file] if args.file else DEFAULT_PATHS
    success = True
    for path in targets:
        if os.path.exists(path):
            if not patch_file(path, revert=args.revert):
                success = False

    if success:
        print("\nAll target files processed successfully!")
        print("Note: In Obsidian, reload the app (Ctrl+R) or toggle Excalidraw plugin off and on to apply changes.")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
