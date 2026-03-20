#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from tkinter import BOTH, RIGHT, X, StringVar, Tk, ttk

from PIL import Image


MAX_SIZE = 1024
SUPPORTED_EXTENSIONS = {".bmp", ".jpg", ".jpeg", ".png", ".tga"}
OUTPUT_DIR_NAME = "output_dtx"
LOG_NAME = "convert_to_dtx.log"
EXCLUDED_DIRS = {OUTPUT_DIR_NAME, "dist", "build", "__pycache__"}
DTX_HEADER_SIZE = 164
DTX_COMMAND_OFFSET = 36
DTX_COMMAND_LENGTH = 128
DTX_RESTYPE = 0
DTX_VERSION = -5
DTX_BPP_32 = 3
ALPHA_REF_COMMAND = "alpharef 128"


@dataclass
class ProgressInfo:
    current: int = 0
    total: int = 0
    success_count: int = 0
    failure_count: int = 0
    adjusted_count: int = 0
    alpha_ref_count: int = 0
    current_file: str = ""
    stage: str = ""


class ProgressWindow:
    def __init__(self, base_dir: Path) -> None:
        self.root = Tk()
        self.root.title("DTX Conversion Progress")
        self.root.geometry("720x240")
        self.root.resizable(False, False)

        container = ttk.Frame(self.root, padding=16)
        container.pack(fill=BOTH, expand=True)

        self.status_var = StringVar(value="Preparing...")
        self.file_var = StringVar(value="Current file: -")
        self.count_var = StringVar(value="Progress: 0 / 0")
        self.result_var = StringVar(value="Succeeded: 0    Failed: 0    Resized/Padded: 0    AlphaRef: 0")
        self.path_var = StringVar(value=f"Source folder: {base_dir}")

        ttk.Label(container, textvariable=self.status_var).pack(anchor="w")
        ttk.Label(container, textvariable=self.file_var, wraplength=680).pack(anchor="w", pady=(8, 0))
        ttk.Label(container, textvariable=self.count_var).pack(anchor="w", pady=(8, 0))
        self.progressbar = ttk.Progressbar(container, orient="horizontal", length=680, mode="determinate")
        self.progressbar.pack(fill=X, pady=(8, 0))
        ttk.Label(container, textvariable=self.result_var).pack(anchor="w", pady=(8, 0))
        ttk.Label(container, textvariable=self.path_var, wraplength=680).pack(anchor="w", pady=(8, 0))

        button_row = ttk.Frame(container)
        button_row.pack(fill=X, pady=(16, 0))
        self.close_button = ttk.Button(button_row, text="Close", command=self.root.destroy, state="disabled")
        self.close_button.pack(side=RIGHT)

        self.root.update_idletasks()

    def update(self, info: ProgressInfo) -> None:
        self.status_var.set(info.stage or "Processing...")
        self.file_var.set(f"Current file: {info.current_file or '-'}")
        self.count_var.set(f"Progress: {info.current} / {info.total}")
        self.result_var.set(
            "Succeeded: "
            f"{info.success_count}    Failed: {info.failure_count}    "
            f"Resized/Padded: {info.adjusted_count}    AlphaRef: {info.alpha_ref_count}"
        )
        self.progressbar["maximum"] = max(info.total, 1)
        self.progressbar["value"] = info.current
        self.root.update_idletasks()
        self.root.update()

    def finish(self, summary: str, success: bool) -> None:
        self.status_var.set("Completed" if success else "Completed with failures")
        self.file_var.set(summary.replace("\n", " | "))
        self.close_button.config(state="normal")
        self.root.update_idletasks()
        self.root.mainloop()


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch convert local BMP/JPG/PNG/TGA textures to DTX.")
    parser.add_argument("--no-ui", action="store_true", help="Print result to stdout instead of showing a progress window.")
    parser.add_argument("--base-dir", type=Path, help="Override the directory to scan for textures.")
    return parser.parse_args()


def bundled_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", app_dir()))


def dtxutil_path() -> Path:
    return bundled_dir() / "dtxutil.exe"


def next_power_of_two(value: int) -> int:
    power = 1
    while power < value:
        power *= 2
    return power


