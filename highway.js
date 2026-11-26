/* Note Highway — LoopProof recipe pages.
 * A Guitar-Hero-style piano-roll highway: notes travel toward a hit
 * line and land exactly on their step, driven by the same audio-clock
 * scheduler that plays the song, so picture and sound cannot drift.
 * Audio: the simulator's own samples (pitch-shifted from their roots,
 * as the sim's keygroup engine does) with synthesized fallbacks; the
 * melody is a synthesized flute (the sim kit has no flute).
 * Build mode adds one layer per loop cycle — the LoopProof build. */
(function () {
  "use strict";
  var dataEl = document.getElementById("hw-data");
  var canvas = document.getElementById("hw-canvas");
  if (!dataEl || !canvas) return;
  var DATA = JSON.parse(dataEl.textContent);
  var STEPS = DATA.steps, SPB = DATA.stepsPerBar || 3;
  var STEP_DUR = 30 / DATA.bpm;               // bpm is quarter-note tempo; a step is an eighth
  var LAYERS = DATA.layers;
  var SIM_SAMPLES = "https://rasrobo.github.io/0700-aam-sim/samples/";
  var REDUCED = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------------- state ---------------- */
  var mode = "build";                          // "build" | "manual"
  var manual = {};                             // layerId -> bool (manual mode)
  LAYERS.forEach(function (l) { manual[l.id] = true; });
  var playing = false, ctx = null, master = null;
  var startAt = 0;                             // ctx time of abs step 0
  var pausedFloat = 0;                         // abs step float when paused
  var nextAbs = 0;                             // next abs step to schedule
  var timer = null, activeVoices = [];
  var scheduledLog = [];                       // debug/verification surface

  function buildCount(cycle) {                 // layers active in build mode
    return Math.min(cycle + 1, LAYERS.length);
  }
  function layerOn(idx, cycle) {
    if (mode === "build") return idx < buildCount(cycle);
    return !!manual[LAYERS[idx].id];
  }
  function stepFloat() {
    if (!ctx) return pausedFloat;
    if (playing) return (ctx.currentTime - startAt) / STEP_DUR;
    return pausedFloat;
  }

  /* ---------------- audio ---------------- */
  var buffers = {}, samplesOk = false, samplesTried = false;
  function ensureCtx() {
    if (ctx) return;
    var AC = window.AudioContext || window.webkitAudioContext;
    ctx = new AC();
    master = ctx.createGain(); master.gain.value = 0.9;
    var comp = ctx.createDynamicsCompressor();
    master.connect(comp); comp.connect(ctx.destination);
  }
  function loadSamples() {
    if (samplesTried) return; samplesTried = true;
    var want = { kick: "kick.wav", snare: "snare.wav", hat: "hat_closed.wav",
                 tone: "mel_e4.wav", bass: "bass_e1.wav" };
    var names = Object.keys(want);
    Promise.all(names.map(function (k) {
      return fetch(SIM_SAMPLES + want[k]).then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.arrayBuffer();
      }).then(function (ab) { return ctx.decodeAudioData(ab); })
        .then(function (buf) { buffers[k] = buf; });
    })).then(function () {
      samplesOk = names.every(function (k) { return buffers[k]; });
    }).catch(function () { samplesOk = false; });
  }
  function noiseBuf() {
    if (buffers._noise) return buffers._noise;
    var b = ctx.createBuffer(1, ctx.sampleRate * 1, ctx.sampleRate);
    var d = b.getChannelData(0);
    for (var i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    buffers._noise = b; return b;
  }
  function track(voice) { activeVoices.push(voice); }
  function playBuf(buf, when, rate, gain) {
    var s = ctx.createBufferSource(); s.buffer = buf;
    s.playbackRate.value = rate;
    var g = ctx.createGain(); g.gain.value = gain;
    s.connect(g); g.connect(master); s.start(when); track(s);
  }
  function noiseHit(when, dur, freq, q, gain, type) {
    var s = ctx.createBufferSource(); s.buffer = noiseBuf();
    s.loop = true;
    var f = ctx.createBiquadFilter(); f.type = type || "bandpass";
    f.frequency.value = freq; f.Q.value = q;
    var g = ctx.createGain();
    g.gain.setValueAtTime(gain, when);
    g.gain.exponentialRampToValueAtTime(0.001, when + dur);
    s.connect(f); f.connect(g); g.connect(master);
    s.start(when); s.stop(when + dur + 0.05); track(s);
  }
  function tone(when, freq, dur, peak, type, glideTo) {
    var o = ctx.createOscillator(); o.type = type || "sine";
    o.frequency.setValueAtTime(freq, when);
    if (glideTo) o.frequency.exponentialRampToValueAtTime(glideTo, when + 0.08);
    var g = ctx.createGain();
    g.gain.setValueAtTime(0, when);
    g.gain.linearRampToValueAtTime(peak, when + 0.012);
    g.gain.exponentialRampToValueAtTime(0.001, when + dur);
    o.connect(g); g.connect(master);
    o.start(when); o.stop(when + dur + 0.05); track(o);
  }
  function flute(when, midi, durSteps) {
    var f = 440 * Math.pow(2, (midi - 69) / 12);
    var dur = Math.max(0.18, durSteps * STEP_DUR * 0.96);
    var o = ctx.createOscillator(); o.type = "sine";
    o.frequency.value = f;
    var o2 = ctx.createOscillator(); o2.type = "sine";
    o2.frequency.value = f * 2;
    var vib = ctx.createOscillator(); vib.frequency.value = 5.2;
    var vibG = ctx.createGain(); vibG.gain.value = REDUCED ? 0 : 3.5;
    vib.connect(vibG); vibG.connect(o.detune);
    var g = ctx.createGain(), g2 = ctx.createGain(); g2.gain.value = 0.12;
    g.gain.setValueAtTime(0, when);
    g.gain.linearRampToValueAtTime(0.34, when + 0.07);
    g.gain.setValueAtTime(0.34, when + Math.max(0.07, dur - 0.09));
    g.gain.linearRampToValueAtTime(0, when + dur);
    o.connect(g); o2.connect(g2); g2.connect(g); g.connect(master);
    // breath: a whisper of filtered noise under the tone
    var n = ctx.createBufferSource(); n.buffer = noiseBuf(); n.loop = true;
    var nf = ctx.createBiquadFilter(); nf.type = "bandpass";
    nf.frequency.value = f; nf.Q.value = 2.5;
    var ng = ctx.createGain(); ng.gain.value = 0.012;
    n.connect(nf); nf.connect(ng); ng.connect(master);
    [o, o2, vib, n].forEach(function (v) {
      v.start(when); v.stop(when + dur + 0.05); track(v);
    });
  }
  var SEMI = function (note, root) { return Math.pow(2, (note - root) / 12); };
  function playNote(layerId, note, when, durSteps) {
    var f = 440 * Math.pow(2, (note - 69) / 12);
    if (layerId === "drums") {
      if (note === 36) {                       // kick
        if (samplesOk) playBuf(buffers.kick, when, 1, 0.9);
        else tone(when, 150, 0.24, 0.8, "sine", 42);
      } else if (note === 38) {                // snare
        if (samplesOk) playBuf(buffers.snare, when, 1, 0.7);
        else { noiseHit(when, 0.16, 1800, 0.8, 0.4); tone(when, 190, 0.09, 0.25, "triangle"); }
      } else {                                 // hats
        if (samplesOk) playBuf(buffers.hat, when, 1, 0.5);
        else noiseHit(when, 0.045, 8000, 1.2, 0.22, "highpass");
      }
    } else if (layerId === "bass") {
      if (samplesOk) playBuf(buffers.bass, when, SEMI(note, 40), 0.8);
      else tone(when, f, Math.min(0.55, durSteps * STEP_DUR), 0.5, "triangle");
    } else if (layerId === "melody") {
      flute(when, note, durSteps);
    } else {                                   // chords + figures: sim e-piano one-shot
      var g = layerId === "chords" ? 0.34 : 0.4;
      if (samplesOk) playBuf(buffers.tone, when, SEMI(note, 64), g);
      else tone(when, f, 0.5, 0.22, "triangle");
    }
  }

  /* ---------------- scheduler ---------------- */
  function scheduleStep(absStep) {
    var cyc = Math.floor(absStep / STEPS), step = absStep % STEPS;
    var when = startAt + absStep * STEP_DUR;
    LAYERS.forEach(function (layer, idx) {
      if (!layerOn(idx, cyc)) return;
      layer.notes.forEach(function (n) {
        if (n[0] === step) {
          playNote(layer.id, n[1], when, n[2]);
          scheduledLog.push({ layer: layer.id, step: step, note: n[1],
                              when: when, cycle: cyc });
          if (scheduledLog.length > 400) scheduledLog.shift();
        }
      });
    });
  }
  function tick() {
    var horizon = ctx.currentTime + 0.15;
    while (startAt + nextAbs * STEP_DUR < horizon) {
      if (startAt + nextAbs * STEP_DUR >= ctx.currentTime - STEP_DUR)
        scheduleStep(nextAbs);
      nextAbs++;
    }
  }
  function stopVoices() {
    activeVoices.forEach(function (v) { try { v.stop(); } catch (e) {} });
    activeVoices = [];
  }

  /* ---------------- controls ---------------- */
  var playBtn = document.getElementById("hw-play");
  var buildBtn = document.getElementById("hw-build");
  var readout = document.getElementById("hw-readout");
  var chips = Array.prototype.slice.call(
    document.querySelectorAll(".hw-chip"));
  function refreshChips(cycle) {
    chips.forEach(function (chip, idx) {
      var on = layerOn(idx, cycle);
      chip.setAttribute("aria-pressed", on ? "true" : "false");
      chip.classList.toggle("hw-off", !on);
    });
    buildBtn.setAttribute("aria-pressed", mode === "build" ? "true" : "false");
    buildBtn.textContent = "Build mode: " + (mode === "build" ? "on" : "off");
    buildBtn.classList.toggle("hw-on", mode === "build");
  }
  function play() {
    ensureCtx(); loadSamples();
    if (ctx.state === "suspended") ctx.resume();
    startAt = ctx.currentTime + 0.08 - pausedFloat * STEP_DUR;
    nextAbs = Math.ceil(pausedFloat);
    playing = true;
    timer = setInterval(tick, 30); tick();
    playBtn.textContent = "⏸ Pause";
  }
  function pause() {
    pausedFloat = stepFloat();
    playing = false;
    clearInterval(timer); stopVoices();
    playBtn.textContent = "▶ Play";
  }
  playBtn.addEventListener("click", function () { playing ? pause() : play(); });
  document.getElementById("hw-restart").addEventListener("click", function () {
    pausedFloat = 0; scheduledLog.length = 0;
    if (playing) { clearInterval(timer); stopVoices();
      startAt = ctx.currentTime + 0.08; nextAbs = 0;
      timer = setInterval(tick, 30); tick(); }
    refreshChips(0);
  });
  function freezeBuild() {                     // manual takes over what
    if (!playing && stepFloat() === 0) return;   // is audible right now;
    var cyc = Math.floor(stepFloat() / STEPS);   // before the first play
    LAYERS.forEach(function (l, i) { manual[l.id] = layerOn(i, cyc); });
  }                                              // manual keeps its defaults
  buildBtn.addEventListener("click", function () {
    if (mode === "build") { freezeBuild(); mode = "manual"; }
    else mode = "build";
    refreshChips(Math.floor(stepFloat() / STEPS));
  });
  chips.forEach(function (chip, idx) {
    chip.addEventListener("click", function () {
      if (mode === "build") {                  // manual override ends build
        freezeBuild();
        mode = "manual";
      }
      manual[LAYERS[idx].id] = !manual[LAYERS[idx].id];
      refreshChips(Math.floor(stepFloat() / STEPS));
    });
  });

  /* ---------------- visuals ---------------- */
  var SPACING = 2.1, LOOKAHEAD = 13, WIDTH = 26;
  var PITCH_MIN = 36, PITCH_MAX = 76;
  function pitchX(n) {
    return ((n - PITCH_MIN) / (PITCH_MAX - PITCH_MIN) - 0.5) * (WIDTH - 3);
  }
  var useGL = false, renderer, scene, camera, noteMeshes = [], linePool = [];
  var hitMat;
  function initGL() {
    if (!window.THREE) return false;
    try {
      renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true });
    } catch (e) { return false; }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0b0e17);
    scene.fog = new THREE.Fog(0x0b0e17, 16, 44);
    camera = new THREE.PerspectiveCamera(55, 16 / 9, 0.1, 120);
    camera.position.set(0, 8.4, 10.8);
    camera.lookAt(0, 0, -9);
    var road = new THREE.Mesh(
      new THREE.PlaneGeometry(WIDTH, 52),
      new THREE.MeshBasicMaterial({ color: 0x12172a }));
    road.rotation.x = -Math.PI / 2; road.position.z = -21;
    scene.add(road);
    [-WIDTH / 2, WIDTH / 2].forEach(function (x) {
      var rail = new THREE.Mesh(new THREE.BoxGeometry(0.18, 0.3, 52),
        new THREE.MeshBasicMaterial({ color: 0xf5a83d }));
      rail.position.set(x, 0.15, -21); scene.add(rail);
    });
    hitMat = new THREE.MeshBasicMaterial({ color: 0xffcf87 });
    var hit = new THREE.Mesh(new THREE.BoxGeometry(WIDTH, 0.22, 0.3), hitMat);
    hit.position.set(0, 0.12, 0); scene.add(hit);
    var lineGeo = new THREE.BoxGeometry(WIDTH, 0.04, 0.07);
    for (var i = 0; i < LOOKAHEAD + 3; i++) {
      var lm = new THREE.Mesh(lineGeo, new THREE.MeshBasicMaterial({
        color: 0x2a3050, transparent: true, opacity: 0.8 }));
      lm.position.y = 0.03; scene.add(lm); linePool.push(lm);
    }
    var geo = new THREE.BoxGeometry(1, 0.42, 1);
    LAYERS.forEach(function (layer, li) {
      var mat = new THREE.MeshBasicMaterial({ color: new THREE.Color(layer.color) });
      var ghost = new THREE.MeshBasicMaterial({ color: new THREE.Color(layer.color),
        transparent: true, opacity: 0.13 });
      layer.notes.forEach(function (n) {
        for (var copy = 0; copy < 2; copy++) {
          var m = new THREE.Mesh(geo, mat);
          m.scale.set(0.62, 1, Math.max(n[2], 0.3) * SPACING * 0.92);
          m.position.x = pitchX(n[1]);
          m.position.y = 0.26 + li * 0.055;
          m.userData = { layer: li, step: n[0] + copy * STEPS, dur: n[2],
                         mat: mat, ghost: ghost, flash: 0, prevDelta: 99 };
          scene.add(m); noteMeshes.push(m);
        }
      });
    });
    return true;
  }
  function sizeGL() {
    if (!useGL) return;
    var w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h; camera.updateProjectionMatrix();
  }
  function drawGL(sf, now) {
    var cyc = Math.floor(sf / STEPS);
    noteMeshes.forEach(function (m) {
      var u = m.userData;
      var delta = u.step - sf;                 // >0: still travelling in
      // leading (camera-side) edge crosses the hit line at delta == 0
      m.position.z = -delta * SPACING - u.dur * SPACING * 0.46;
      var on = layerOn(u.layer, cyc);
      m.material = (!on) ? u.ghost :
        (now < u.flash ? flashMat : u.mat);
      m.visible = delta < LOOKAHEAD && delta > -u.dur - 1.5;
      if (!REDUCED && u.prevDelta > 0 && delta <= 0 && on) u.flash = now + 130;
      u.prevDelta = delta;
    });
    linePool.forEach(function (lm, i) {
      var d = (Math.ceil(sf) + i) - sf;
      lm.position.z = -d * SPACING;
      var stepIdx = Math.ceil(sf) + i;
      lm.material.opacity = (stepIdx % SPB === 0) ? 0.95 : 0.4;
      lm.visible = d < LOOKAHEAD + 2;
    });
    if (!REDUCED && hitMat)
      hitMat.color.setScalar(0).offsetHSL(0.09, 0.75,
        0.55 + 0.13 * Math.max(0, 1 - (sf % 1)) * (playing ? 1 : 0));
    renderer.render(scene, camera);
  }
  var flashMat = null;

  /* 2D fallback (no WebGL / no Three.js): same data, same clock. */
  var ctx2d = null;
  function draw2D(sf) {
    if (!ctx2d) ctx2d = canvas.getContext("2d");
    var w = canvas.width = canvas.clientWidth * (window.devicePixelRatio || 1);
    var h = canvas.height = canvas.clientHeight * (window.devicePixelRatio || 1);
    var horizon = h * 0.16, cyc = Math.floor(sf / STEPS);
    ctx2d.fillStyle = "#0b0e17"; ctx2d.fillRect(0, 0, w, h);
    ctx2d.fillStyle = "#12172a";
    ctx2d.beginPath();
    ctx2d.moveTo(w * 0.30, horizon); ctx2d.lineTo(w * 0.70, horizon);
    ctx2d.lineTo(w * 0.97, h); ctx2d.lineTo(w * 0.03, h); ctx2d.fill();
    function proj(delta, note) {
      var t = 1 - delta / LOOKAHEAD;           // 0 far -> 1 at hit line
      var y = horizon + Math.pow(t, 1.6) * (h * 0.86 - horizon);
      var spread = 0.20 + 0.77 * Math.pow(t, 1.6);
      var x = w / 2 + (pitchX(note) / WIDTH) * w * spread;
      return { x: x, y: y, s: spread };
    }
    LAYERS.forEach(function (layer, li) {
      var on = layerOn(li, cyc);
      ctx2d.globalAlpha = on ? 1 : 0.15;
      ctx2d.fillStyle = layer.color;
      layer.notes.forEach(function (n) {
        for (var copy = 0; copy < 2; copy++) {
          var delta = (n[0] + copy * STEPS) - sf;
          if (delta > LOOKAHEAD || delta < -n[2] - 1) continue;
          var a = proj(Math.max(delta, 0), n[1]);
          var b = proj(delta + Math.max(n[2], 0.3), n[1]);
          var bw = Math.max(2, w * 0.016 * a.s);
          ctx2d.fillRect(a.x - bw / 2, b.y, bw, Math.max(2, a.y - b.y));
        }
      });
    });
    ctx2d.globalAlpha = 1;
    ctx2d.fillStyle = "#ffcf87";
    ctx2d.fillRect(w * 0.03, h * 0.86, w * 0.94, Math.max(2, h * 0.006));
  }

  useGL = initGL();
  if (useGL) {
    flashMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
    sizeGL();
    window.addEventListener("resize", sizeGL);
  } else {
    var note = document.querySelector(".hw-fallback-note");
    if (note) note.hidden = false;
  }
  refreshChips(0);

  var lastCycle = -1;
  function frame() {
    var sf = stepFloat();
    var cyc = Math.floor(sf / STEPS);
    if (cyc !== lastCycle) { lastCycle = cyc; refreshChips(cyc); }
    if (useGL) drawGL(sf, performance.now()); else draw2D(sf);
    if (ctx) {
      var s = ((Math.floor(sf) % STEPS) + STEPS) % STEPS;
      var names = LAYERS.filter(function (l, i) { return layerOn(i, cyc); })
        .map(function (l) { return l.label; }).join(" + ");
      readout.textContent = "Bar " + (Math.floor(s / SPB) + 1) +
        " · Step " + (s + 1) + " / " + STEPS + " · Cycle " + (cyc + 1) +
        " · " + DATA.bpm + " BPM · " + (names || "—");
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  /* verification/debug surface */
  window.__highway = {
    data: DATA,
    state: function () { return { mode: mode, manual: Object.assign({}, manual),
      nextAbs: nextAbs, samplesOk: samplesOk }; },
    playing: function () { return playing; },
    stepFloat: stepFloat,
    scheduled: scheduledLog,
    samplesOk: function () { return samplesOk; },
    noteZ: function (layerId, step, note) {     // world z of nearest copy
      var sf = stepFloat(), best = null;
      noteMeshes.forEach(function (m) {
        var u = m.userData;
        if (LAYERS[u.layer].id === layerId &&
            u.step % STEPS === step &&
            Math.abs(m.position.x - pitchX(note)) < 0.01) {
          var lead = m.position.z + u.dur * SPACING * 0.46;
          if (best === null || Math.abs(lead) < Math.abs(best)) best = lead;
        }
      });
      return best;
    }
  };
})();
