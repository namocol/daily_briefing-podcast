#!/usr/bin/env python3
"""Build the WebVTT transcript and HTML show-notes page for an episode.

Library use (from make_episode.py):
    write_vtt(paragraphs, spans, "episode.vtt")   # spans = [(start_sec, end_sec), ...]

CLI use, for audio recorded without timings:
    python3 transcript.py estimate <script.txt> <episode.mp3> <out.vtt>
estimates the timings from text length (TTS speaks at a steady rate).
"""
import re, subprocess, sys


def _ts(t):
    h, rem = divmod(max(t, 0), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def _sentences(p):
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'])", p.strip())
    return [s for s in parts if s]


def write_vtt(paragraphs, spans, out_path):
    """One cue per sentence; each paragraph's time is split across its sentences by length."""
    lines = ["WEBVTT", ""]
    n = 1
    for para, (start, end) in zip(paragraphs, spans):
        sents = _sentences(para)
        total = sum(len(s) for s in sents) or 1
        t = start
        for s in sents:
            dur = (end - start) * len(s) / total
            lines += [str(n), f"{_ts(t)} --> {_ts(t + dur)}", "Narrator: " + s, ""]
            t += dur
            n += 1
    open(out_path, "w").write("\n".join(lines))


def paragraphs_of(path):
    return [p.strip() for p in open(path).read().split("\n\n") if p.strip()]


def estimate(script, mp3, out_vtt, gap=0.45):
    """TTS speaks at a near-constant rate, so split the audio by text length.

    gap is the silence inserted after every paragraph when the episode was recorded.
    """
    paras = paragraphs_of(script)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "csv=p=0", mp3], capture_output=True, text=True).stdout)
    speech = dur - gap * len(paras)
    total = sum(len(p) for p in paras)
    spans, t = [], 0.0
    for p in paras:
        d = speech * len(p) / total
        spans.append((t, t + d))
        t += d + gap
    write_vtt(paras, spans, out_vtt)


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "estimate":
        estimate(*sys.argv[2:])
    else:
        sys.exit(__doc__)
