"""Tests for scripts/gcode_preprocessor.py."""

from pathlib import Path

import pytest

from gcode_preprocessor import (
    PLUNGE,
    RETRACT,
    Options,
    classify_z_move,
    main,
    process_lines,
    split_comment,
)

RAW = Options(wrap=False)


def body(lines, opts=RAW):
    """Output without the provenance comment lines."""
    return [
        line
        for line in process_lines(lines, opts)
        if not line.startswith(("; processed by triaina", "; removed:"))
    ]


class TestSpindle:
    def test_m3_becomes_plunge_and_m5_retract(self):
        assert body(["M3 S1000", "G1 X10 F600", "M5"]) == [PLUNGE, "G1 X10 F600", RETRACT]

    def test_m4_is_plunge(self):
        assert body(["M4"]) == [PLUNGE, RETRACT]

    def test_repeated_m3_plunges_once(self):
        assert body(["M3", "M3", "M5", "M5"]) == [PLUNGE, RETRACT]

    def test_m5_with_blade_up_emits_nothing(self):
        assert body(["M5"]) == []

    def test_leading_zero_command(self):
        assert body(["M03", "M05"]) == [PLUNGE, RETRACT]


class TestZ:
    def test_down_then_up(self):
        out = body(["G0 Z5", "G1 Z-0.5 F300", "G1 X10 Y10", "G0 Z5"])
        assert out == [PLUNGE, "G1 F300", "G1 X10 Y10", RETRACT]

    def test_z_word_removed_from_combined_move(self):
        assert body(["G1 X5 Z-1 F500"]) == [PLUNGE, "G1 X5 F500", RETRACT]

    def test_multipass_step_down_keeps_blade_down(self):
        out = body(["G1 Z-0.1 F300", "G1 X1", "G1 Z-0.2", "G1 X2", "G0 Z3"])
        assert out.count(PLUNGE) == 1
        assert out.count(RETRACT) == 1

    def test_custom_threshold(self):
        opts = Options(wrap=False, z_threshold=0.5)
        assert body(["G1 Z0.4 F300"], opts)[0] == PLUNGE

    def test_relative_mode(self):
        out = body(["G90", "G0 Z3", "G91", "G1 Z-3.5 F300", "G1 Z4"])
        assert out == ["G90", "G91", PLUNGE, "G1 F300", RETRACT]

    @pytest.mark.parametrize(
        "z, down, expected",
        [
            (-1.0, False, PLUNGE),
            (0.0, False, PLUNGE),
            (-1.0, True, None),
            (2.0, True, RETRACT),
            (2.0, False, None),
        ],
    )
    def test_classify(self, z, down, expected):
        assert classify_z_move(z, 0.0, down) == expected


class TestStripping:
    def test_e_words_removed(self):
        assert body(["G1 X1 Y2 E0.5 F600"]) == ["G1 X1 Y2 F600"]

    def test_heater_and_fan_commands_dropped(self):
        assert body(["M104 S200", "M109 S200", "M140 S60", "M106 S255", "M107"]) == []

    def test_drop_summary_comment(self):
        out = process_lines(["M104 S200", "M104 S0"], RAW)
        assert "; removed: M104 x2" in out

    def test_tool_change_retracts(self):
        assert body(["M3", "T1", "G1 X1 F100"]) == [PLUNGE, RETRACT, "G1 X1 F100"]

    def test_line_numbers_and_checksum_removed(self):
        assert body(["N10 G1 X1 F100*57"]) == ["G1 X1 F100"]


class TestFeed:
    def test_feed_clamped(self):
        assert body(["G1 X1 F9000"], Options(wrap=False, max_feed=1200)) == ["G1 X1 F1200"]

    def test_default_feed_injected_once(self):
        out = body(["G1 X1", "G1 X2"], Options(wrap=False, default_feed=800))
        assert out == ["G1 X1 F800", "G1 X2"]

    def test_default_feed_never_exceeds_max(self):
        out = body(["G1 X1"], Options(wrap=False, default_feed=5000, max_feed=1000))
        assert out == ["G1 X1 F1000"]

    def test_explicit_feed_suppresses_default(self):
        assert body(["G1 F300", "G1 X1"]) == ["G1 F300", "G1 X1"]


class TestPassThrough:
    def test_comments_kept(self):
        assert body(["; header", "G1 X1 F100 ; cut", "(paren)"]) == [
            "; header",
            "G1 X1 F100 ; cut",
            "(paren)",
        ]

    def test_macro_lines_kept(self):
        assert body(["SET_VELOCITY_LIMIT ACCEL=500"]) == ["SET_VELOCITY_LIMIT ACCEL=500"]

    def test_split_comment(self):
        assert split_comment("G1 X1 (a) ; b") == ("G1 X1", "(a) ; b")


class TestWrap:
    def test_header_and_footer(self):
        out = process_lines(["G1 X1 F100"], Options(home=True))
        assert out[out.index("G28") : out.index("G28") + 3] == ["G28", "CUTTER_MODE", RETRACT]
        assert out[-1] == "PRINTER_MODE"

    def test_footer_lifts_blade_left_down(self):
        out = process_lines(["M3", "G1 X1 F100"])
        assert out[-2:] == [RETRACT, "PRINTER_MODE"]

    def test_footer_no_duplicate_retract(self):
        out = process_lines(["M3", "G1 X1 F100", "M5"])
        assert out[-3:] == ["G1 X1 F100", RETRACT, "PRINTER_MODE"]

    def test_no_wrap_still_lifts_blade_at_end(self):
        assert body(["M3"])[-1] == RETRACT


class TestCli:
    def test_writes_default_output(self, tmp_path: Path):
        src = tmp_path / "job.gcode"
        src.write_text("M3\nG1 X1 Y1 E1 F99999\nM5\n")
        assert main([str(src)]) == 0
        text = (tmp_path / "job.cut.gcode").read_text()
        assert "CUTTER_MODE" in text and "E1" not in text and "F1500" in text

    def test_explicit_output(self, tmp_path: Path):
        src = tmp_path / "a.nc"
        dst = tmp_path / "b.gcode"
        src.write_text("G1 X1\n")
        assert main([str(src), "-o", str(dst), "--no-wrap"]) == 0
        assert "CUTTER_MODE" not in dst.read_text()

    def test_stdout(self, tmp_path: Path, capsys):
        src = tmp_path / "a.gcode"
        src.write_text("G1 X1\n")
        assert main([str(src), "-o", "-"]) == 0
        assert "G1 X1 F1500" in capsys.readouterr().out

    def test_missing_input(self, tmp_path: Path, capsys):
        assert main([str(tmp_path / "nope.gcode")]) == 1
        assert "cannot read" in capsys.readouterr().err

    def test_rejects_non_positive_feed(self, tmp_path: Path):
        src = tmp_path / "a.gcode"
        src.write_text("G1 X1\n")
        assert main([str(src), "--max-feed", "0"]) == 2
