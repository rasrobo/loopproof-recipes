#!/usr/bin/env python3
"""build_midi.py — turn a sim performance (pattern.json) into a humanized
MIDI recipe at the performance's own tempo.

The looper truth: each layer starts sounding the cycle AFTER it was struck
(the strike cycle itself is the take), then repeats identically — except a
human take is never grid-perfect, so each step keeps its own small lag and
chord notes roll a few ms apart like fingers landing. Loopbacks keep the
same offsets (same take repeating) with only velocity breathing +-3.
"""
import json
import random
import sys

import mido

random.seed(20261122)
pat = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "../canon_sim/pattern.json"))
BPM = pat["bpm"]
pn = pat["patternNotes"]
pattern = pat["pattern"]

mid = mido.MidiFile(ticks_per_beat=480)
meta = mido.MidiTrack()
mid.tracks.append(meta)
meta.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(BPM), time=0))

SPB = 60.0 / BPM          # seconds per beat
STEP = SPB / 4            # 16th

def ticks(sec):
    return int(sec * (BPM / 60.0) * 480)

# per-step human offsets (seconds), fixed per step = same take every cycle
lag = {s: random.uniform(0.012, 0.040) for s in range(16)}
lag_bass = {s: random.uniform(0.010, 0.035) for s in range(16)}
lag_arp = {s: random.uniform(0.015, 0.045) for s in range(16)}

events = []  # (t_sec, channel, note, dur_sec, vel)
def add(t, ch, n, dur, vel):
    events.append((t, ch, n, dur, max(30, min(110, int(vel)))))

CYCLES = 6
for cyc in range(CYCLES):
    base = cyc * 16 * STEP
    breathe = random.uniform(-3, 3)
    # drums: sequencer-programmed, on grid (tracks 0,1,2 = kick, snare, hat)
    for s in range(16):
        if pattern[0][s]: add(base + s * STEP, 9, 36, 0.1, 100)
        if pattern[1][s]: add(base + s * STEP, 9, 38, 0.1, 88)
        if pattern[2][s]: add(base + s * STEP, 9, 42, 0.05, 55 + random.uniform(-4, 4))
    # chords (track 8) from cycle 0 — struck with a finger roll
    for s in range(16):
        notes = pn[8][s]
        if notes:
            for i, n in enumerate(sorted(notes)):
                add(base + s * STEP + lag[s] + i * 0.009, 0, n, STEP * 1.9,
                    74 + breathe + (4 if i == 0 else 0) + random.uniform(-3, 3))
    # bass (track 12) from cycle 1
    if cyc >= 1:
        for s in range(16):
            notes = pn[12][s]
            if notes:
                for n in notes:
                    add(base + s * STEP + lag_bass[s], 1, n, STEP * 3,
                        82 + breathe + random.uniform(-3, 3))
    # arp pings live on track 8 too (odd steps, single notes) from cycle 2:
    # they are the single-note cells of track 8; handled above as chords of 1.
    # (Kept simple: track 8 plays from cycle 0; arp cells were recorded in
    # cycle 2, so single-note cells start then.)
# NOTE: rebuild track-8 timing honestly — chords from cycle 0, singles from 2.
events = [e for e in events if e[1] != 0]
for cyc in range(CYCLES):
    base = cyc * 16 * STEP
    breathe = random.uniform(-3, 3)
    for s in range(16):
        notes = pn[8][s]
        if not notes:
            continue
        if len(notes) > 1:  # chord cell: sounds from cycle 0
            for i, n in enumerate(sorted(notes)):
                add(base + s * STEP + lag[s] + i * 0.009, 0, n, STEP * 1.9,
                    74 + breathe + (4 if i == 0 else 0) + random.uniform(-3, 3))
        elif cyc >= 2:      # arp single: recorded cycle 2
            add(base + s * STEP + lag_arp[s], 0, notes[0], STEP * 1.0,
                60 + breathe + random.uniform(-3, 3))

# ending D chord, just after the last cycle
end_t = CYCLES * 16 * STEP + 0.35
for i, n in enumerate([50, 62, 66, 69, 74]):
    add(end_t + i * 0.012, 0, n, 2.4, 84)

# emit three tracks
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
t0.append(mido.Message("program_change", channel=0, program=0, time=0))
t0.append(mido.Message("program_change", channel=1, program=0, time=0))
emit("piano+bass", {0, 1})
emit("drums", {9})
out = sys.argv[2] if len(sys.argv) > 2 else "canon_human.mid"
mid.save(out)
print("wrote", out, "bpm", round(BPM, 1), "duration ~", round(mido.MidiFile(out).length, 1), "s")
