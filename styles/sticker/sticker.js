// Sticker Explainer style kit. Everything is a pure function of time t (seconds):
// no CSS transitions, no timers, no Math.random. window.seek(t) paints frame t.
(function () {
  const K = {};
  K.clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  K.lerp = (a, b, k) => a + (b - a) * k;
  K.easeInOut = (k) => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2);
  K.easeOut = (k) => 1 - Math.pow(1 - k, 3);
  // Closed-form damped spring 0 -> 1 (small overshoot = sticker "pop").
  K.spring = (t, k = 220, d = 18) => {
    if (t <= 0) return 0;
    const w0 = Math.sqrt(k), z = d / (2 * w0);
    if (z >= 1) return 1 - Math.exp(-w0 * t) * (1 + w0 * t);
    const wd = w0 * Math.sqrt(1 - z * z);
    return 1 - Math.exp(-z * w0 * t) * (Math.cos(wd * t) + (z * w0 / wd) * Math.sin(wd * t));
  };
  K.prog = (t, start, dur) => K.clamp((t - start) / dur);

  // Timing helpers from build/timing.js (window.TIMING)
  K.line = (id) => (window.TIMING.lines.find((l) => l.id === id) || { start: 0, end: 0, words: [] });
  K.at = (id, off = 0) => K.line(id).start + off;
  K.word = (id, w, nth = 0) => {
    // time the n-th word in line `id` that starts with `w` is spoken
    const hits = K.line(id).words.filter((x) => x.w.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '').startsWith(w.toLowerCase()));
    return (hits[nth] || hits[0] || { start: K.at(id) }).start;
  };

  // Pop-in for an element: scale spring + fade, optional exit
  K.pop = (el, t, tIn, tOut = Infinity, rot = 0) => {
    const s = K.spring(t - tIn);
    const out = K.clamp((t - tOut) / 0.25);
    const vis = t >= tIn && out < 1;
    el.style.opacity = vis ? (1 - out) * K.clamp((t - tIn) / 0.08) : 0;
    el.style.transform = `translate(-50%,-50%) scale(${(0.4 + 0.6 * s) * (1 - 0.2 * out)}) rotate(${rot}deg)`;
  };

  // Camera: keyframes [{t, x, y, z}] in world coords; eased moves of `dur` seconds into each key.
  K.camera = (world, keys, t, W = 1080, H = 1920, dur = 0.9) => {
    let c = keys[0];
    for (let i = 1; i < keys.length; i++) {
      const k = keys[i];
      if (t < k.t) break;
      const p = K.easeInOut(K.prog(t, k.t, k.dur || dur));
      c = { x: K.lerp(c.x, k.x, p), y: K.lerp(c.y, k.y, p), z: K.lerp(c.z, k.z, p) };
    }
    // gentle drift so holds never feel frozen
    const dz = 1 + 0.012 * Math.sin(t * 0.7);
    // Frame: zoom out a little and aim above centre so everything stays inside the platforms' safe area
    // (clear of TikTok/IG buttons and captions, and inside the 3:4 profile-grid crop). Override per video.
    const fz = window.FRAME_ZOOM ?? 0.88, cy = window.FRAME_CY ?? 960;
    const z = c.z * dz * fz;
    world.style.transform = `translate(${W / 2}px,${cy}px) scale(${z}) translate(${-c.x}px,${-c.y}px)`;
  };

  // Subtitles: current line, yellow highlight on the word being spoken.
  // Word mode (subtitle A/B from 23 Oct, after @mindwander_dot_id): 1-3 words at a time, big, centred, with a pop.
  // Turned on by TIMING.subs === 'word' (set from brand.json schedule "subs") or window.SUB_MODE = 'word'.
  K.chunks = (L) => {
    if (L._chunks) return L._chunks;
    const out = []; let cur = [];
    const push = () => { if (cur.length) out.push({ text: cur.map((x) => x.w).join(' '), start: cur[0].start, end: cur[cur.length - 1].end }); cur = []; };
    L.words.forEach((w) => {
      const len = cur.map((x) => x.w).join(' ').length;
      if (cur.length && (cur.length >= 2 || len + 1 + w.w.length > 12)) push();
      cur.push(w);
      if (/[.,!?;:…]$/.test(w.w)) push();
    });
    push();
    return (L._chunks = out);
  };
  K.subtitlesWord = (box, t) => {
    const lead = window.SUB_LEAD ?? 0.08, tt = t + lead;
    const L = window.TIMING.lines.filter((l) => tt >= l.start - 0.05 && tt <= l.end + 0.3).pop();
    if (!L) { box.style.opacity = 0; return; }
    const cs = K.chunks(L);
    const i = cs.reduce((k, c, j) => (tt >= c.start - 0.03 ? j : k), 0), c = cs[i];
    const key = L.id + ':' + i;
    if (box.dataset.id !== key) { box.dataset.id = key; box.innerHTML = `<b>${c.text}</b>`; }
    const s = K.spring(tt - c.start + 0.03, 420, 22);
    box.style.opacity = 1;
    box.firstChild.style.transform = `scale(${0.82 + 0.18 * s})`;
  };

  K.subtitles = (box, t) => {
    if ((window.SUB_MODE || window.TIMING.subs) === 'word') { box.classList.add('word'); return K.subtitlesWord(box, t); }
    // latest line that has started wins (so a split subtitle page flips on its first word, not 0.35 s later)
    const L = window.TIMING.lines.filter((l) => t >= l.start - 0.05 && t <= l.end + 0.35).pop();
    if (!L) { box.style.opacity = 0; return; }
    if (box.dataset.id !== L.id) {
      box.dataset.id = L.id;
      box.innerHTML = L.words.map((w, i) => `<span data-i="${i}">${w.w}</span>`).join(' ');
    }
    box.style.opacity = 1;
    // Highlight leads the voice slightly: viewers perceive a highlight that lands exactly on the
    // word onset as late (and frames are quantised to 1/30 s). Override per video with window.SUB_LEAD.
    const tt = t + (window.SUB_LEAD ?? 0.08);
    box.querySelectorAll('span').forEach((s) => {
      const w = L.words[+s.dataset.i];
      s.classList.toggle('on', tt >= w.start && tt < w.end + 0.05);
      s.classList.toggle('said', tt >= w.start);
    });
  };

  // Count-up number formatted as Indonesian rupiah
  K.rupiah = (n) => 'Rp' + Math.round(n).toLocaleString('id-ID');

  // One shared SVG filter for illustration stickers: dilate alpha -> white outline, plus soft shadow.
  K.installFilters = () => {
    if (document.getElementById('stk')) return;
    const d = document.createElement('div');
    d.innerHTML = `<svg width="0" height="0" style="position:absolute"><defs>
      <filter id="stk" x="-20%" y="-20%" width="140%" height="140%">
        <feMorphology in="SourceAlpha" operator="dilate" radius="8" result="d"/>
        <feFlood flood-color="#fff"/><feComposite in2="d" operator="in" result="o"/>
        <feGaussianBlur in="d" stdDeviation="10" result="b"/><feOffset in="b" dy="14" result="bo"/>
        <feFlood flood-color="#1B2430" flood-opacity=".22"/><feComposite in2="bo" operator="in" result="sh"/>
        <feMerge><feMergeNode in="sh"/><feMergeNode in="o"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter></defs></svg>`;
    document.body.appendChild(d.firstChild);
  };
  document.addEventListener('DOMContentLoaded', K.installFilters);
  window.K = K;
})();
