import argparse
import base64
import copy
import json
import os
import re
import shutil
import struct
import tempfile
from pathlib import Path
from string import Template


TARGET_HTML = "webview/index.html"
TITLEBAR_SYMBOL_PATTERN = re.compile(
    rb"symbolColor:([A-Za-z_$][\w$]*)\.nativeTheme\.shouldUseDarkColors\?"
    rb"([A-Za-z_$][\w$]*):([A-Za-z_$][\w$]*)"
)
PORTABLE_CORE_GATE_PATTERN = re.compile(
    rb"function ([A-Za-z_$][\w$]*)\(\)\{return process\.platform===`win32`&&"
    rb".*?codexWindowsAppContainedCore.*?\}\)===`1`\}"
    rb"function ([A-Za-z_$][\w$]*)\(\)\{",
    re.DOTALL,
)
WINDOWS_UPDATER_PATTERN = re.compile(
    rb"enableUpdater:[A-Za-z_$][\w$]*\.shouldIncludeUpdater\([^)]*\)"
)


def read_asar(path):
    with open(path, "rb") as stream:
        prefix = stream.read(16)
        if len(prefix) != 16:
            raise RuntimeError("Invalid ASAR header")
        header_size = struct.unpack("<I", prefix[8:12])[0]
        json_size = struct.unpack("<I", prefix[12:16])[0]
        header = json.loads(stream.read(json_size).decode("utf-8"))
    return header, 12 + header_size


def node_for(header, path):
    node = header
    for part in path.split("/"):
        node = node["files"][part]
    return node


def packed_files(node, prefix=""):
    result = []
    for name, item in node.get("files", {}).items():
        path = f"{prefix}/{name}" if prefix else name
        if "files" in item:
            result.extend(packed_files(item, path))
        elif not item.get("unpacked"):
            result.append((path, item))
    return result


def encode_header(header):
    raw = json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    padded = (len(raw) + 3) & ~3
    return (
        struct.pack("<IIII", 4, padded + 8, padded + 4, len(raw))
        + raw
        + b"\0" * (padded - len(raw))
    )


def read_packed_file(source, header, data_start, path):
    node = node_for(header, path)
    with open(source, "rb") as stream:
        stream.seek(data_start + int(node["offset"]))
        return stream.read(int(node["size"]))


def discover_targets(source, header, data_start):
    html = read_packed_file(source, header, data_start, TARGET_HTML).decode(
        "utf-8", errors="replace"
    )
    runtime_match = re.search(r'src="\./assets/(index-[^"]+\.js)"', html)
    css_match = re.search(r'href="\./assets/(app-shared-[^"]+\.css)"', html)
    if not runtime_match or not css_match:
        raise RuntimeError("Could not discover the current webview entry assets")

    all_paths = [path for path, _ in packed_files(header)]
    main_candidates = [
        path
        for path in all_paths
        if path.startswith(".vite/build/main-") and path.endswith(".js")
    ]
    if len(main_candidates) != 1:
        raise RuntimeError(
            f"Expected one Electron main bundle, found {len(main_candidates)}"
        )

    bootstrap_candidates = [
        path
        for path in all_paths
        if path.startswith(".vite/build/bootstrap-") and path.endswith(".js")
    ]
    if len(bootstrap_candidates) != 1:
        raise RuntimeError(
            f"Expected one Electron bootstrap bundle, found {len(bootstrap_candidates)}"
        )

    return (
        f"webview/assets/{css_match.group(1)}",
        f"webview/assets/{runtime_match.group(1)}",
        main_candidates[0],
        bootstrap_candidates[0],
    )


def patch_portable_bootstrap(data):
    gate = PORTABLE_CORE_GATE_PATTERN.search(data)
    updater = WINDOWS_UPDATER_PATTERN.search(data)
    if not gate or not updater:
        raise RuntimeError("Could not locate the Windows packaged-runtime startup gates")

    gate_replacement = (
        b"function "
        + gate.group(1)
        + b"(){return!1}function "
        + gate.group(2)
        + b"(){"
    )
    gate_replacement += b" " * (len(gate.group(0)) - len(gate_replacement))
    data = data[: gate.start()] + gate_replacement + data[gate.end() :]

    updater = WINDOWS_UPDATER_PATTERN.search(data)
    updater_replacement = b"enableUpdater:!1"
    updater_replacement += b" " * (len(updater.group(0)) - len(updater_replacement))
    return data[: updater.start()] + updater_replacement + data[updater.end() :]