def normalize_image(image: Image.Image) -> tuple[Image.Image, bool]:
    width, height = image.size
    has_alpha = "A" in image.getbands()
    mode = "RGBA" if has_alpha else "RGB"
    if image.mode != mode:
        image = image.convert(mode)

    adjusted = False
    working = image
    if width > MAX_SIZE or height > MAX_SIZE:
        working = image.copy()
        working.thumbnail((MAX_SIZE, MAX_SIZE), Image.Resampling.LANCZOS)
        adjusted = True

    target_size = next_power_of_two(max(working.width, working.height))
    target_size = min(target_size, MAX_SIZE)

    if working.width == target_size and working.height == target_size:
        return working, adjusted

    adjusted = True
    background = (0, 0, 0, 0) if has_alpha else (0, 0, 0)
    canvas = Image.new(mode, (target_size, target_size), background)
    offset = ((target_size - working.width) // 2, (target_size - working.height) // 2)
    canvas.paste(working, offset)
    return canvas, adjusted


def image_has_transparency(image: Image.Image) -> bool:
    if "A" not in image.getbands():
        return False

    alpha_extrema = image.getchannel("A").getextrema()
    return alpha_extrema is not None and alpha_extrema[0] < 255


def is_in_excluded_dir(path: Path, base_dir: Path) -> bool:
    relative_parts = path.relative_to(base_dir).parts
    return any(part in EXCLUDED_DIRS for part in relative_parts[:-1])


def collect_input_files(base_dir: Path) -> list[Path]:
    return [
        path
        for path in sorted(base_dir.rglob("*"))
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
        and not is_in_excluded_dir(path, base_dir)
    ]


def convert_image_to_tga(source: Path, relative_source: Path, temp_dir: Path) -> tuple[Path, bool]:
    temp_tga = (temp_dir / relative_source).with_suffix(".tga")
    temp_tga.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        has_alpha = image_has_transparency(image)
        normalized, adjusted = normalize_image(image)
        normalized.save(temp_tga, format="TGA")
    return temp_tga, adjusted, has_alpha


def convert_tga_to_dtx(tga_file: Path, output_file: Path) -> None:
    command = [str(dtxutil_path()), "-tga2dtx", str(tga_file), str(output_file)]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip() or "dtxutil failed")


def read_command_string(data: bytearray) -> str:
    raw = bytes(data[DTX_COMMAND_OFFSET : DTX_COMMAND_OFFSET + DTX_COMMAND_LENGTH])
    return raw.split(b"\0", 1)[0].decode("ascii", errors="ignore")


def write_command_string(data: bytearray, value: str) -> None:
    encoded = value.encode("ascii")
    if len(encoded) >= DTX_COMMAND_LENGTH:
        raise ValueError(f"Command string too long: {value!r}")

    data[DTX_COMMAND_OFFSET : DTX_COMMAND_OFFSET + DTX_COMMAND_LENGTH] = b"\0" * DTX_COMMAND_LENGTH
    data[DTX_COMMAND_OFFSET : DTX_COMMAND_OFFSET + len(encoded)] = encoded


def patch_dtx_alpha_command(output_file: Path, has_alpha: bool) -> bool:
    data = bytearray(output_file.read_bytes())
    if len(data) < DTX_HEADER_SIZE:
        raise RuntimeError(f"DTX file too small: {output_file}")

    res_type = int.from_bytes(data[0:4], "little", signed=False)
    version = int.from_bytes(data[4:8], "little", signed=True)
    bpp_ident = data[26] or DTX_BPP_32

    if res_type != DTX_RESTYPE or version != DTX_VERSION:
        raise RuntimeError(f"Unsupported DTX header: resType={res_type}, version={version}")

    if bpp_ident != DTX_BPP_32:
        raise RuntimeError(f"Unsupported DTX pixel format: BPPIdent={bpp_ident}")

    current_command = read_command_string(data).strip()
    new_command = current_command

    if has_alpha:
        if re.search(r"(?i)\balpharef\s+\d+\b", current_command):
            new_command = re.sub(r"(?i)\balpharef\s+\d+\b", ALPHA_REF_COMMAND, current_command, count=1)
        elif re.search(r"(?i)\balphadef\s+\d+\b", current_command):
            new_command = re.sub(r"(?i)\balphadef\s+\d+\b", ALPHA_REF_COMMAND, current_command, count=1)
        elif current_command:
            new_command = f"{current_command}; {ALPHA_REF_COMMAND}"
        else:
            new_command = ALPHA_REF_COMMAND

    if new_command == current_command:
        return False

    write_command_string(data, new_command)
    output_file.write_bytes(data)
    return True


