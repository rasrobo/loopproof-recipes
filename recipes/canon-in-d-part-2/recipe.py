#!/usr/bin/env python3
"""build_midi_melody.py — Canon in D, Part 2 recipe: the MELODY on top
of the Part 1 accompaniment loop.

Accompaniment is exactly Part 1 (canon_v2, 45 BPM): drums every cycle,
chords from cycle 0, bass from cycle 1, arpeggio pings from cycle 2 —
read from the sim performance pattern (tools/canon_sim/pattern.json).

The melody enters once the accompaniment is complete (after cycle 5),
one note per chord — each melody note on the same step as its chord:
  phrase 1, cycle 6: F#5 E5 D5 C#5 B4 A4 B4 C#5 (over D A Bm F#m G D G A)
  phrase 2, cycle 7: D5 C#5 B4 A4 G4 F#4 G4 E4 (over the same chords)
Then the final D chord ending, as Part 1. The composition is verified
note-for-note by tools/composition_check.py + tools/spec_canon_part2.json.

FIXES (2026-11-23, Stephan's ear: "sounds off", twice):
1. The melody sits on its OWN channel (2). On channel 0 it shared
   note-offs with the chords and arp — one A4 was killed 13 ms after
   it started by the previous D chord's note-off.
2. Placement: an earlier build put the melody at steps 0,4,8,12 over
   two cycles per phrase, so most notes sat over the WRONG chord
   (E5 over Bm, C#5 over G...). Now one note per chord, in the cycle.
3. Audibility (Stephan's ear again, same day: "I don't hear the
   melody"): the melody was present and correct but rendered in the
   SAME piano voice as the accompaniment at a similar level, so it
   merged into the texture. It now renders as a flute lead (GM
   program 73) at velocity ~108. Measured on the rendered WAV: the
   melody's share of its pitch band went 0.35 -> 0.75. Lesson: a
   composition check proves the notes; only a level/timbre check
   proves anyone can HEAR them.
Humanized like Part 1: per-step lag, chord roll, velocity breathing.
"""
import json
import random
import sys

import mido

random.seed(20261123)
pat = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "../canon_sim/pattern.json"))
BPM = 45.0                      # canon_v2 tempo (Part 1 song)
pn = pat["patternNotes"]
pattern = pat["pattern"]

mid = mido.MidiFile(ticks_per_beat=480)
meta = mido.MidiTrack()
mid.tracks.append(meta)
meta.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(BPM), time=0))

SPB = 60.0 / BPM
STEP = SPB / 4                  # 16th = 0.3333 s; cycle = 5.3333 s

def ticks(sec):
    return int(sec * (BPM / 60.0) * 480)

lag = {s: random.uniform(0.012, 0.040) for s in range(16)}
lag_bass = {s: random.uniform(0.010, 0.035) for s in range(16)}
lag_arp = {s: random.uniform(0.015, 0.045) for s in range(16)}
lag_mel = {s: random.uniform(0.010, 0.030) for s in range(16)}

events = []  # (t_sec, channel, note, dur_sec, vel)
def add(t, ch, n, dur, vel):
    events.append((t, ch, n, dur, max(30, min(115, int(vel)))))

CYCLES = 10
for cyc in range(CYCLES):
    base = cyc * 16 * STEP
    breathe = random.uniform(-3, 3)
    for s in range(16):
        if pattern[0][s]: add(base + s * STEP, 9, 36, 0.1, 100)
        if pattern[1][s]: add(base + s * STEP, 9, 38, 0.1, 88)
        if pattern[2][s]: add(base + s * STEP, 9, 42, 0.05, 55 + random.uniform(-4, 4))
    for s in range(16):
        notes = pn[8][s]
        if not notes:
            continue
        if len(notes) > 1:      # chord cell: sounds from cycle 0
            for i, n in enumerate(sorted(notes)):
                add(base + s * STEP + lag[s] + i * 0.009, 0, n, STEP * 1.9,
                    74 + breathe + (4 if i == 0 else 0) + random.uniform(-3, 3))
        elif cyc >= 2:          # arp single: recorded cycle 2
            add(base + s * STEP + lag_arp[s], 0, notes[0], STEP * 1.0,
                60 + breathe + random.uniform(-3, 3))
    if cyc >= 1:                # bass from cycle 1
        for s in range(16):
            notes = pn[12][s]
            if notes:
                for n in notes:
                    add(base + s * STEP + lag_bass[s], 1, n, STEP * 3,
                        82 + breathe + random.uniform(-3, 3))

# ---- the melody (Part 2) — own channel (2), ONE NOTE PER CHORD ----
# Chords sit at steps 0,2,4,...,14; the melody note for each chord sits
# on the SAME step, so phrase 1 spans ONE cycle (steps 0..14, 2 apart),
# phrase 2 the next. (An earlier build placed notes at steps 0,4,8,12
# over two cycles — most notes landed over the wrong chord and the
# composition check caught it. Spec: tools/spec_canon_part2.json.)
PHRASE1 = {6: [78, 76, 74, 73, 71, 69, 71, 73]}   # over D A Bm F#m G D G A
PHRASE2 = {7: [74, 73, 71, 69, 67, 66, 67, 64]}   # over D A Bm F#m G D G A
for table in (PHRASE1, PHRASE2):
    for cyc, notes in table.items():
        base = cyc * 16 * STEP
        for k, n in enumerate(notes):
            s = 2 * k
            add(base + s * STEP + lag_mel[s], 2, n, STEP * 2 * 0.96,
                108 + random.uniform(-3, 3))

# ending D chord, just after the last cycle
end_t = CYCLES * 16 * STEP + 0.35
for i, n in enumerate([50, 62, 66, 69, 74]):
    add(end_t + i * 0.012, 0, n, 2.4, 84)

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
t0.append(mido.Message("program_change", channel=2, program=73, time=0))  # flute lead — see FIX 3
emit("piano+bass+melody", {0, 1, 2})
emit("drums", {9})
out = sys.argv[2] if len(sys.argv) > 2 else "canon_part2.mid"
mid.save(out)
print("wrote", out, "bpm", BPM, "duration ~", round(mido.MidiFile(out).length, 1), "s")

# ---- verify the melody content from the file just written ----
m2 = mido.MidiFile(out)
ons = {}
seq = []
for tr in m2.tracks:
    t = 0
    for msg in tr:
        t += msg.time
        if msg.type == "note_on" and msg.velocity > 0 and msg.channel == 2:
            ons[(msg.channel, msg.note, t)] = t
            seq.append((t, msg.note))
        if msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            for k in [k for k in ons if k[0] == msg.channel and k[1] == msg.note]:
                seq.append(("off", ons.pop(k), msg.note, t))
                break
mel = {}
for item in seq:
    if item[0] == "off":
        _, on_t, n, off_t = item
        cyc = int(on_t / ticks(16 * STEP))
        if cyc >= 6 and n >= 63:
            mel.setdefault(cyc, []).append((n, round((off_t - on_t) / ticks(STEP), 2)))
print("MELODY per cycle (note, dur in steps):")
for cyc in sorted(mel):
    print(" cycle", cyc, sorted(mel[cyc], key=lambda x: -x[0]) if False else mel[cyc])
