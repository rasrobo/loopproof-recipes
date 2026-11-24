#!/usr/bin/env python3
"""build_midi_rising.py — House of the Rising Sun as a humanized MIDI recipe.

Source score: the repo's own scripts/abc_to_loops.py "rising" ABC —
6/8, A minor, 8 bars: Am C D F Am E Am E, with the traditional melody
(E4 pickup | A4 B4 | C5 E5 | D5 A4 | C5 E5 | A4 held | E4 held | A4 | E4).

Layered like the sim performance: drums programmed first, then one loop
at a time — chords (cycle 0), bass (cycle 1), the 6/8 arpeggio (cycle 2),
the melody (cycle 3) — then one full cycle and a held Am ending.
Each layer keeps its own fixed per-position lag (same take every cycle),
chord notes roll a few ms apart, velocities breathe +-3 per cycle.
"""
import random
import sys

import mido

random.seed(20261123)

EIGHTH = 0.32                      # seconds per eighth note
BAR = 6 * EIGHTH                   # 6/8 bar = 1.92 s
BPM = 60.0 / (2 * EIGHTH)          # quarter = 2 eighths -> 93.75

mid = mido.MidiFile(ticks_per_beat=480)
meta = mido.MidiTrack()
mid.tracks.append(meta)
meta.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(BPM), time=0))


def ticks(sec):
    return int(sec * (BPM / 60.0) * 480)


# bar -> (triad, bass root)
BARS = [
    ([57, 60, 64], 45),   # Am  A3 C4 E4 / A2
    ([60, 64, 67], 48),   # C   C4 E4 G4 / C3
    ([62, 66, 69], 50),   # D   D4 F#4 A4 / D3
    ([57, 60, 65], 41),   # F   A3 C4 F4 / F2
    ([57, 60, 64], 45),   # Am
    ([56, 59, 64], 40),   # E   G#3 B3 E4 / E2
    ([57, 60, 64], 45),   # Am
    ([56, 59, 64], 40),   # E
]

# melody: (offset eighths from cycle start, dur eighths, note)
MELODY = [
    (-2, 2, 64),          # E4 pickup
    (0, 4, 69), (4, 2, 71),      # A4 B4
    (6, 4, 72), (10, 2, 76),     # C5 E5
    (12, 4, 74), (16, 2, 69),    # D5 A4
    (18, 4, 72), (22, 2, 76),    # C5 E5
    (24, 6, 69),                 # A4 held
    (30, 6, 64),                 # E4 held
    (36, 6, 69),                 # A4 full bar
    (42, 6, 64),                 # E4 full bar
]

# fixed per-position human lags (seconds) — same take every cycle
lag_chord = {i: random.uniform(0.012, 0.038) for i in range(8)}
lag_bass = {i: random.uniform(0.010, 0.034) for i in range(48)}
lag_arp = {i: random.uniform(0.012, 0.036) for i in range(48)}
lag_mel = {i: random.uniform(0.018, 0.048) for i in range(len(MELODY))}

events = []  # (t_sec, channel, note, dur_sec, vel)


def add(t, ch, n, dur, vel):
    events.append((t, ch, n, dur, max(30, min(112, int(vel)))))


CYCLES = 5
for cyc in range(CYCLES):
    base = cyc * 8 * BAR
    breathe = random.uniform(-3, 3)
    for b, (triad, root) in enumerate(BARS):
        bt = base + b * BAR
        # drums — programmed into the sequencer, on grid, every cycle
        add(bt, 9, 36, 0.1, 98)                       # kick on 1
        add(bt + 3 * EIGHTH, 9, 38, 0.1, 86)          # snare on 2
        for e in range(6):
            add(bt + e * EIGHTH, 9, 42, 0.04, 42 + random.uniform(-4, 4))
        # chords — cycle 0: short struck triad at the bar head, finger roll
        for i, n in enumerate(sorted(triad)):
            add(bt + lag_chord[b] + i * 0.009, 0, n, BAR * 0.55,
                72 + breathe + (4 if i == 0 else 0) + random.uniform(-3, 3))
        # bass — cycle 1: root on 1, fifth on 2
        if cyc >= 1:
            add(bt + lag_bass[b * 6], 1, root, EIGHTH * 2.8,
                84 + breathe + random.uniform(-3, 3))
            add(bt + 3 * EIGHTH + lag_bass[b * 6 + 3], 1, root + 7, EIGHTH * 2.4,
                74 + breathe + random.uniform(-3, 3))
        # arpeggio — cycle 2: the 6/8 picking figure, r t f r+12 f t
        if cyc >= 2:
            r, t3, f5 = sorted(triad)
            fig = [r, t3, f5, r + 12, f5, t3]
            for e, n in enumerate(fig):
                add(bt + e * EIGHTH + lag_arp[b * 6 + e], 3, n, EIGHTH * 0.95,
                    62 + breathe + random.uniform(-3, 3))
    # melody — cycle 3: the vocal line, slightly behind the beat
    # (cycle level, NOT per-bar — offsets are relative to the cycle start)
    if cyc >= 3:
        for i, (off, dur_e, n) in enumerate(MELODY):
            add(base + off * EIGHTH + lag_mel[i], 2, n, dur_e * EIGHTH * 0.92,
                105 + breathe + random.uniform(-3, 3))

# ending: held Am, just after the last cycle
end_t = CYCLES * 8 * BAR + 0.35
for i, n in enumerate([45, 57, 60, 64, 69]):
    add(end_t + i * 0.012, 0, n, 3.0, 84)

def emit(name, chans):
    tr = mido.MidiTrack()
    mid.tracks.append(tr)
    tr.append(mido.MetaMessage("track_name", name=name, time=0))
    msgs = []
    for (t, ch, n, dur, vel) in events:
        if ch not in chans:
            continue
        msgs.append((ticks(t), mido.Message("note_on", channel=ch, note=n, velocity=vel, time=0)))
        msgs.append((ticks(t + dur), mido.Message("note_off", channel=ch, note=n, velocity=0, time=0)))
    msgs.sort(key=lambda e: e[0])
    last = 0
    for tk, m in msgs:
        m.time = tk - last
        last = tk
        tr.append(m)


t0 = mido.MidiTrack(); mid.tracks.append(t0)
for ch in (0, 1, 2, 3):
    prog = 73 if ch == 2 else 0   # melody = flute lead (audibility fix, 2026-11-23: same piano voice as the accompaniment buried it; band share 0.45 -> 0.68)
emit("keys+bass+melody+arp", {0, 1, 2, 3})
emit("drums", {9})
out = sys.argv[1] if len(sys.argv) > 1 else "rising.mid"
mid.save(out)
print("wrote", out, "bpm", round(BPM, 2), "duration ~", round(mido.MidiFile(out).length, 1), "s")
