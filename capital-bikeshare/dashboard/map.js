(() => {
  // ---------- calculations ----------
  dash.calc('map_hour_totals', {
    inputs: ['map_station_hour'],
    title: 'Trips by hour, working days',
    description: 'Trips started in each hour on an average working day, across all mapped stations.',
    fn: (map_station_hour) => {
      const h = {};
      map_station_hour.forEach((r) => { h[r.hr] = (h[r.hr] || 0) + r.starts; });
      return Object.keys(h).map(Number).sort((a, b) => a - b).map((hr) => ({ hr, trips: Math.round(h[hr]) }));
    },
  });

  dash.calc('map_month_totals', {
    inputs: ['map_station_month', 'map_stations'],
    title: 'Trips and stations by month',
    description: 'Trips started each month, and how many stations had opened by then.',
    fn: (map_station_month, map_stations) => {
      const m = {};
      map_station_month.forEach((r) => { m[r.ym] = (m[r.ym] || 0) + r.starts; });
      return Object.keys(m).sort().map((ym) => ({
        ym, trips: m[ym], stations_open: map_stations.filter((s) => s.first_month <= ym).length,
      }));
    },
  });

  dash.calc('map_downtown', {
    inputs: ['map_station_hour', 'map_stations'],
    title: 'Downtown trips by hour',
    description: 'On an average working day, trips that start or end at stations in downtown D.C. (latitude 38.893–38.906, longitude −77.045 to −77.018, roughly Foggy Bottom to Penn Quarter).',
    fn: (map_station_hour, map_stations) => {
      const core = new Set(map_stations.filter((s) => s.lat >= 38.893 && s.lat <= 38.906 && s.lon >= -77.045 && s.lon <= -77.018).map((s) => s.num));
      const h = {};
      map_station_hour.forEach((r) => {
        const o = (h[r.hr] = h[r.hr] || { hr: r.hr, start_downtown: 0, end_downtown: 0 });
        if (core.has(r.num)) { o.start_downtown += r.starts; o.end_downtown += r.ends; }
      });
      return Object.values(h).sort((a, b) => a.hr - b.hr)
        .map((o) => ({ hr: o.hr, start_downtown: Math.round(o.start_downtown), end_downtown: Math.round(o.end_downtown) }));
    },
  });

  dash.calc('map_top_stations', {
    inputs: ['map_stations'],
    title: 'Busiest stations',
    description: 'The ten stations where the most trips started in 2011–2012.',
    fn: (map_stations) => [...map_stations].sort((a, b) => b.starts - a.starts).slice(0, 10)
      .map((s) => ({ station: s.name, starts: s.starts, ends: s.ends, member_share: s.member_share })),
  });

  dash.calc('map_top_routes', {
    inputs: ['map_routes', 'map_stations'],
    title: 'Busiest routes',
    description: 'The ten station-to-station routes with the most trips in 2011–2012 (round trips to the same station left out).',
    fn: (map_routes, map_stations) => {
      const name = {};
      map_stations.forEach((s) => { name[s.num] = s.name; });
      return [...map_routes].sort((a, b) => b.trips - a.trips).slice(0, 10)
        .map((r) => ({ route: name[r.from] + ' → ' + name[r.to], trips: r.trips, member_share: r.member_share }));
    },
  });

  dash.calc('map_coverage', {
    inputs: ['map_summary'],
    title: 'Trips placed on the map',
    description: 'Share of trips in the public trip files whose start and end stations could be placed on the map.',
    fn: (map_summary) => [{ share: map_summary[0].trips_mapped / map_summary[0].trips_total, left_out: map_summary[0].trips_total - map_summary[0].trips_mapped }],
  });

  // ---------- helpers ----------
  const fmt = d3.format(',');
  const pct = d3.format('.1%');
  const compact = new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 2 });
  const monFmt = d3.utcFormat('%B %Y');
  const parseM = d3.utcParse('%Y-%m');
  const hrLab = (h) => (h === 0 ? '12am' : h < 12 ? h + 'am' : h === 12 ? '12pm' : (h - 12) + 'pm');
  const hrLong = (h) => hrLab(h) + '–' + hrLab((h + 1) % 24);
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const DATA = ['map_stations', 'map_station_hour', 'map_station_month', 'map_route_hour', 'map_route_month', 'map_routes', 'map_summary'];
  const STEP = { hour: 1700, month: 1400 };
  const HOLD = { hour: 2400, month: 2200 };
  const DOTS_AT_PEAK = 170;

  let page = null; let $ = null;
  const M = { mode: 'hour', idx: 0, playing: false, acc: 0, lastT: 0, dots: [], queue: [], built: false, W: 0, H: 0, lastW: 0 };

  function tipFor(box) {
    let t = box.querySelector('.bk-tip');
    if (!t) { t = document.createElement('div'); t.className = 'bk-tip'; box.appendChild(t); }
    return {
      show(evt, head, rows) {
        t.replaceChildren();
        const h = document.createElement('div'); h.className = 'bk-tip-h'; h.textContent = head; t.appendChild(h);
        rows.forEach((r) => { const d = document.createElement('div'); d.className = 'bk-tip-row'; d.textContent = r; t.appendChild(d); });
        t.style.display = 'block';
        const b = box.getBoundingClientRect();
        let x = evt.clientX - b.left + 12, y = evt.clientY - b.top - 10;
        if (x + t.offsetWidth > b.width) x = evt.clientX - b.left - t.offsetWidth - 12;
        t.style.left = Math.max(0, x) + 'px'; t.style.top = Math.max(0, Math.min(y, b.height - t.offsetHeight)) + 'px';
      },
      hide() { t.style.display = 'none'; },
    };
  }

  // ---------- data shaped for drawing ----------
  let D = null;
  function prepare() {
    const get = (id) => dash.data(id);
    if (DATA.some((id) => get(id).status !== 'ok')) return null;
    const stations = get('map_stations').data;
    const byNum = new Map(stations.map((s) => [s.num, s]));
    const group = (rows, key) => { const m = new Map(); rows.forEach((r) => { const k = r[key]; if (!m.has(k)) m.set(k, []); m.get(k).push(r); }); return m; };
    return {
      stations, byNum,
      stHour: group(get('map_station_hour').data, 'hr'),
      stMonth: group(get('map_station_month').data, 'ym'),
      rtHour: group(get('map_route_hour').data, 'hr'),
      rtMonth: group(get('map_route_month').data, 'ym'),
      routes: get('map_routes').data,
    };
  }

  function frames() {
    if (M.mode === 'hour') {
      const t = dash.data('map_hour_totals'); const dt = dash.data('map_downtown');
      if (t.status !== 'ok' || dt.status !== 'ok') return null;
      return t.data.map((r) => ({ key: r.hr, src: 'map_hour_totals', where: 'hr=' + r.hr, field: 'trips', n: r.trips, when: hrLong(r.hr), dt: dt.data.find((d) => d.hr === r.hr) }));
    }
    const t = dash.data('map_month_totals');
    if (t.status !== 'ok') return null;
    return t.data.map((r) => ({ key: r.ym, src: 'map_month_totals', where: 'ym=' + r.ym, field: 'trips', n: r.trips, open: r.stations_open, when: monFmt(parseM(r.ym)) }));
  }

  // ---------- the map ----------
  let svg, zg, gRoutes, gLinks, gGlow, gSt, gDots, gHit, gLab, proj, stSel, glowSel, hitSel, zoom;
  const Z = { k: 1, t: d3.zoomIdentity };
  const P = (s) => [s.x + (s.ox || 0), s.y + (s.oy || 0)];
  const R = { st: 2.6, hit: 8, dot: 2.4 };

  function build() {
    const box = $('.bk-m-map');
    const W = Math.max(300, box.clientWidth);
    const H = Math.round(Math.max(380, Math.min(640, W * 0.78)));
    M.W = W; M.H = H;
    box.replaceChildren();
    const lat0 = d3.mean(D.stations, (s) => s.lat) * Math.PI / 180;
    const kx = Math.cos(lat0);
    const xs = D.stations.map((s) => s.lon * kx), ys = D.stations.map((s) => -s.lat);
    const [x0, x1] = d3.extent(xs), [y0, y1] = d3.extent(ys);
    const pad = 28;
    const k = Math.min((W - 2 * pad) / (x1 - x0), (H - 2 * pad) / (y1 - y0));
    const ox = (W - k * (x1 - x0)) / 2, oy = (H - k * (y1 - y0)) / 2;
    proj = (s) => [ox + (s.lon * kx - x0) * k, oy + (-s.lat - y0) * k];
    D.stations.forEach((s) => { [s.x, s.y] = proj(s); s.ox = 0; s.oy = 0; });
    svg = d3.select(box).append('svg').attr('width', '100%').attr('height', H).attr('viewBox', `0 0 ${W} ${H}`)
      .attr('role', 'img').attr('aria-label', 'Interactive map of bike share stations: click a station for details, drag it to stretch its connections')
      .style('touch-action', 'none').style('cursor', 'grab');
    svg.append('rect').attr('width', W).attr('height', H).attr('fill', 'transparent');
    zg = svg.append('g');
    gRoutes = zg.append('g');
    const topR = [...D.routes].sort((a, b) => b.trips - a.trips).slice(0, 60);
    gRoutes.selectAll('path').data(topR).join('path').attr('fill', 'none').attr('stroke', 'var(--color-fg)')
      .attr('stroke-opacity', 0.08).attr('stroke-width', 1).attr('vector-effect', 'non-scaling-stroke')
      .attr('d', (r) => arc(D.byNum.get(r.from), D.byNum.get(r.to)));
    gLinks = zg.append('g').attr('pointer-events', 'none');
    gGlow = zg.append('g').attr('pointer-events', 'none');
    glowSel = gGlow.selectAll('circle').data(D.stations, (s) => s.num).join('circle')
      .attr('cx', (s) => s.x).attr('cy', (s) => s.y).attr('r', 0).attr('fill', dash.colors[0]).attr('fill-opacity', 0.32);
    gSt = zg.append('g').attr('pointer-events', 'none');
    stSel = gSt.selectAll('circle').data(D.stations, (s) => s.num).join('circle')
      .attr('cx', (s) => s.x).attr('cy', (s) => s.y).attr('r', R.st)
      .attr('fill', (s) => (s.approx ? 'var(--color-panel)' : 'var(--color-fg)'))
      .attr('stroke', (s) => (s.approx ? 'var(--color-fg)' : 'none')).attr('stroke-width', 1.2)
      .attr('vector-effect', 'non-scaling-stroke').attr('stroke-dasharray', (s) => (s.approx ? '1.5 1.5' : null));
    gDots = zg.append('g').attr('pointer-events', 'none');
    gHit = zg.append('g');
    gLab = svg.append('g').attr('pointer-events', 'none');
    // scale bar: 1 km (drawn for the unzoomed map)
    M.kmPx = k / 111.32;
    M.sb = svg.append('g').attr('transform', `translate(${pad},${H - 14})`).attr('pointer-events', 'none');
    M.sbLine = M.sb.append('line').attr('stroke', 'var(--color-fg-muted)').attr('stroke-width', 2);
    M.sbText = M.sb.append('text').attr('dy', '0.35em').attr('class', 'bk-ann-m').text('1 km');

    const tip = tipFor(box);
    M.tip = tip;
    hitSel = gHit.selectAll('circle').data(D.stations, (s) => s.num).join('circle')
      .attr('cx', (s) => s.x).attr('cy', (s) => s.y).attr('r', R.hit).attr('fill', 'transparent').style('cursor', 'pointer')
      .attr('tabindex', 0).attr('role', 'button').attr('aria-label', (s) => s.name)
      .on('mousemove', (e, s) => { if (!M.dragging) tip.show(e, s.name, [
        fmt(Math.round(s.cur || 0)) + ' trips started ' + (M.frameLabel || ''),
        fmt(s.starts) + ' started, ' + fmt(s.ends) + ' ended over 2011–2012',
        'Click for details · drag the bubble to pull it out',
      ].concat(s.approx ? ['Position approximate: station has since closed'] : [])); })
      .on('mouseleave', () => tip.hide())
      .on('keydown', (e, s) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(M.sel === s.num ? null : s.num); } })
      .call(d3.drag().container(() => zg.node())
        .subject((e, s) => { const [x, y] = P(s); return { x, y }; })
        .on('start', (e, s) => { M.dragging = s; M.moved = false; tip.hide(); if (s.spring) { s.spring.stop(); s.spring = null; } })
        .on('drag', (e, s) => {
          if (!M.moved && Math.hypot(e.x - P(s)[0], e.y - P(s)[1]) < 3 / Z.k) return;
          if (!M.moved) { M.moved = true; if (M.sel !== s.num) select(s.num); svg.style('cursor', 'grabbing'); }
          s.ox = e.x - s.x; s.oy = e.y - s.y; place(s);
        })
        .on('end', (e, s) => {
          M.dragging = null; svg.style('cursor', 'grab');
          if (!M.moved) { select(M.sel === s.num ? null : s.num); return; }
          const fx = s.ox, fy = s.oy, T = reduced ? 1 : 1100;
          const ease = d3.easeElasticOut.amplitude(1).period(0.35);
          s.spring = d3.timer((el) => {
            const u = Math.min(1, el / T), v = ease(u);
            s.ox = fx * (1 - v); s.oy = fy * (1 - v); place(s);
            if (u >= 1 && s.spring) { s.spring.stop(); s.spring = null; }
          });
        }));

    zoom = d3.zoom().scaleExtent([1, 10]).translateExtent([[-W * 0.2, -H * 0.2], [W * 1.2, H * 1.2]])
      .filter((e) => (e.type === 'wheel' ? e.ctrlKey || e.metaKey : !e.button))
      .on('zoom', (e) => { Z.t = e.transform; Z.k = e.transform.k; zg.attr('transform', e.transform); rescale(); });
    svg.call(zoom).on('dblclick.zoom', null);
    svg.on('click', (e) => { if (e.target === svg.node().firstChild) select(null); });
    M.dots.forEach((d) => d.el.remove());
    M.dots = []; M.queue = [];
    M.built = true;
    rescale();
    if (M.sel != null) select(M.sel, true);
  }

  // keep marks the same size on screen while zoomed
  function rescale() {
    const k = Z.k;
    stSel.attr('r', (s) => (s.big ? 4.5 : R.st) / k);
    hitSel.attr('r', (s) => Math.max(R.hit / k, (s.gr || 0) / Math.sqrt(k)));
    glowSel.attr('r', (s) => (s.gr || 0) / Math.sqrt(k));
    gDots.selectAll('circle').attr('r', R.dot / k);
    M.sbLine.attr('x2', M.kmPx * k); M.sbText.attr('x', M.kmPx * k + 6);
    labels();
  }

  function labels() {
    gLab.selectAll('*').remove();
    const pick = [...D.stations].sort((a, b) => b.starts - a.starts).slice(0, Z.k > 2.5 ? 12 : 4);
    if (M.sel != null && !pick.some((s) => s.num === M.sel)) pick.push(D.byNum.get(M.sel));
    const placed = [];
    pick.forEach((s) => {
      const [sx, sy] = Z.t.apply(P(s));
      if (sx < 0 || sy < 0 || sx > M.W || sy > M.H) return;
      const sel = s.num === M.sel;
      const t = gLab.append('text').attr('class', sel ? 'bk-ann bk-ann-sel' : 'bk-ann').text(s.name.split(' / ')[0])
        .style('paint-order', 'stroke').style('stroke', 'var(--color-panel)').style('stroke-width', 3);
      const w = t.node().getComputedTextLength();
      let x = sx + 9, y = sy + 4;
      if (x + w > M.W - 4) x = sx - 9 - w;
      while (placed.some((q) => Math.abs(q.y - y) < 14 && x < q.x + q.w && x + w > q.x)) y += 14;
      placed.push({ x, y, w }); t.attr('x', x).attr('y', y);
    });
  }

  // move one station (and anything tied to it) to its current position
  function place(s) {
    const [x, y] = P(s);
    stSel.filter((d) => d === s).attr('cx', x).attr('cy', y);
    glowSel.filter((d) => d === s).attr('cx', x).attr('cy', y);
    hitSel.filter((d) => d === s).attr('cx', x).attr('cy', y);
    gRoutes.selectAll('path').filter((r) => r.from === s.num || r.to === s.num).attr('d', (r) => arc(D.byNum.get(r.from), D.byNum.get(r.to)));
    gLinks.selectAll('path').attr('d', (l) => arc(D.byNum.get(l.from), D.byNum.get(l.to)));
    labels();
  }

  function arc(a, b) {
    const [ax, ay] = P(a), [bx, by] = P(b);
    const mx = (ax + bx) / 2, my = (ay + by) / 2;
    const cx = mx - (by - ay) * 0.18, cy = my + (bx - ax) * 0.18;
    return `M${ax},${ay} Q${cx},${cy} ${bx},${by}`;
  }

  // ---------- selecting a station ----------
  const LINKS = ['map_station_links', 'map_link_hour', 'map_link_month'];
  function linkData() {
    if (LINKS.some((id) => dash.data(id).status !== 'ok')) return null;
    if (!D.links) {
      const g = (rows, key) => { const m = new Map(); rows.forEach((r) => { const k = r[key]; if (!m.has(k)) m.set(k, []); m.get(k).push(r); }); return m; };
      D.links = g(dash.data('map_station_links').data, 'num');
      const both = (rows) => { const m = new Map(); rows.forEach((r) => { [r.from, r.to].forEach((n) => { if (!m.has(n)) m.set(n, []); m.get(n).push(r); }); }); return m; };
      D.lHour = both(dash.data('map_link_hour').data);
      D.lMonth = both(dash.data('map_link_month').data);
    }
    return D;
  }

  function select(num, silent) {
    M.sel = num;
    const panel = $('.bk-m-panel');
    const find = $('.bk-m-find');
    find.value = num == null ? '' : String(num);
    if (num == null) {
      panel.classList.remove('on'); panel.setAttribute('aria-hidden', 'true');
      gLinks.selectAll('*').remove();
      stSel.attr('opacity', null); gRoutes.attr('opacity', 1);
      labels(); if (!silent) show();
      return;
    }
    panel.classList.add('on'); panel.removeAttribute('aria-hidden');
    renderPanel();
    if (!silent) show();
  }

  function drawLinks() {
    gLinks.selectAll('*').remove();
    if (M.sel == null) return;
    const L = linkData(); if (!L) return;
    const rows = (L.links.get(M.sel) || []).map((r) => (r.dir === 'out' ? { from: M.sel, to: r.other, trips: r.trips, dir: 'out' } : { from: r.other, to: M.sel, trips: r.trips, dir: 'in' }));
    const tmax = d3.max(rows, (r) => r.trips) || 1;
    gLinks.selectAll('path').data(rows).join('path').attr('fill', 'none')
      .attr('stroke', (l) => (l.dir === 'out' ? dash.colors[1] : dash.colors[0])).attr('stroke-opacity', 0.75)
      .attr('stroke-width', (l) => 1 + (l.trips / tmax) * 4).attr('vector-effect', 'non-scaling-stroke')
      .attr('stroke-dasharray', (l) => (l.dir === 'in' ? '5 4' : null)).attr('stroke-linecap', 'round')
      .attr('d', (l) => arc(D.byNum.get(l.from), D.byNum.get(l.to)));
    const near = new Set([M.sel, ...rows.map((r) => r.from), ...rows.map((r) => r.to)]);
    stSel.attr('opacity', (s) => (near.has(s.num) ? 1 : 0.25));
    gRoutes.attr('opacity', 0.3);
  }

  function renderPanel() {
    const s = D.byNum.get(M.sel); if (!s) return;
    const pn = $('.bk-m-panel');
    const where = 'num=' + s.num;
    const setMark = (el, src, field, w, txt) => { el.textContent = txt; el.dataset.source = src; el.dataset.field = field; el.dataset.where = w; };
    setMark(pn.querySelector('.bk-p-name'), 'map_stations', 'name', where, s.name);
    pn.querySelector('.bk-p-sub').textContent = 'First trip ' + monFmt(parseM(s.first_month)) + (s.approx ? ' · closed since; position approximate' : '');
    setMark(pn.querySelector('.bk-p-starts'), 'map_stations', 'starts', where, fmt(s.starts));
    setMark(pn.querySelector('.bk-p-ends'), 'map_stations', 'ends', where, fmt(s.ends));
    setMark(pn.querySelector('.bk-p-mem'), 'map_stations', 'member_share', where, pct(s.member_share));
    // hourly pattern on working days
    const hb = pn.querySelector('.bk-p-hour'); hb.replaceChildren();
    const hrs = d3.range(24).map((h) => (D.stHour.get(h) || []).find((r) => r.num === s.num) || { hr: h, starts: 0, ends: 0 });
    {
      const W = Math.max(220, hb.clientWidth || 280), H = 110, l = 4, b = 18;
      const svgH = d3.select(hb).append('svg').attr('width', '100%').attr('height', H).attr('viewBox', `0 0 ${W} ${H}`);
      const x = d3.scaleLinear([0, 23], [l, W - 4]);
      const y = d3.scaleLinear([0, d3.max(hrs, (r) => Math.max(r.starts, r.ends)) || 1], [H - b, 6]);
      [['starts', dash.colors[1], null], ['ends', dash.colors[0], '4 3']].forEach(([f, c, dashA]) => svgH.append('path').datum(hrs)
        .attr('fill', 'none').attr('stroke', c).attr('stroke-width', 2).attr('stroke-linejoin', 'round').attr('stroke-linecap', 'round').attr('stroke-dasharray', dashA)
        .attr('d', d3.line().x((r, i) => x(i)).y((r) => y(r[f]))));
      [0, 6, 12, 18, 23].forEach((h) => svgH.append('text').attr('class', 'bk-ann-m').attr('x', x(h)).attr('y', H - 4)
        .attr('text-anchor', h === 0 ? 'start' : h === 23 ? 'end' : 'middle').text(hrLab(h)));
      const cur = M.mode === 'hour' ? M.idx : null;
      if (cur != null) svgH.append('line').attr('x1', x(cur)).attr('x2', x(cur)).attr('y1', 4).attr('y2', H - b).attr('stroke', 'var(--cds-chart-reference)').attr('stroke-dasharray', '2 3');
    }
    // monthly starts
    const mb = pn.querySelector('.bk-p-month'); mb.replaceChildren();
    {
      const months = [...D.stMonth.keys()].sort();
      const vals = months.map((ym) => ({ ym, v: ((D.stMonth.get(ym) || []).find((r) => r.num === s.num) || { starts: 0 }).starts }));
      const W = Math.max(220, mb.clientWidth || 280), H = 64;
      const svgM = d3.select(mb).append('svg').attr('width', '100%').attr('height', H).attr('viewBox', `0 0 ${W} ${H}`);
      const x = d3.scaleBand(months, [0, W]).padding(0.2);
      const y = d3.scaleLinear([0, d3.max(vals, (d) => d.v) || 1], [H - 14, 2]);
      svgM.selectAll('rect').data(vals).join('rect').attr('x', (d) => x(d.ym)).attr('width', x.bandwidth())
        .attr('y', (d) => y(d.v)).attr('height', (d) => H - 14 - y(d.v)).attr('rx', 2)
        .attr('fill', (d) => (M.mode === 'month' && months[M.idx] === d.ym ? 'var(--color-fg)' : dash.colors[0]));
      svgM.append('text').attr('class', 'bk-ann-m').attr('x', 0).attr('y', H - 2).text('Jan 2011');
      svgM.append('text').attr('class', 'bk-ann-m').attr('x', W).attr('y', H - 2).attr('text-anchor', 'end').text('Dec 2012');
    }
    // where riders go and come from
    const L = linkData();
    ['out', 'in'].forEach((dir) => {
      const ul = pn.querySelector(dir === 'out' ? '.bk-p-out' : '.bk-p-in'); ul.replaceChildren();
      if (!L) { const li = document.createElement('li'); li.className = 'dash-skeleton'; li.textContent = '—'; ul.appendChild(li); return; }
      (L.links.get(s.num) || []).filter((r) => r.dir === dir).sort((a, b) => a.rank - b.rank).forEach((r) => {
        const o = D.byNum.get(r.other); if (!o) return;
        const li = document.createElement('li');
        const btn = document.createElement('button'); btn.type = 'button'; btn.className = 'bk-p-link'; btn.textContent = o.name.split(' / ')[0];
        btn.addEventListener('click', () => { select(o.num); focusOn(o); });
        const n = document.createElement('span'); n.className = 'bk-p-n';
        setMark(n, 'map_station_links', 'trips', `num=${s.num}&dir=${dir}&rank=${r.rank}`, fmt(r.trips));
        li.append(btn, n); ul.appendChild(li);
      });
    });
    drawLinks(); labels();
  }

  function focusOn(s) {
    const [x, y] = P(s); const k = Math.max(Z.k, 3);
    svg.transition().duration(reduced ? 0 : 700).call(zoom.transform, d3.zoomIdentity.translate(M.W / 2 - x * k, M.H / 2 - y * k).scale(k));
  }

  // ---------- frame drawing ----------
  function show() {
    const F = frames(); if (!F || !M.built) return;
    if (M.idx >= F.length) M.idx = 0;
    const f = F[M.idx];
    const range = $('.bk-m-range'); range.max = String(F.length - 1); range.value = String(M.idx);
    $('.bk-m-when').textContent = f.when;
    const n = $('.bk-m-n'); n.classList.remove('dash-skeleton'); n.textContent = fmt(f.n);
    n.dataset.source = f.src; n.dataset.field = f.field; n.dataset.where = f.where;
    $('.bk-m-l').textContent = M.mode === 'hour' ? 'trips started in this hour on an average working day' : 'trips started this month';
    const st = $('.bk-m-st');
    st.replaceChildren();
    if (M.mode === 'month') {
      const b = document.createElement('b'); b.textContent = fmt(f.open);
      b.dataset.source = 'map_month_totals'; b.dataset.field = 'stations_open'; b.dataset.where = f.where;
      st.append(b, document.createTextNode(' stations open'));
    } else st.textContent = 'Glow = trips starting at each station · dots = riders on the busiest routes';

    // station glow and visibility
    const act = new Map();
    const rows = M.mode === 'hour' ? D.stHour.get(f.key) || [] : D.stMonth.get(f.key) || [];
    rows.forEach((r) => act.set(r.num, r.starts));
    const vmax = M.mode === 'hour' ? M.vmaxH : M.vmaxM;
    const open = (s) => M.mode === 'hour' || s.first_month <= f.key;
    D.stations.forEach((st) => {
      st.cur = act.get(st.num) || 0;
      st.gr = open(st) ? Math.sqrt(st.cur / vmax) * 16 : 0;
      st.big = M.mode === 'month' && st.first_month === f.key;
      st.isOpen = open(st);
    });
    const k = Z.k;
    glowSel.transition().duration(reduced ? 0 : 450).attr('r', (st) => st.gr / Math.sqrt(k))
      .attr('fill-opacity', (st) => (M.sel == null || st.num === M.sel ? 0.32 : 0.12));
    stSel.transition().duration(reduced ? 0 : 450).attr('r', (st) => (st.big ? 4.5 : R.st) / k);
    if (M.sel == null) stSel.attr('opacity', (st) => (st.isOpen ? 1 : 0.06));
    // the bubble is the handle: grab area grows with it
    hitSel.attr('r', (st) => Math.max(R.hit / k, st.gr / Math.sqrt(k))).attr('pointer-events', (st) => (st.isOpen ? null : 'none'));
    M.frameLabel = M.mode === 'hour' ? 'in ' + f.when + ' on an average working day' : 'in ' + f.when;

    // riders for this frame
    let rt, scale;
    const L = M.sel != null ? linkData() : null;
    if (L) {
      const all = M.mode === 'hour' ? L.lHour.get(M.sel) || [] : L.lMonth.get(M.sel) || [];
      const fk = M.mode === 'hour' ? 'hr' : 'ym';
      rt = all.filter((r) => r[fk] === f.key);
      const per = d3.rollup(all, (v) => d3.sum(v, (r) => r.trips), (r) => r[fk]);
      scale = 70 / (d3.max([...per.values()]) || 1);
    } else {
      rt = M.mode === 'hour' ? D.rtHour.get(f.key) || [] : D.rtMonth.get(f.key) || [];
      scale = DOTS_AT_PEAK / (M.mode === 'hour' ? M.peakH : M.peakM);
    }
    const dur = STEP[M.mode] + (annotation(F, M.idx) ? HOLD[M.mode] : 0);
    const now = performance.now();
    M.queue = [];
    rt.forEach((r) => {
      let k = r.trips * scale; let c = Math.floor(k) + (Math.random() < k - Math.floor(k) ? 1 : 0);
      while (c-- > 0) M.queue.push({ at: now + Math.random() * dur, from: r.from, to: r.to });
    });
    M.queue.sort((a, b) => a.at - b.at);

    // caption
    const ann = M.sel == null ? annotation(F, M.idx) : null; M.annHere = !!ann;
    const cap = $('.bk-m-cap');
    if (ann) {
      cap.querySelector('.bk-cap-t').textContent = ann.title;
      const body = cap.querySelector('.bk-cap-b'); body.replaceChildren();
      ann.parts.forEach((p) => {
        if (typeof p === 'string') return body.appendChild(document.createTextNode(p));
        const b = document.createElement('b'); b.textContent = p.kind === 'pct' ? pct(p.v) : fmt(p.v);
        b.dataset.source = p.src; b.dataset.field = p.field; if (p.where) b.dataset.where = p.where; else b.dataset.row = '0';
        body.appendChild(b);
      });
      cap.classList.add('on');
    } else cap.classList.remove('on');
    if (M.sel != null) { renderPanel(); const o = D.byNum.get(M.sel); st.textContent = 'Showing riders to and from ' + o.name.split(' / ')[0] + ' · press Esc or click empty map to clear'; }
    drawTimeline(F);
  }

  const p = (v, src, field, where, kind) => ({ v, src, field, where, kind });
  function annotation(F, i) {
    const f = F[i];
    if (M.mode === 'hour') {
      if (f.key === 8 && f.dt) return { title: 'Morning rush: everyone heads downtown', parts: [p(f.dt.end_downtown, 'map_downtown', 'end_downtown', 'hr=8'), ' trips end downtown in this hour, but only ', p(f.dt.start_downtown, 'map_downtown', 'start_downtown', 'hr=8'), ' start there.'] };
      if (f.key === 17 && f.dt) return { title: 'Evening rush: the flow reverses', parts: [p(f.dt.start_downtown, 'map_downtown', 'start_downtown', 'hr=17'), ' trips leave downtown in this hour, and ', p(f.dt.end_downtown, 'map_downtown', 'end_downtown', 'hr=17'), ' arrive.'] };
      if (f.key === 3) return { title: 'The quietest hour', parts: ['Just ', p(f.n, f.src, 'trips', f.where), ' trips on an average working day.'] };
      return null;
    }
    const last = F[F.length - 1];
    if (i === 0) return { title: 'The network in January 2011', parts: [p(f.open, 'map_month_totals', 'stations_open', f.where), ' stations, mostly in central D.C. and Arlington.'] };
    if (f.key === '2011-12') return { title: 'A winter of new stations', parts: ['Up to ', p(f.open, 'map_month_totals', 'stations_open', f.where), ' stations by December 2011. Bigger dots are stations opening this month.'] };
    if (i === F.length - 1) return { title: 'The network at the end of 2012', parts: [p(last.open, 'map_month_totals', 'stations_open', last.where), ' stations, with ', p(last.n, 'map_month_totals', 'trips', last.where), ' trips this month.'] };
    return null;
  }

  function drawTimeline(F) {
    const box = $('.bk-m-tl');
    const W = Math.max(280, box.clientWidth); const H = 54;
    let s = d3.select(box).select('svg');
    if (s.empty() || +s.attr('data-w') !== W || s.attr('data-mode') !== M.mode) {
      box.replaceChildren(); box.dataset.source = F[0].src;
      s = d3.select(box).append('svg').attr('width', '100%').attr('height', H).attr('viewBox', `0 0 ${W} ${H}`).attr('data-w', W).attr('data-mode', M.mode);
      const x = d3.scaleBand(d3.range(F.length), [0, W]).paddingInner(0.15);
      const y = d3.scaleLinear([0, d3.max(F, (d) => d.n)], [H, 12]);
      s.selectAll('rect.b').data(F).join('rect').attr('class', 'b').attr('x', (d, i) => x(i)).attr('width', x.bandwidth())
        .attr('y', (d) => y(d.n)).attr('height', (d) => H - y(d.n)).attr('rx', 2).attr('fill', dash.colors[0]).attr('fill-opacity', 0.5);
      F.forEach((f, i) => { if (annotation(F, i)) s.append('circle').attr('cx', x(i) + x.bandwidth() / 2).attr('cy', 5).attr('r', 3.5).attr('fill', 'var(--color-fg)'); });
      s.append('rect').attr('class', 'cur').attr('y', 0).attr('height', H).attr('fill', 'var(--color-fg)').attr('fill-opacity', 0.9).attr('width', 3);
      s.on('click', (e) => { const [mx] = d3.pointer(e); M.idx = Math.max(0, Math.min(F.length - 1, Math.floor((mx / W) * F.length))); M.acc = 0; show(); });
      $('.bk-m-a').textContent = F[0].when; $('.bk-m-b').textContent = F[F.length - 1].when;
    }
    const bw = W / F.length;
    s.select('.cur').attr('x', M.idx * bw + bw / 2 - 1.5);
  }

  function tick(t) {
    const dt = M.lastT ? Math.min(0.05, (t - M.lastT) / 1000) : 0; M.lastT = t;
    if (M.built && page && !page.hidden) {
      if (M.playing) {
        M.acc += dt * 1000;
        if (M.acc >= STEP[M.mode] + (M.annHere ? HOLD[M.mode] : 0)) { M.acc = 0; const F = frames(); if (F) { M.idx = (M.idx + 1) % F.length; show(); } }
      }
      if (!reduced || M.playing) {
        while (M.queue.length && M.queue[0].at <= t) {
          const q = M.queue.shift(); const a = D.byNum.get(q.from), b = D.byNum.get(q.to);
          if (!a || !b) continue;
          const len = Math.hypot(b.x - a.x, b.y - a.y);
          const el = gDots.append('circle').attr('r', R.dot / Z.k).attr('fill', M.sel != null && q.to === M.sel ? dash.colors[0] : dash.colors[1]).attr('fill-opacity', 0.9);
          M.dots.push({ el, a, b, t0: t, life: 700 + len * 9 });
        }
        M.dots = M.dots.filter((d) => {
          const u = (t - d.t0) / d.life;
          if (u >= 1) { d.el.remove(); return false; }
          const [ax, ay] = P(d.a), [bx, by] = P(d.b);
          const mx = (ax + bx) / 2 - (by - ay) * 0.18, my = (ay + by) / 2 + (bx - ax) * 0.18;
          const x = (1 - u) * (1 - u) * ax + 2 * (1 - u) * u * mx + u * u * bx;
          const y = (1 - u) * (1 - u) * ay + 2 * (1 - u) * u * my + u * u * by;
          d.el.attr('cx', x).attr('cy', y).attr('fill-opacity', u > 0.85 ? (1 - u) * 6 : 0.9);
          return true;
        });
      }
    }
    requestAnimationFrame(tick);
  }

  function fillTables() {
    const fill = (sel, id, cols) => {
      const tb = $(sel + ' tbody'); const r = dash.data(id);
      tb.replaceChildren();
      if (r.status !== 'ok') return;
      r.data.forEach((row) => {
        const tr = document.createElement('tr');
        cols.forEach(([f, fm]) => { const td = document.createElement('td'); td.textContent = fm ? fm(row[f]) : row[f]; tr.appendChild(td); });
        tb.appendChild(tr);
      });
    };
    fill('.bk-t-st', 'map_top_stations', [['station'], ['starts', fmt], ['ends', fmt], ['member_share', pct]]);
    fill('.bk-t-rt', 'map_top_routes', [['route'], ['trips', fmt], ['member_share', pct]]);
    const kpi = (sel, id, f, fm) => { const el = $(sel); const r = dash.data(id); if (r.status === 'ok') { el.classList.remove('dash-skeleton'); el.textContent = fm(r.data[0][f]); } };
    kpi('.bk-mk-trips', 'map_summary', 'trips_mapped', (v) => compact.format(v));
    kpi('.bk-mk-share', 'map_coverage', 'share', pct);
    kpi('.bk-mk-left', 'map_coverage', 'left_out', fmt);
    kpi('.bk-mk-st', 'map_summary', 'stations', fmt);
    kpi('.bk-mk-top', 'map_top_stations', 'starts', fmt);
    const ts = dash.data('map_top_stations'); if (ts.status === 'ok') $('.bk-mk-top-n').textContent = ts.data[0].station;
    kpi('.bk-mk-rt', 'map_top_routes', 'trips', fmt);
    const tr = dash.data('map_top_routes'); if (tr.status === 'ok') $('.bk-mk-rt-n').textContent = tr.data[0].route;
  }

  function redraw() {
    if (!page || page.hidden) return;
    const failed = DATA.some((id) => dash.data(id).status === 'error');
    if (failed) { const box = $('.bk-m-map'); box.classList.remove('dash-skeleton'); box.replaceChildren(); const d = document.createElement('div'); d.className = 'bk-fail'; d.append(document.createElement('i'), 'Failed to load'); box.appendChild(d); return; }
    fillTables();
    if (!D) {
      D = prepare(); if (!D) return;
      M.vmaxH = d3.max(dash.data('map_station_hour').data, (r) => r.starts);
      M.vmaxM = d3.max(dash.data('map_station_month').data, (r) => r.starts);
      M.peakH = d3.max([...D.rtHour.values()], (rs) => d3.sum(rs, (r) => r.trips));
      M.peakM = d3.max([...D.rtMonth.values()], (rs) => d3.sum(rs, (r) => r.trips));
    }
    const find = $('.bk-m-find');
    if (find.options.length <= 1) {
      [...D.stations].sort((a, b) => a.name.localeCompare(b.name)).forEach((st) => find.appendChild(new Option(st.name, String(st.num))));
    }
    if (M.sel != null && linkData()) drawLinks();
    const box = $('.bk-m-map'); box.classList.remove('dash-skeleton');
    if (!M.built || box.clientWidth !== M.lastW) { M.lastW = box.clientWidth; build(); }
    if (!M.started) { M.started = true; if (!reduced) { M.playing = true; $('.bk-mplay').textContent = '❚❚ Pause'; } }
    show();
  }

  window.bkMapInit = (el) => {
    page = el; $ = (s) => page.querySelector(s);
    page.querySelectorAll('.bk-sw-a').forEach((e) => (e.style.background = dash.colors[0]));
    page.querySelectorAll('.bk-sw-b').forEach((e) => (e.style.background = dash.colors[1]));
    page.querySelectorAll('.bk-mseg button').forEach((btn) => btn.addEventListener('click', () => {
      M.mode = btn.dataset.mm; M.idx = 0; M.acc = 0;
      page.querySelectorAll('.bk-mseg button').forEach((b) => b.setAttribute('aria-pressed', String(b === btn)));
      show();
    }));
    const pb = $('.bk-mplay');
    pb.addEventListener('click', () => { M.playing = !M.playing; pb.textContent = M.playing ? '❚❚ Pause' : '▶ Play'; });
    $('.bk-m-range').addEventListener('input', (e) => { M.idx = Number(e.target.value); M.acc = 0; show(); });
    $('.bk-p-close').addEventListener('click', () => select(null));
    page.addEventListener('keydown', (e) => { if (e.key === 'Escape' && M.sel != null) select(null); });
    $('.bk-m-find').addEventListener('change', (e) => {
      const v = e.target.value; if (!v) return select(null);
      const st = D && D.byNum.get(Number(v)); if (st) { select(st.num); focusOn(st); }
    });
    const zb = (f) => () => svg && svg.transition().duration(reduced ? 0 : 350).call(f);
    $('.bk-z-in').addEventListener('click', zb((t) => zoom.scaleBy(t, 1.6)));
    $('.bk-z-out').addEventListener('click', zb((t) => zoom.scaleBy(t, 1 / 1.6)));
    $('.bk-z-reset').addEventListener('click', zb((t) => zoom.transform(t, d3.zoomIdentity)));
    dash.onData(redraw);
    requestAnimationFrame(tick);
  };
  window.bkMapRedraw = () => { M.lastW = -1; redraw(); };
})();
