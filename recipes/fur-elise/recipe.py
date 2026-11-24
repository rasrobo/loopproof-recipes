"""Für Elise — recipe v2, built from a VERIFIED source, not from memory.

Source: Mutopia Project, Mutopia-2015/08/18-931, typeset by Stelios
Samelis (public domain) — LilyPond engraving of Beethoven WoO 59,
downloaded from mutopiaproject.org (file: tools/verified/
fuer_elise_mutopia_woo59.mid; a GitHub mirror agreed byte-for-byte).

Extracted from that file (absolute eighth-note steps of the strain,
48 steps = 16 bars of 3/8): the melody line, the held-note sustains
(2 eighths; the closing A4 rings 4), the bass roots (they land on the
third eighth of the held-note bars), the two-hand broken-chord figure,
and the harmony rhythm (Am, turning to E under the held B4s, back to Am).

The source MIDI is flat-velocity (LilyPond does not encode the score's
dynamics) and carries no pedal data, so the dynamics here are an
editorial layer, documented as such: the strain is dolce, the second
statement swells slightly, and the closing descent (C5 - B4 - A4)
carries the crescendo. Pitches, durations, sustains and harmony are
the verified file's, untouched.

Layering (LoopProof format): drums + chords from cycle 0, bass cycle 1,
broken chords cycle 2, melody cycles 3-4 (the strain repeats, as in the
piece), final Am sonority to close. Each layer on its own channel; the
melody rides the flute lead (GM 73) so it sings over the accompaniment.
"""
import json
import random

import mido

EIGHTH = 0.30                        # seconds per step (performance tempo)
BAR = 3 * EIGHTH
CYCLE_S = 48 * EIGHTH                # 14.4 s — the 16-bar strain
BPM = 60.0 / (2 * EIGHTH)            # 100.0

mid = mido.MidiFile(ticks_per_beat=480)
meta = mido.MidiTrack()
mid.tracks.append(meta)
meta.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(BPM), time=0))


def ticks(sec):
    return int(sec * (BPM / 60.0) * 480)


events = []  # (time_ticks, channel, note, dur_ticks, velocity)
expected = []  # melody notes in song seconds, for the output audit


def add(t, ch, n, dur, vel):
    events.append((ticks(t), ch, n, ticks(dur), vel))


rng = random.Random(11)

# ---- verified strain tables (step -> pitch), from the Mutopia file ----
MELODY = {0: (76, 1), 1: (75, 1), 2: (76, 1), 3: (75, 1), 4: (76, 1),
          5: (71, 1), 6: (74, 1), 7: (72, 1), 8: (69, 2),
          14: (71, 2), 20: (72, 2),
          24: (76, 1), 25: (75, 1), 26: (76, 1), 27: (75, 1), 28: (76, 1),
          29: (71, 1), 30: (74, 1), 31: (72, 1), 32: (69, 2),
          38: (71, 2), 42: (72, 1), 43: (71, 1), 44: (69, 4)}
BASS = {8: 45, 14: 40, 20: 45, 32: 45, 38: 40, 44: 45}
ARP = {9: 52, 10: 57, 11: 60, 12: 64, 13: 69, 15: 52, 16: 56, 17: 64,
       18: 68, 19: 71, 21: 52, 22: 57, 23: 64,
       33: 52, 34: 57, 35: 60, 36: 64, 37: 69, 39: 52, 40: 56, 41: 64,
       45: 52, 46: 57}
# harmony segments (step range -> chord): Am except E under the held B4s
def chord_at(step):
    if 14 <= step < 20 or 38 <= step < 44:
        return (59, 64, 68)          # E
    return (57, 60, 64)              # Am

CYCLES = 5
for cyc in range(CYCLES):
    base = cyc * CYCLE_S
    for bar in range(16):
        bb = base + bar * BAR
        lag = rng.uniform(-0.004, 0.008)
        # drums — the LoopProof pulse (our format's spine, not the score's)
        add(bb, 9, 36, 0.09, 84)
        if bar in (3, 7, 11, 15):
            add(bb, 9, 38, 0.09, 76)
        for s in range(3):
            add(bb + s * EIGHTH, 9, 42, 0.05, 44)
        # chords — one triad per bar, harmony from the verified segments
        for j, n in enumerate(chord_at(bar * 3)):
            add(bb + lag + j * 0.012, 0, n, 2.8 * EIGHTH,
                70 + rng.randint(-5, 5))
    if cyc >= 1:  # bass roots, on their verified steps
        for st, n in BASS.items():
            add(base + st * EIGHTH, 1, n, 1.9 * EIGHTH, 92)
    if cyc >= 2:  # the two-hand broken-chord figure, verified steps
        for st, n in ARP.items():
            add(base + st * EIGHTH + rng.uniform(-0.004, 0.008), 3, n,
                0.95 * EIGHTH, 58 + rng.randint(-4, 4))
    if cyc >= 3:  # melody — the strain, twice, with its sustains
        for st, (n, dsteps) in MELODY.items():
            vel = 100
            if dsteps >= 2:
                vel = 104
            if st >= 24:
                vel += 6             # second statement swells
            if st >= 42:
                vel += 6             # the closing crescendo
            t = base + st * EIGHTH
            dur = dsteps * 0.95 * EIGHTH
            add(t, 2, n, dur, vel + rng.randint(-3, 3))
            expected.append({"note": n, "onset": round(t, 3),
                             "dur": round(dur, 3), "vel": vel})

# ending — final Am sonority, struck once and left ringing
end_t = CYCLES * CYCLE_S + 0.35
add(end_t, 1, 45, 2.2, 95)
for j, n in enumerate((57, 60, 64)):
    add(end_t + j * 0.012, 0, n, 2.2, 82)
add(end_t, 2, 69, 2.2, 104)
expected.append({"note": 69, "onset": round(end_t, 3), "dur": 2.2, "vel": 104})


def emit(name, chans):
    tr = mido.MidiTrack()
    mid.tracks.append(tr)
    msgs = []
    for (t, ch, n, d, v) in events:
        if ch not in chans:
            continue
        msgs.append((t, mido.Message("note_on", channel=ch, note=n,
                                     velocity=v, time=0)))
        msgs.append((t + d, mido.Message("note_off", channel=ch, note=n,
                                         velocity=0, time=0)))
    msgs.sort(key=lambda x: x[0])
    last = 0
    for t, m in msgs:
        m.time = t - last
        last = t
        tr.append(m)
    tr.append(mido.MetaMessage("end_of_track", time=0))


t0 = mid.tracks[0]
for ch, prog in ((0, 0), (1, 32), (2, 73), (3, 0), (9, 0)):
    t0.append(mido.Message("program_change", channel=ch, program=prog, time=0))

emit("melody+chords", {0, 2, 3})
emit("bass+drums", {1, 9})

out = "fuer_elise_v2.mid"
mid.save(out)
with open("fuer_expected.json", "w") as f:
    json.dump({"song": "Für Elise (verified Mutopia WoO 59)",
               "melody": expected}, f, indent=1)
print("wrote", out, "duration ~", round(mido.MidiFile(out).length, 1), "s;",
      len(expected), "expected melody notes for the output audit")
