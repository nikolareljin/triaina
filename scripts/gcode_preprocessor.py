#!/usr/bin/env python3
"""Turn 2D vector G-code into drag-knife G-code for the triaina Klipper macros.

Input comes from Inkscape (gcodetools or similar), Inkcut, or LightBurn. Those
tools express "blade down" in one of two ways:

- a Z move down to cutting depth (Inkscape, most CNC post-processors), or
- a spindle/laser on command, ``M3``/``M4``, with ``M5`` for off (LightBurn).

Both are rewritten to the ``CUT_PLUNGE`` / ``CUT_RETRACT`` macros from
``config/klipper_cutter_macros.cfg``, so the real cutting and travel heights
live in one place on the printer and never in the job file.

The tool also removes anything that would drive the extruder, heaters or
fans, and caps every feedrate at ``--max-feed``.

Usage::

    python scripts/gcode_preprocessor.py input.gcode -o output.gcode
    python scripts/gcode_preprocessor.py input.gcode --max-feed 1200 --no-wrap

Exit codes: 0 on success, 1 on unreadable input or unwritable output,
2 on bad arguments (argparse).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

__all__ = [
    "Options",
    "classify_z_move",
    "main",
    "process_lines",
    "split_comment",
]

PLUNGE = "CUT_PLUNGE"
RETRACT = "CUT_RETRACT"

#: Commands removed outright: heaters, fans, extruder mode. A cutter job never
#: needs them and a stray M109 would stall the job waiting for a hot nozzle.
DROPPED_COMMANDS = frozenset(
    {"M82", "M83", "M104", "M106", "M107", "M109", "M140", "M190", "G10", "G11"}
)
#: Spindle/laser on. Mapped to CUT_PLUNGE.
SPINDLE_ON = frozenset({"M3", "M4"})
#: Spindle/laser off. Mapped to CUT_RETRACT.
SPINDLE_OFF = frozenset({"M5"})
#: Motion commands whose words are rewritten.
MOTION = frozenset({"G0", "G1"})

_WORD = re.compile(r"([A-Za-z])\s*([-+]?(?:\d+\.?\d*|\.\d+))")


@dataclass
class Options:
    """Settings for :func:`process_lines`.

    Attributes:
        max_feed: Upper bound for any ``F`` word, in mm/min.
        default_feed: ``F`` injected on the first motion line if the job never
            set one, in mm/min. Klipper would otherwise use its startup speed.
        z_threshold: Absolute Z at or below which the job means "cutting".
            Inkscape and most CAM tools cut at Z <= 0 and travel above it.
        wrap: Add the ``CUTTER_MODE`` header and ``PRINTER_MODE`` footer.
        home: Emit ``G28`` before ``CUTTER_MODE`` (only with ``wrap``).
    """

    max_feed: float = 1500.0
    default_feed: float = 1500.0
    z_threshold: float = 0.0
    wrap: bool = True
    home: bool = False


@dataclass
class _State:
    absolute: bool = True
    z: Optional[float] = None
    blade_down: bool = False
    feed_seen: bool = False
    dropped: dict = field(default_factory=dict)


def split_comment(line: str) -> tuple[str, str]:
    """Split a G-code line into ``(code, comment)``.

    Handles ``;`` comments and ``( ... )`` comments. The returned comment keeps
    its delimiter so it can be written back unchanged.
    """
    code, sep, tail = line.partition(";")
    comment = sep + tail
    parens = re.findall(r"\([^)]*\)", code)
    if parens:
        code = re.sub(r"\([^)]*\)", "", code)
        comment = " ".join(parens) + (" " + comment if comment else "")
    return code.strip(), comment.strip()


def classify_z_move(new_z: float, z_threshold: float, blade_down: bool) -> Optional[str]:
    """Decide what a move to absolute ``new_z`` means for the blade.

    Returns ``"CUT_PLUNGE"`` when the move enters cutting depth with the blade
    up, ``"CUT_RETRACT"`` when it leaves cutting depth with the blade down,
    and ``None`` when the blade state does not change (for example a second
    step-down while already cutting, or a travel-height change while up).

    The decision uses an absolute threshold rather than the sign of the move,
    because the first Z in a file has no previous Z to compare against, and
    multi-pass jobs step down several times while the blade stays engaged.
    """
    cutting = new_z <= z_threshold
    if cutting and not blade_down:
        return PLUNGE
    if not cutting and blade_down:
        return RETRACT
    return None


def _fmt(value: float) -> str:
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def _blade(action: Optional[str], state: _State, out: list[str]) -> None:
    if action == PLUNGE and not state.blade_down:
        out.append(PLUNGE)
        state.blade_down = True
    elif action == RETRACT and state.blade_down:
        out.append(RETRACT)
        state.blade_down = False


def _note_drop(state: _State, command: str) -> None:
    state.dropped[command] = state.dropped.get(command, 0) + 1


def _rewrite_motion(
    command: str, words: list[tuple[str, str]], state: _State, opts: Options, out: list[str]
) -> str:
    """Handle one G0/G1. Emits blade macros into ``out``; returns the motion line."""
    kept: list[str] = []
    for letter, raw in words:
        value = float(raw)
        if letter == "Z":
            new_z = value if state.absolute or state.z is None else state.z + value
            if not state.absolute and state.z is None:
                # Relative Z with no known start: use the sign as a fallback.
                new_z = opts.z_threshold + value
            state.z = new_z
            _blade(classify_z_move(new_z, opts.z_threshold, state.blade_down), state, out)
        elif letter == "E":
            _note_drop(state, "E")
        elif letter == "F":
            state.feed_seen = True
            kept.append("F" + _fmt(min(value, opts.max_feed)))
        else:
            kept.append(letter + raw)
    has_xy = any(w[0] in "XY" for w in kept)
    if has_xy and not state.feed_seen:
        kept.append("F" + _fmt(min(opts.default_feed, opts.max_feed)))
        state.feed_seen = True
    if not kept:
        return ""
    return " ".join([command] + kept)


def process_lines(lines: Iterable[str], opts: Optional[Options] = None) -> list[str]:
    """Rewrite G-code lines for the drag knife. Pure: no I/O.

    Args:
        lines: Input lines, with or without trailing newlines.
        opts: Settings; defaults to :class:`Options`.

    Returns:
        Output lines without trailing newlines.
    """
    opts = opts or Options()
    state = _State()
    body: list[str] = []

    for raw in lines:
        code, comment = split_comment(raw.rstrip("\r\n"))
        if not code:
            if comment:
                body.append(comment)
            continue

        if not re.match(r"[A-Za-z]\s*[-+.\d]", code):
            # Extended command such as a Klipper macro name. Pass through.
            body.append(f"{code} {comment}".rstrip())
            continue

        # N line numbers and *checksums carry no meaning once the file is rewritten.
        code = re.sub(r"\*\d+\s*$", "", code)
        words = [
            (m.group(1).upper(), m.group(2))
            for m in _WORD.finditer(code)
            if m.group(1).upper() != "N"
        ]
        if not words:
            # Not a G/M word line (for example a bare macro name). Keep it.
            body.append(raw.strip())
            continue

        letter, number = words[0]
        if letter == "T":
            # Tool change: lift the blade, drop the T word (Klipper has no
            # tool table unless one is configured, so T1 would error).
            _blade(RETRACT, state, body)
            _note_drop(state, "T")
            continue
        if letter not in "GMXYZEF":
            body.append(raw.strip())
            continue
        command = f"{letter}{int(float(number))}" if letter in "GM" else ""
        rest = words[1:] if command else words

        if command in DROPPED_COMMANDS:
            _note_drop(state, command)
            continue
        if command in SPINDLE_ON:
            _blade(PLUNGE, state, body)
            continue
        if command in SPINDLE_OFF:
            _blade(RETRACT, state, body)
            continue
        if command == "G90":
            state.absolute = True
        elif command == "G91":
            state.absolute = False

        if command in MOTION or not command:
            # A line with no G word continues the previous motion (modal G1).
            line = _rewrite_motion(command or "G1", rest, state, opts, body)
            if line:
                body.append(f"{line} {comment}".rstrip())
            continue

        body.append(f"{code} {comment}".rstrip())

    out = ["; processed by triaina gcode_preprocessor"]
    if state.dropped:
        summary = ", ".join(f"{k} x{v}" for k, v in sorted(state.dropped.items()))
        out.append(f"; removed: {summary}")
    if opts.wrap:
        out.append("G21")
        out.append("G90")
        if opts.home:
            out.append("G28")
        out.append("CUTTER_MODE")
        out.append(RETRACT)
    out.extend(body)
    if state.blade_down:
        out.append(RETRACT)
    if opts.wrap:
        out.append("PRINTER_MODE")
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gcode_preprocessor",
        description="Convert vector G-code into triaina drag-knife G-code.",
    )
    parser.add_argument("input", type=Path, help="source .gcode/.nc file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="destination file (default: <input>.cut.gcode; '-' for stdout)",
    )
    parser.add_argument(
        "--max-feed",
        type=float,
        default=Options.max_feed,
        help="cap for every F word, mm/min (default: %(default)s)",
    )
    parser.add_argument(
        "--default-feed",
        type=float,
        default=Options.default_feed,
        help="F used when the job sets none, mm/min (default: %(default)s)",
    )
    parser.add_argument(
        "--z-threshold",
        type=float,
        default=Options.z_threshold,
        help="Z at or below this is cutting depth (default: %(default)s)",
    )
    parser.add_argument(
        "--no-wrap", action="store_true", help="omit the CUTTER_MODE header and PRINTER_MODE footer"
    )
    parser.add_argument("--home", action="store_true", help="emit G28 before CUTTER_MODE")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.max_feed <= 0 or args.default_feed <= 0:
        print("error: feeds must be positive", file=sys.stderr)
        return 2
    opts = Options(
        max_feed=args.max_feed,
        default_feed=args.default_feed,
        z_threshold=args.z_threshold,
        wrap=not args.no_wrap,
        home=args.home,
    )
    try:
        lines = args.input.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        print(f"error: cannot read {args.input}: {exc.strerror}", file=sys.stderr)
        return 1

    result = "\n".join(process_lines(lines, opts)) + "\n"

    if args.output is not None and str(args.output) == "-":
        sys.stdout.write(result)
        return 0
    output = args.output or args.input.with_suffix(".cut.gcode")
    try:
        output.write_text(result, encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot write {output}: {exc.strerror}", file=sys.stderr)
        return 1
    print(f"wrote {output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