def write_log(log_file: Path, lines: list[str]) -> None:
    log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_summary(
    base_dir: Path,
    output_dir: Path,
    success_count: int,
    failure_count: int,
    adjusted_count: int,
    alpha_ref_count: int,
) -> str:
    log_file = base_dir / LOG_NAME
    return (
        f"Source folder: {base_dir}\n"
        f"Output folder: {output_dir}\n"
        f"Succeeded: {success_count}\n"
        f"Failed: {failure_count}\n"
        f"Resized or padded to compatible size: {adjusted_count}\n"
        f"AlphaRef command applied: {alpha_ref_count}\n"
        f"Log: {log_file}"
    )


def run(base_dir: Path | str | None = None, progress_window: ProgressWindow | None = None) -> tuple[str, bool]:
    base_dir = Path(base_dir).resolve() if base_dir is not None else app_dir().resolve()
    output_dir = base_dir / OUTPUT_DIR_NAME
    output_dir.mkdir(exist_ok=True)

    if not dtxutil_path().exists():
        raise FileNotFoundError(f"Missing dtxutil.exe: {dtxutil_path()}")

    input_files = collect_input_files(base_dir)
    if not input_files:
        return f"No supported files were found.\nFolder: {base_dir}", False

    log_lines: list[str] = []
    success_count = 0
    adjusted_count = 0
    alpha_ref_count = 0
    progress = ProgressInfo(total=len(input_files), stage="Scanning files...")

    if progress_window is not None:
        progress_window.update(progress)

    with tempfile.TemporaryDirectory(prefix="texture_to_dtx_") as temp_dir_name:
        temp_dir = Path(temp_dir_name)

        for index, source in enumerate(input_files, start=1):
            relative_source = source.relative_to(base_dir)
            output_file = (output_dir / relative_source).with_suffix(".dtx")
            output_file.parent.mkdir(parents=True, exist_ok=True)

            progress.current = index
            progress.current_file = str(relative_source)
            progress.stage = "Converting image..."

            try:
                temp_tga, adjusted, has_alpha = convert_image_to_tga(source, relative_source, temp_dir)
                progress.stage = "Generating DTX..."
                if progress_window is not None:
                    progress_window.update(progress)

                convert_tga_to_dtx(temp_tga, output_file)
                alpha_adjusted = patch_dtx_alpha_command(output_file, has_alpha)
                success_count += 1
                adjusted_count += int(adjusted)
                alpha_ref_count += int(alpha_adjusted)
                progress.success_count = success_count
                progress.adjusted_count = adjusted_count
                progress.alpha_ref_count = alpha_ref_count
                notes: list[str] = []
                if adjusted:
                    notes.append("adjusted-to-compatible-size")
                if alpha_adjusted:
                    notes.append(ALPHA_REF_COMMAND)
                note_text = f" [{', '.join(notes)}]" if notes else ""
                log_lines.append(f"OK   {relative_source} -> {output_file.relative_to(output_dir)}{note_text}")
            except Exception as exc:
                progress.failure_count += 1
                log_lines.append(f"FAIL {relative_source}: {exc}")

            if progress_window is not None:
                progress_window.update(progress)

    failure_count = len(input_files) - success_count
    log_file = base_dir / LOG_NAME
    write_log(log_file, log_lines)
    summary = build_summary(base_dir, output_dir, success_count, failure_count, adjusted_count, alpha_ref_count)
    return summary, failure_count == 0


def main() -> int:
    args = parse_args()

    if args.no_ui:
        try:
            message, success = run(args.base_dir)
        except Exception as exc:
            message = f"Processing failed:\n{exc}"
            success = False
        print(message)
        return 0 if success else 1

    progress_window = ProgressWindow(Path(args.base_dir).resolve() if args.base_dir else app_dir().resolve())
    try:
        message, success = run(args.base_dir, progress_window=progress_window)
    except Exception as exc:
        message = f"Processing failed:\n{exc}"
        success = False

    progress_window.finish(message, success)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