def file_data_uri(path, mime):
    with open(path, "rb") as stream:
        return f"data:{mime};base64," + base64.b64encode(stream.read()).decode("ascii")


def theme_css(background, city_background):
    template = Path(__file__).with_name("theme.css").read_text(encoding="utf-8")
    return Template(template).substitute(
        background=background, city_background=city_background
    ).encode("utf-8")


def discover_background_videos(video_path):
    video_path = os.path.abspath(video_path)
    directory = os.path.dirname(video_path)
    candidates = [
        os.path.join(directory, name)
        for name in sorted(os.listdir(directory))
        if name.startswith("UI_BackgroundMain.BGPlanet") and name.lower().endswith(".webm")
    ]
    if video_path not in candidates and os.path.isfile(video_path):
        candidates.append(video_path)
    if not candidates:
        raise RuntimeError(f"No rotating background videos found beside {video_path}")
    return candidates


def theme_html():
    return (
        '<video id="cyberpunk-dynamic-background" autoplay muted loop playsinline aria-hidden="true"></video>'
        '<video id="cyberpunk-dynamic-background-next" autoplay muted loop playsinline aria-hidden="true"></video>'
    ).encode("utf-8")


def theme_runtime(video_paths):
    sources = [file_data_uri(path, "video/webm") for path in video_paths]
    template = Path(__file__).with_name("theme-runtime.js").read_text(encoding="utf-8")
    return Template(template).substitute(
        sources=json.dumps(sources, separators=(",", ":"))
    ).encode("utf-8")


def patch_asar(
    asar_path, background_path, icon_path, city_background_path, video_path, cursor_path
):
    # Keep the original icon/cursor argument positions; the current theme ignores them.
    backup = asar_path + ".official"
    if not os.path.exists(backup):
        shutil.copy2(asar_path, backup)
    source = backup
    original_header, data_start = read_asar(source)
    header = copy.deepcopy(original_header)
    files = packed_files(header)
    target_css, target_runtime_js, main_js, bootstrap_js = discover_targets(
        source, header, data_start
    )
    additions = {
        target_css: theme_css(
            file_data_uri(background_path, "image/jpeg"),
            file_data_uri(city_background_path, "image/jpeg"),
        ),
        TARGET_HTML: theme_html(),
        target_runtime_js: theme_runtime(discover_background_videos(video_path)),
    }
    for path, data in additions.items():
        node = node_for(header, path)
        node["size"] = int(node["size"]) + len(data)
    offset = 0
    for _, node in files:
        node["offset"] = str(offset)
        offset += int(node["size"])
    encoded = encode_header(header)
    temp_fd, temp_path = tempfile.mkstemp(
        prefix="app-themed-", suffix=".asar", dir=os.path.dirname(asar_path)
    )
    os.close(temp_fd)
    try:
        with open(source, "rb") as inp, open(temp_path, "wb") as out:
            out.write(encoded)
            for path, original_node in packed_files(original_header):
                size = int(original_node["size"])
                inp.seek(data_start + int(original_node["offset"]))
                if path == main_js:
                    data = inp.read(size)
                    match = TITLEBAR_SYMBOL_PATTERN.search(data)
                    if not match:
                        raise RuntimeError("Could not locate Windows titlebar symbol-color logic")
                    replacement = b"symbolColor:" + match.group(2)
                    replacement += b" " * (len(match.group(0)) - len(replacement))
                    out.write(data[: match.start()] + replacement + data[match.end() :])
                    continue
                if path == bootstrap_js:
                    data = inp.read(size)
                    out.write(patch_portable_bootstrap(data))
                    continue
                remaining = size
                while remaining:
                    chunk = inp.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise RuntimeError(f"Unexpected EOF while reading {path}")
                    out.write(chunk)
                    remaining -= len(chunk)
                out.write(additions.get(path, b""))
        os.replace(temp_path, asar_path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("asar")
    parser.add_argument("background")
    parser.add_argument("icon", help="Legacy position; use - for the current theme")
    parser.add_argument("city_background")
    parser.add_argument("video")
    parser.add_argument("cursor", help="Legacy position; use - for the current theme")
    args = parser.parse_args()
    patch_asar(
        args.asar, args.background, args.icon, args.city_background, args.video, args.cursor
    )
    print("Cyberpunk theme injected successfully")
