(() => {
  const root = document.getElementById('report');
  if (!root) return;
  const $ = (s) => root.querySelector(s);
  const fmt = d3.format(',');
  const pct = d3.format('.1%');
  const parse = d3.utcParse('%Y-%m-%d');
  const longDay = d3.utcFormat('%A %-d %B %Y');
  const shortDay = d3.utcFormat('%-d %b %Y');
  const monFmt = d3.utcFormat('%B %Y');
  const hrLab = (h) => (h === 0 ? 'midnight' : h < 12 ? h + 'am' : h === 12 ? 'noon' : (h - 12) + 'pm');
  const WX = { 1: 'clear', 2: 'mist', 3: 'wet', 4: 'wet' };
  const DEF = { start: '2011-01-01', end: '2012-12-31', daytype: 'all', riders: 'all', weather: 'all' };
  const MIN = '2011-01-01', MAX = '2012-12-31';
  const RIDER_COL = { all: 'cnt', registered: 'registered', casual: 'casual' };

  const prm = () => ({ ...DEF, ...dash.params() });

  // ---------- controls ----------
  const start = $('.rp-start'), end = $('.rp-end');
  const valid = (v) => v && v >= MIN && v <= MAX;
  start.addEventListener('change', () => { if (start.validity.valid && valid(start.value)) dash.setParams({ start: start.value }); });
  end.addEventListener('change', () => { if (end.validity.valid && valid(end.value)) dash.setParams({ end: end.value }); });
  [start, end].forEach((el) => el.addEventListener('blur', syncControls));
  root.querySelectorAll('.rp-preset').forEach((b) => b.addEventListener('click', () => dash.setParams({ start: b.dataset.s, end: b.dataset.e })));
  root.querySelectorAll('.rp-seg').forEach((seg) => seg.querySelectorAll('button').forEach((b) => b.addEventListener('click', () => dash.setParams({ [seg.dataset.p]: b.dataset.v }))));
  $('.rp-reset').addEventListener('click', () => dash.resetParams());
  root.querySelectorAll('[data-goto]').forEach((a) => a.addEventListener('click', () => window.bkOpenPage && window.bkOpenPage(a.dataset.goto)));

  function syncControls() {
    const p = prm();
    if (start !== document.activeElement) start.value = p.start;
    if (end !== document.activeElement) end.value = p.end;
    root.querySelectorAll('.rp-seg').forEach((seg) => seg.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.v === p[seg.dataset.p]))));
    root.querySelectorAll('.rp-preset').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.s === p.start && b.dataset.e === p.end)));
  }

  // ---------- filtering ----------
  function filterDays(rows, p) {
    const lo = p.start <= p.end ? p.start : p.end, hi = p.start <= p.end ? p.end : p.start;
    return rows.filter((r) => r.dteday >= lo && r.dteday <= hi
      && (p.daytype === 'all' || (p.daytype === 'working' ? Number(r.workingday) === 1 : Number(r.workingday) === 0))
      && (p.weather === 'all' || WX[r.weathersit] === p.weather));
  }

  // ---------- small DOM helpers for prose ----------
  const P = (box, src) => { const el = document.createElement('p'); el.className = 'rp-p'; if (src) el.dataset.source = src; box.appendChild(el); return el; };
  const say = (el, ...parts) => parts.forEach((x) => {
    if (x == null || x === false) return;
    if (typeof x === 'string') el.appendChild(document.createTextNode(x));
    else { const b = document.createElement('b'); b.textContent = x.b; el.appendChild(b); }
  });
  const B = (t) => ({ b: t });

  function riderWords(p) { return p.riders === 'registered' ? 'registered members' : p.riders === 'casual' ? 'casual riders' : 'riders'; }
  function scopeWords(p) {
    const bits = [];
    if (p.daytype === 'working') bits.push('on working days');
    if (p.daytype === 'weekend') bits.push('on weekends and holidays');
    if (p.weather === 'clear') bits.push('on clear days');
    if (p.weather === 'mist') bits.push('on misty or cloudy days');
    if (p.weather === 'wet') bits.push('on days with rain or snow');
    return bits.length ? ' ' + bits.join(' ') : '';
  }
  function filterLine(p) {
    const lo = p.start <= p.end ? p.start : p.end, hi = p.start <= p.end ? p.end : p.start;
    const bits = [shortDay(parse(lo)) + ' to ' + shortDay(parse(hi))];
    bits.push(p.daytype === 'all' ? 'all days' : p.daytype === 'working' ? 'working days' : 'weekends and holidays');
    bits.push(p.riders === 'all' ? 'all riders' : p.riders === 'registered' ? 'members only' : 'casual riders only');
    if (p.weather !== 'all') bits.push(p.weather === 'clear' ? 'clear weather' : p.weather === 'mist' ? 'mist or cloud' : 'rain or snow');
    return bits.join(' · ');
  }

  // ---------- charts ----------
  function svgIn(box, H) {
    box.replaceChildren();
    const W = Math.max(280, box.clientWidth);
    return { svg: d3.select(box).append('svg').attr('width', '100%').attr('height', H).attr('viewBox', `0 0 ${W} ${H}`), W, H };
  }
  function yAxis(svg, y, left, W) {
    const g = svg.append('g').attr('class', 'bk-tick').attr('transform', `translate(${left},0)`)
      .call(d3.axisLeft(y).ticks(4).tickSize(-(W - left)).tickFormat((v) => new Intl.NumberFormat('en', { notation: 'compact' }).format(v)));
    g.attr('font-size', null).attr('font-family', null); g.select('.domain').remove();
    g.selectAll('line').attr('stroke', 'var(--cds-chart-grid)'); g.selectAll('text').attr('x', -6);
  }
  function measure(svg, texts) {
    const t = svg.append('text').attr('class', 'bk-tick').style('font-size', 'var(--cds-font-size-caption)');
    let w = 0; texts.forEach((s) => { t.text(s); w = Math.max(w, t.node().getComputedTextLength()); }); t.remove(); return w;
  }

  function chartDaily(box, days, col) {
    if (!days.length) return box.replaceChildren();
    const { svg, W, H } = svgIn(box, 220);
    const pts = days.map((r) => ({ d: parse(r.dteday), v: Number(r[col]) }));
    const roll = pts.map((p, i) => { const a = pts.slice(Math.max(0, i - 6), i + 1); return { d: p.d, v: d3.mean(a, (x) => x.v) }; });
    const y = d3.scaleLinear([0, d3.max(pts, (p) => p.v) * 1.08 || 1], [H - 24, 8]).nice();
    const left = measure(svg, y.ticks(4).map((v) => new Intl.NumberFormat('en', { notation: 'compact' }).format(v))) + 10;
    const x = d3.scaleUtc(d3.extent(pts, (p) => p.d), [left + 4, W - 6]);
    yAxis(svg, y, left, W);
    const gx = svg.append('g').attr('class', 'bk-tick').attr('transform', `translate(0,${H - 24})`).call(d3.axisBottom(x).ticks(W < 480 ? 3 : 6).tickSize(0));
    gx.attr('font-size', null).attr('font-family', null); gx.select('.domain').attr('stroke', 'var(--cds-chart-axis)'); gx.selectAll('text').attr('dy', '1.2em');
    if (pts.length > 1) {
      svg.append('path').datum(pts).attr('fill', 'none').attr('stroke', 'var(--cds-chart-muted)').attr('stroke-width', 1).attr('d', d3.line().x((p) => x(p.d)).y((p) => y(p.v)));
      svg.append('path').datum(roll).attr('fill', 'none').attr('stroke', dash.colors[0]).attr('stroke-width', 2).attr('stroke-linejoin', 'round').attr('stroke-linecap', 'round').attr('d', d3.line().x((p) => x(p.d)).y((p) => y(p.v)));
    } else {
      svg.append('circle').attr('cx', x(pts[0].d)).attr('cy', y(pts[0].v)).attr('r', 4).attr('fill', dash.colors[0]);
    }
    // tooltip
    const tip = tipFor(box);
    const dot = svg.append('circle').attr('r', 4).attr('fill', dash.colors[0]).style('display', 'none');
    svg.append('rect').attr('x', left).attr('width', W - left).attr('height', H - 24).attr('fill', 'transparent')
      .on('mousemove', (e) => {
        const [mx] = d3.pointer(e); const t = x.invert(mx);
        const i = d3.bisector((p) => p.d).center(pts, t); const p0 = pts[i];
        dot.attr('cx', x(p0.d)).attr('cy', y(p0.v)).style('display', null);
        tip.show(e, shortDay(p0.d), [fmt(p0.v) + ' trips', '7-day average ' + fmt(Math.round(roll[i].v))]);
      })
      .on('mouseleave', () => { tip.hide(); dot.style('display', 'none'); });
  }

  function chartHourly(box, prof) {
    const { svg, W, H } = svgIn(box, 200);
    const y = d3.scaleLinear([0, d3.max(prof, (p) => p.v) * 1.12 || 1], [H - 24, 8]).nice();
    const left = measure(svg, y.ticks(4).map((v) => new Intl.NumberFormat('en', { notation: 'compact' }).format(v))) + 10;
    const x = d3.scaleBand(d3.range(24), [left, W - 4]).padding(0.18);
    yAxis(svg, y, left, W);
    const peak = prof.reduce((a, p) => (p.v > a.v ? p : a), prof[0]);
    svg.selectAll('rect.b').data(prof).join('rect').attr('class', 'b').attr('x', (p) => x(p.hr)).attr('width', x.bandwidth())
      .attr('y', (p) => y(p.v)).attr('height', (p) => H - 24 - y(p.v)).attr('rx', 2)
      .attr('fill', (p) => (p.peak ? dash.colors[0] : 'var(--cds-chart-muted)'));
    [0, 6, 12, 18].forEach((h) => svg.append('text').attr('class', 'bk-ann-m').attr('x', x(h)).attr('y', H - 6).text(h === 0 ? '12am' : h === 12 ? '12pm' : h < 12 ? h + 'am' : (h - 12) + 'pm'));
    const tip = tipFor(box);
    svg.selectAll('rect.h').data(prof).join('rect').attr('class', 'h').attr('x', (p) => x(p.hr)).attr('width', x.bandwidth()).attr('y', 0).attr('height', H - 24).attr('fill', 'transparent')
      .on('mousemove', (e, p) => tip.show(e, hrLab(p.hr) + ' to ' + hrLab((p.hr + 1) % 24), [fmt(Math.round(p.v)) + ' trips on an average day']))
      .on('mouseleave', () => tip.hide());
    void peak;
  }

  function chartWeather(box, groups) {
    const { svg, W, H } = svgIn(box, 34 * groups.length + 10);
    const left = measure(svg, groups.map((g) => g.label)) + 12;
    const right = measure(svg, groups.map((g) => fmt(g.avg) + ' a day')) + 14;
    const x = d3.scaleLinear([0, d3.max(groups, (g) => g.avg) || 1], [left, W - right]);
    groups.forEach((g, i) => {
      const yy = 6 + i * 34;
      svg.append('text').attr('x', left - 8).attr('y', yy + 11).attr('dy', '0.35em').attr('text-anchor', 'end').style('fill', 'var(--color-fg)').style('font-size', 'var(--cds-font-size-caption)').text(g.label);
      svg.append('rect').attr('x', left).attr('y', yy).attr('height', 22).attr('width', Math.max(2, x(g.avg) - left)).attr('rx', 4)
        .attr('fill', g.key === 'wet' ? 'var(--cds-chart-status-critical)' : g.key === 'clear' ? dash.colors[0] : 'var(--cds-chart-muted)');
      svg.append('text').attr('x', x(g.avg) + 6).attr('y', yy + 11).attr('dy', '0.35em').style('fill', 'var(--color-fg-muted)').style('font-size', 'var(--cds-font-size-caption)').text(fmt(g.avg) + ' a day');
    });
  }

  function tipFor(box) {
    box.style.position = 'relative';
    let t = box.querySelector('.bk-tip'); if (!t) { t = document.createElement('div'); t.className = 'bk-tip'; box.appendChild(t); }
    return {
      show(e, h, rows) {
        t.replaceChildren(); const hd = document.createElement('div'); hd.className = 'bk-tip-h'; hd.textContent = h; t.appendChild(hd);
        rows.forEach((r) => { const d = document.createElement('div'); d.textContent = r; t.appendChild(d); });
        t.style.display = 'block'; const b = box.getBoundingClientRect();
        let x = e.clientX - b.left + 12; if (x + t.offsetWidth > b.width) x = e.clientX - b.left - t.offsetWidth - 12;
        t.style.left = Math.max(0, x) + 'px'; t.style.top = Math.max(0, e.clientY - b.top - t.offsetHeight - 8) + 'px';
      },
      hide() { t.style.display = 'none'; },
    };
  }

  // ---------- the report ----------
  function render() {
    if (root.hidden) return;
    syncControls();
    const p = prm();
    $('.rp-scope').textContent = filterLine(p);
    const dd = dash.data('day'), hh = dash.data('hour');
    const body = $('.rp-body');
    if (dd.status === 'error') { body.replaceChildren(); const f = document.createElement('div'); f.className = 'bk-fail'; f.append(document.createElement('i'), 'Failed to load'); body.appendChild(f); return; }
    if (dd.status !== 'ok') return;
    body.classList.remove('dash-skeleton');
    const col = RIDER_COL[p.riders];
    const days = filterDays(dd.data, p).sort((a, b) => (a.dteday < b.dteday ? -1 : 1));
    const sec = (id) => { const el = $(id); el.querySelectorAll('.rp-p, .rp-empty').forEach((n) => n.remove()); return el; };

    // 1. summary
    const s1 = sec('#rp-summary');
    const s1box = s1.querySelector('.rp-text');
    s1box.replaceChildren();
    if (!days.length) {
      const e = document.createElement('p'); e.className = 'rp-empty'; e.textContent = 'No days match these filters. Widen the dates or clear a filter.';
      s1box.appendChild(e);
      ['#rp-trend .rp-chart', '#rp-when .rp-chart', '#rp-weather .rp-chart'].forEach((q) => $(q).replaceChildren());
      ['#rp-trend .rp-text', '#rp-when .rp-text', '#rp-weather .rp-text', '#rp-where .rp-text'].forEach((q) => $(q).replaceChildren());
      $('.rp-st tbody').replaceChildren();
      return;
    }
    const total = d3.sum(days, (r) => Number(r[col]));
    const avg = total / days.length;
    const reg = d3.sum(days, (r) => Number(r.registered)), all = d3.sum(days, (r) => Number(r.cnt));
    const best = days.reduce((a, r) => (Number(r[col]) > Number(a[col]) ? r : a));
    const worst = days.reduce((a, r) => (Number(r[col]) < Number(a[col]) ? r : a));
    const a = P(s1box, 'day');
    if (days.length === 1) say(a, 'On ', B(longDay(parse(days[0].dteday))), ', ', riderWords(p), ' took ', B(fmt(total)), ' trips.');
    else say(a, 'From ', B(shortDay(parse(days[0].dteday))), ' to ', B(shortDay(parse(days[days.length - 1].dteday))), ', ', riderWords(p), ' took ', B(fmt(total)), ' trips' + scopeWords(p) + ', an average of ', B(fmt(Math.round(avg))), ' a day across ', B(fmt(days.length)), ' days.');
    if (p.riders === 'all') say(a, ' Registered members made ', B(pct(reg / all)), ' of them.');
    else say(a, ' That is ', B(pct(total / all)), ' of all trips on those days.');
    // same dates a year earlier, when the range sits in 2012
    if (days[0].dteday >= '2012-01-01') {
      const back = (d) => '2011' + d.slice(4);
      const lo = back(days[0].dteday), hi = back(days[days.length - 1].dteday);
      const prev = filterDays(dd.data, { ...p, start: lo, end: hi });
      if (prev.length) {
        const pavg = d3.mean(prev, (r) => Number(r[col]));
        const ch = avg / pavg - 1;
        say(a, ' Per day, that is ', B((ch >= 0 ? 'up ' : 'down ') + pct(Math.abs(ch))), ' on the same dates in 2011.');
      }
    }
    if (days.length > 1) {
      const b = P(s1box, 'day');
      say(b, 'The busiest day was ', B(longDay(parse(best.dteday))), ', with ', B(fmt(Number(best[col]))), ' trips. The quietest was ', B(longDay(parse(worst.dteday))), ', with ', B(fmt(Number(worst[col]))),
        worst.dteday === '2012-10-29' ? ', the day Hurricane Sandy reached Washington.' : '.');
    }

    // 2. trend
    const tbox = $('#rp-trend .rp-text'); tbox.replaceChildren();
    const months = d3.rollups(days, (v) => d3.mean(v, (r) => Number(r[col])), (r) => r.dteday.slice(0, 7)).sort((x, y) => (x[0] < y[0] ? -1 : 1));
    const t1 = P(tbox, 'day');
    if (months.length >= 2) {
      const [fm, fv] = months[0], [lm, lv] = months[months.length - 1];
      const pk = months.reduce((x, y) => (y[1] > x[1] ? y : x));
      say(t1, 'Daily demand went ', lv >= fv ? 'from ' : 'down from ', B(fmt(Math.round(fv))), ' a day in ', B(monFmt(parse(fm + '-01'))), ' to ', B(fmt(Math.round(lv))), ' in ', B(monFmt(parse(lm + '-01'))), '. ',
        'The strongest month was ', B(monFmt(parse(pk[0] + '-01'))), ', at ', B(fmt(Math.round(pk[1]))), ' a day.');
    } else say(t1, 'This selection covers part of a single month, so there is no month-to-month trend to describe. The chart shows each day.');
    chartDaily($('#rp-trend .rp-chart'), days, col);

    // 3. when
    const wbox = $('#rp-when .rp-text'); wbox.replaceChildren();
    const wchart = $('#rp-when .rp-chart');
    if (hh.status === 'ok') {
      const set = new Set(days.map((r) => r.dteday));
      const sums = new Array(24).fill(0);
      hh.data.forEach((r) => { if (set.has(r.dteday)) sums[Number(r.hr)] += Number(r[col]); });
      const prof = sums.map((v, hr) => ({ hr, v: v / days.length }));
      const am = prof.slice(6, 10).reduce((x, y) => (y.v > x.v ? y : x));
      const pmP = prof.slice(15, 20).reduce((x, y) => (y.v > x.v ? y : x));
      const top = prof.reduce((x, y) => (y.v > x.v ? y : x));
      const midday = d3.mean(prof.slice(10, 15), (r) => r.v);
      const w1 = P(wbox, 'hour');
      if (top.v < 3 || d3.sum(prof, (r) => r.v) < 150) {
        say(w1, 'There are too few trips in this selection to show a clear daily rhythm.');
      } else if (am.v > midday * 1.4 && pmP.v > midday * 1.2) {
        am.peak = true; pmP.peak = true;
        say(w1, 'Riding has two rush hours: a morning peak at ', B(hrLab(am.hr)), ' with ', B(fmt(Math.round(am.v))), ' trips in the hour, and an evening peak at ', B(hrLab(pmP.hr)), ' with ', B(fmt(Math.round(pmP.v))), '. That is the shape of commuting.');
      } else if (top.hr < 10 || top.hr > 17) {
        top.peak = true;
        say(w1, 'Riding peaks at ', B(hrLab(top.hr)), ', with ', B(fmt(Math.round(top.v))), ' trips in the hour.');
      } else {
        top.peak = true;
        say(w1, 'There is no real rush hour here. Riding builds through the morning to a peak at ', B(hrLab(top.hr)), ', with ', B(fmt(Math.round(top.v))), ' trips in the hour, and stays busy through the afternoon. That is the shape of leisure riding.');
      }
      chartHourly(wchart, prof);
    } else if (hh.status === 'error') { wchart.replaceChildren(); }

    // 4. weather
    const xbox = $('#rp-weather .rp-text'); xbox.replaceChildren();
    const groups = [['clear', 'Clear'], ['mist', 'Mist or cloud'], ['wet', 'Rain or snow']].map(([key, label]) => {
      const g = days.filter((r) => WX[r.weathersit] === key);
      return { key, label, n: g.length, avg: g.length ? Math.round(d3.mean(g, (r) => Number(r[col]))) : 0 };
    }).filter((g) => g.n);
    const x1 = P(xbox, 'day');
    const clear = groups.find((g) => g.key === 'clear'), wet = groups.find((g) => g.key === 'wet');
    if (clear && wet) say(x1, 'Weather makes a big difference. Clear days averaged ', B(fmt(clear.avg)), ' trips, against ', B(fmt(wet.avg)), ' on the ', B(fmt(wet.n)), wet.n === 1 ? ' day' : ' days', ' with rain or snow, a drop of ', B(pct(1 - wet.avg / clear.avg)), '.');
    else if (groups.length === 1) say(x1, 'Every day in this selection had the same weather type, so there is nothing to compare.');
    else say(x1, 'There were no days with rain or snow in this selection.');
    const temp = days.map((r) => ({ t: Number(r.temp) * 41, v: Number(r[col]) }));
    const cold = temp.filter((r) => r.t < 10), warm = temp.filter((r) => r.t >= 20 && r.t < 30);
    if (cold.length >= 3 && warm.length >= 3) {
      const x2 = P(xbox, 'day');
      say(x2, 'Temperature matters too: days between 20 and 30°C averaged ', B(fmt(Math.round(d3.mean(warm, (r) => r.v)))), ' trips, compared with ', B(fmt(Math.round(d3.mean(cold, (r) => r.v)))), ' on days below 10°C.');
    }
    chartWeather($('#rp-weather .rp-chart'), groups);

    // 5. where
    const gbox = $('#rp-where .rp-text'); gbox.replaceChildren();
    const sm = dash.data('map_station_month'), st = dash.data('map_stations');
    const tb = $('.rp-st tbody'); tb.replaceChildren();
    if (sm.status === 'ok' && st.status === 'ok') {
      const lo = days[0].dteday.slice(0, 7), hi = days[days.length - 1].dteday.slice(0, 7);
      const name = new Map(st.data.map((s) => [s.num, s.name]));
      const tot = d3.rollups(sm.data.filter((r) => r.ym >= lo && r.ym <= hi), (v) => d3.sum(v, (r) => r.starts), (r) => r.num).sort((x, y) => y[1] - x[1]);
      const sumAll = d3.sum(tot, (r) => r[1]);
      const top = tot.slice(0, 5);
      const g1 = P(gbox, 'map_station_month');
      if (top.length) {
        say(g1, 'The busiest station from ', B(monFmt(parse(lo + '-01'))), ' to ', B(monFmt(parse(hi + '-01'))), ' was ', B(name.get(top[0][0])), ', where ', B(fmt(top[0][1])), ' trips started. The five busiest stations together handled ', B(pct(d3.sum(top, (r) => r[1]) / sumAll)), ' of all trips across ', B(fmt(tot.length)), ' active stations.');
        if (p.daytype !== 'all' || p.riders !== 'all' || p.weather !== 'all') say(g1, ' Station figures count every trip in these months, whatever the other filters.');
      }
      top.forEach((r, i) => {
        const tr = document.createElement('tr');
        [String(i + 1), name.get(r[0]), fmt(r[1])].forEach((v) => { const td = document.createElement('td'); td.textContent = v; tr.appendChild(td); });
        tb.appendChild(tr);
      });
    }
  }

  dash.onData(render);
  window.bkRedrawReport = render;
})();
