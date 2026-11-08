#!/usr/bin/env python3
"""
Excalidraw Comprehensive Performance & Grid Patch for Obsidian
1. Scales default grid cell to 35px (matching 175% zoom size at 100%).
2. Fast bounding-box hit testing for freedraw elements (eliminates cursor/hover CPU spikes).
3. Smooth zoom caching for freedraw strokes (eliminates multi-second freeze when zooming).
4. getSceneVersion memoization (eliminates massive GC and hashing lag during pan/zoom/draw).
5. onChange freedraw bypass during active stroke drawing (eliminates input lag & dropped strokes).
"""

import sys
import os
import shutil
import argparse

LINE19_REPLACEMENTS = [
    (
        ',ha=20,',
        ',ha=35,'
    ),
    (
        'gridSize:r3(ZA(t.gridSize)?t.gridSize:ha)',
        'gridSize:r3(ZA(t.gridSize)&&20!==t.gridSize?t.gridSize:ha)'
    ),
    (
        'hitElement(A,e,t,i=!0){return!!(',
        'hitElement(A,e,t,i=!0){if("freedraw"===t.type&&(A<t.x-10||A>t.x+t.width+10||e<t.y-10||e>t.y+t.height+10))return!1;return!!('
    ),
    (
        'g=A&&A.zoomValue!==o.value&&!a?.shouldCacheIgnoreZoom',
        'g=A&&A.zoomValue!==o.value&&!a?.shouldCacheIgnoreZoom&&("freedraw"!==e.type||Math.abs(A.zoomValue-o.value)/A.zoomValue>.4)'
    ),
]

# Build the replacement chain for line 19
CHAIN_PARTS = []
for old_s, new_s in LINE19_REPLACEMENTS:
    # Escape quotes for JS string literals
    esc_old = old_s.replace('\\', '\\\\').replace('"', '\\"')
    esc_new = new_s.replace('\\', '\\\\').replace('"', '\\"')
    CHAIN_PARTS.append(f'.replace("{esc_old}", "{esc_new}")')

REPLACEMENT_CHAIN = "".join(CHAIN_PARTS)

# Line 35 replacements
LINE35_REPLACEMENTS = [
    # 1. Memoize getSceneVersion in ExcalidrawView
    (
        "getSceneVersion(e){return this.excalidrawHashElementsVersion||(this.excalidrawHashElementsVersion=this.packages.excalidrawLib.hashElementsVersion),this.excalidrawHashElementsVersion(e.filter(e=>!e.isDeleted))}",
        "getSceneVersion(e){if(this._lastElementsRef===e&&void 0!==this._cachedSceneVersion)return this._cachedSceneVersion;this.excalidrawHashElementsVersion||(this.excalidrawHashElementsVersion=this.packages.excalidrawLib.hashElementsVersion);const t=this.excalidrawHashElementsVersion(e.filter(e=>!e.isDeleted));return this._lastElementsRef=e,this._cachedSceneVersion=t,t}"
    ),
    # 2. Bypass expensive scene change checks during active freedraw stroke
    (
        "this.isDirty()||null!==t.editingTextElement||null!==t.selectedLinearElement&&t.selectedLinearElement.isEditing||this.checkSceneVersion(e),handleMarkdownImageEditorSelection(this,e,t.selectedElementIds),this.triggerSceneChangeHooks(e,t,i)",
        '"freedraw"===t.newElement?.type?void 0:(this.isDirty()||null!==t.editingTextElement||null!==t.selectedLinearElement&&t.selectedLinearElement.isEditing||this.checkSceneVersion(e),handleMarkdownImageEditorSelection(this,e,t.selectedElementIds),this.triggerSceneChangeHooks(e,t,i))'
    )
]

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

    # Find line 19 (unpackExcalidraw) and line 35 (plugin code)
    idx19 = None
    idx35 = None
    for i, line in enumerate(lines):
        if idx19 is None and "const unpackExcalidraw" in line:
            idx19 = i
        if idx35 is None and "class ExcalidrawView" in line:
            idx35 = i

    if idx19 is None:
        print(f"[-] unpackExcalidraw not found in {filepath}")
        return False
    if idx35 is None:
        print(f"[-] ExcalidrawView not found in {filepath}")
        return False

    line19 = lines[idx19]
    line35 = lines[idx35]

    if revert:
        changed = False
        # Revert line 19: strip any appended replacement chains
        if REPLACEMENT_CHAIN in line19:
            lines[idx19] = line19.replace(REPLACEMENT_CHAIN, "")
            changed = True
        else:
            # Check for older grid-only replacement chain
            old_grid_chain = (
                '.replace(",ha=20,", ",ha=35,")'
                '.replace("gridSize:r3(ZA(t.gridSize)?t.gridSize:ha)", "gridSize:r3(ZA(t.gridSize)&&20!==t.gridSize?t.gridSize:ha)")'
            )
            if old_grid_chain in line19:
                lines[idx19] = line19.replace(old_grid_chain, "")
                changed = True

        # Revert line 35
        for orig_s, patched_s in LINE35_REPLACEMENTS:
            if patched_s in lines[idx35]:
                lines[idx35] = lines[idx35].replace(patched_s, orig_s)
                changed = True

        if changed:
            with open(filepath, "w", encoding="utf-8") as f:
                f.writelines(lines)
            print(f"[+] Successfully reverted patch in: {filepath}")
        else:
            print(f"[*] File is not patched or already original: {filepath}")
        return True

    # Check if already patched with full chain
    if REPLACEMENT_CHAIN in line19 and all(patched_s in line35 for _, patched_s in LINE35_REPLACEMENTS):
        print(f"[*] File is already fully patched: {filepath}")
        return True

    # If it was patched with older grid-only chain, clean it up first
    old_grid_chain = (
        '.replace(",ha=20,", ",ha=35,")'
        '.replace("gridSize:r3(ZA(t.gridSize)?t.gridSize:ha)", "gridSize:r3(ZA(t.gridSize)&&20!==t.gridSize?t.gridSize:ha)")'
    )
    if old_grid_chain in line19:
        line19 = line19.replace(old_grid_chain, "")

    # Backup original before modifying if no backup exists
    backup_path = filepath + ".orig"
    if not os.path.exists(backup_path):
        shutil.copyfile(filepath, backup_path)
        print(f"[+] Backup created at {backup_path}")

    # Patch line 19
    stripped = line19.rstrip("\r\n")
    ending = line19[len(stripped):]
    if stripped.endswith(");"):
        new_line19 = stripped[:-2] + ")" + REPLACEMENT_CHAIN + ";" + ending
    elif stripped.endswith(")"):
        new_line19 = stripped + REPLACEMENT_CHAIN + ending
    else:
        print(f"[-] Unexpected line ending in line {idx19 + 1}")
        return False
    lines[idx19] = new_line19

    # Patch line 35
    patched_line35 = lines[idx35]
    for orig_s, patched_s in LINE35_REPLACEMENTS:
        if orig_s in patched_line35:
            patched_line35 = patched_line35.replace(orig_s, patched_s, 1)
        elif patched_s in patched_line35:
            pass # already applied
        else:
            print(f"[-] Target pattern in line 35 not found: {orig_s[:40]}...")
            return False
    lines[idx35] = patched_line35

    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print(f"[+] Successfully patched: {filepath}")
    return True

def main():
    parser = argparse.ArgumentParser(description="Comprehensive Performance & Grid Patch for Obsidian Excalidraw")
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
        print("Note: In Obsidian, press Ctrl+R to reload the application and apply the optimizations.")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
