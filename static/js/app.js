const $ = id => document.getElementById(id) || document.createElement('div');
const has = id => !!document.getElementById(id);
const C = {or: '#E8731A', gr: '#14452F', gr2: '#1F6A48', lg: '#B9C2BC'};
let META, timer, secs = 0, poll;
const api = async (url, opt) => {
  const r = await fetch(url, opt); const d = await r.json();
  if (!r.ok) throw new Error(d.error || 'Something went wrong. Try again.'); return d;
};
const show = (el, msg) => { el.textContent = msg; el.hidden = !msg; };
$('burger').onclick = () => $('menu').classList.toggle('open');
$('menu').onclick = () => $('menu').classList.remove('open');

function fill(sel, items, val) { sel.innerHTML = items.map(i => `<option>${i}</option>`).join(''); if (val) sel.value = val; }
function onBus() {
  const st = META.routes[META.buses[$('bus').value]].stops;
  fill($('src'), st, st[0]); fill($('dst'), st, st[st.length - 1]); fill($('stop'), st, st[Math.floor(st.length / 2)]);
}
async function load() {
  META = await api('/api/meta');
  if (has('trackForm')) { fill($('bus'), Object.keys(META.buses)); $('bus').onchange = onBus; onBus(); trackNow(); }
  drawCharts(); if (has('home')) homeStat(); if (has('planForm')) planInit(); if (has('routeStops')) routeStops();
}

// ---- Tracking ----
function card(cls, label, val) { return `<div class="card ${cls}"><small>${label}</small><b>${val}</b></div>`; }
function drawMap(d) {
  const pts = d.stops.map(s => `${s.x},${s.y}`).join(' ');
  const sel = $('stop').value;
  $('map').innerHTML = `<polyline points="${pts}" fill="none" stroke="${C.gr2}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>` +
    d.stops.map(s => `<circle cx="${s.x}" cy="${s.y}" r="${s.name === sel ? 3 : 2}" fill="${s.name === sel ? C.or : '#fff'}" stroke="${C.gr}" stroke-width="1"/><text x="${s.x}" y="${s.y + 6}" font-size="3" text-anchor="middle" fill="${C.gr}">${s.name}</text>`).join('') +
    `<circle class="pulse" cx="${d.position.x}" cy="${d.position.y}" r="3" fill="${C.or}"/><circle cx="${d.position.x}" cy="${d.position.y}" r="3" fill="${C.or}" stroke="#fff" stroke-width="1"/><text x="${d.position.x}" y="${d.position.y - 5}" font-size="3.2" font-weight="700" text-anchor="middle" fill="${C.or}">${d.bus}</text>`;
}
async function trackNow() {
  const err = $('trackErr'); show(err, '');
  const st = META.routes[META.buses[$('bus').value]].stops;
  if (st.indexOf($('src').value) >= st.indexOf($('dst').value)) return show(err, 'Choose a destination that comes after the source on this route.');
  try {
    const d = await api(`/api/track?bus=${$('bus').value}&stop=${encodeURIComponent($('stop').value)}`);
    const cls = d.status === 'On Time' ? 'g' : 'r';
    $('cards').innerHTML = card('', 'Arriving in', `${Math.round(d.eta_min)} minutes`) + card('g', 'Distance', `${d.distance_km} km`) +
      card('', 'Current speed', `${d.speed} km/h`) + card(cls, 'Status', d.status + (d.delay_min > 0 ? ` (+${d.delay_min} min)` : '')) + card('g', 'Traffic', d.traffic);
    $('stops').innerHTML = d.upcoming.map(u => `<li class="${u.name === $('stop').value ? 'sel' : ''}"><span>${u.name}</span><span>${u.km} km &middot; ${u.eta_min} min</span></li>`).join('') || '<li>Bus is at the last stop. Next trip starts soon.</li>';
    drawMap(d); secs = Math.round(d.eta_min * 60); tick();
    $('h-next').textContent = Math.round(d.eta_min);
    $('modelNote').textContent = 'Prediction engine: ' + d.model + '. Tracking data is simulated demo data.';
  } catch (e) { show(err, e.message); }
}
function tick() { clearInterval(timer); const f = () => { $('count').textContent = `${String(Math.floor(secs / 60)).padStart(2, '0')}:${String(secs % 60).padStart(2, '0')}`; if (secs > 0) secs--; }; f(); timer = setInterval(f, 1000); }
$('trackForm').onsubmit = e => { e.preventDefault(); trackNow(); clearInterval(poll); poll = setInterval(trackNow, 10000); };
$('stop').onchange = trackNow;

// ---- Prediction ----
$('predForm').onsubmit = async e => {
  e.preventDefault(); show($('predErr'), ''); $('predOut').hidden = true;
  try {
    const d = await api('/api/predict', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({
      speed: $('p-speed').value, distance: $('p-dist').value, traffic: $('p-traffic').value, hour: $('p-hour').value, dow: $('p-dow').value, hist_speed: $('p-hist').value})});
    $('predOut').hidden = false;
    $('predOut').innerHTML = `Predicted arrival<br><b>${d.eta_min} min</b><br>Timetable: ${d.scheduled_min} min &middot; Estimated delay: <strong>${d.delay_min > 0 ? '+' : ''}${d.delay_min} min</strong><br><small>Model: ${d.model}</small>`;
  } catch (e) { show($('predErr'), e.message); }
};

// ---- Charts ----
const ds = (label, data, color, extra = {}) => ({label, data, borderColor: color, backgroundColor: color, tension: .35, ...extra});
async function drawCharts() {
  const [h, t, a] = await Promise.all([api('/api/history'), api('/api/traffic-effect'), api('/api/analytics')]);
  has('histChart') && new Chart($('histChart'), {type: 'line', data: {labels: h.map(x => x.hour), datasets: [ds('Scheduled', h.map(x => x.scheduled), C.lg, {borderDash: [5, 5]}), ds('Actual', h.map(x => x.actual), C.gr), ds('Predicted', h.map(x => x.predicted), C.or)]}, options: {scales: {y: {title: {display: true, text: 'Trip minutes'}}}}});
  has('trafficChart') && new Chart($('trafficChart'), {type: 'bar', data: {labels: t.map(x => x.traffic), datasets: [{label: 'ETA for 5 km (min)', data: t.map(x => x.eta_min), backgroundColor: [C.gr2, C.lg, C.or], borderRadius: 10}]}, options: {plugins: {legend: {display: false}}}});
  has('routeChart') && new Chart($('routeChart'), {type: 'bar', data: {labels: a.routes.map(r => r.route), datasets: [{label: 'On-time %', data: a.routes.map(r => r.on_time_pct), backgroundColor: C.gr2, borderRadius: 10}]}, options: {scales: {y: {max: 100}}, plugins: {legend: {display: false}}}});
  $('kpis').innerHTML = card('', 'Total buses', a.total_buses) + card('g', 'Active routes', a.active_routes) + card('', 'Avg waiting time', a.avg_wait_min + ' min') + card('g', 'On-time', a.on_time_pct + '%') + card('r', 'Delayed buses', a.delayed_buses);
  $('alerts').innerHTML = a.delayed.map(d => `<li>&#9888; <b>${d.bus}</b> (${d.route}) is about ${d.delay_min} min late to ${d.next_stop}.</li>`).join('') || '<li>No delays right now. All buses are on schedule.</li>';
  $('routeCards').innerHTML = a.routes.map(r => `<div class="card g"><h4>${r.route}: ${r.name}</h4><small>${r.trips} past trips &middot; avg delay ${r.avg_delay} min &middot; ${r.on_time_pct}% on time</small></div>`).join('');
}

$('contactForm').onsubmit = async e => {
  e.preventDefault(); show($('cErr'), ''); $('cOk').hidden = true;
  try { await api('/api/contact', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name: $('c-name').value, email: $('c-email').value, message: $('c-msg').value})}); $('cOk').hidden = false; e.target.reset(); }
  catch (x) { show($('cErr'), x.message); }
};
load().catch(e => show($('trackErr'), 'Could not reach the server: ' + e.message));

async function homeStat() { try { const d = await api('/api/track?bus=BUS-101&stop=City%20College'); $('h-next').textContent = Math.round(d.eta_min); } catch (e) {} }
function routeStops() { $('routeStops').innerHTML = Object.entries(META.routes).map(([k, r]) => `<div class="card"><h4>${k}: ${r.name}</h4><small>${r.stops.join(' &rarr; ')}</small></div>`).join(''); }
function planInit() {
  const all = [...new Set(Object.values(META.routes).flatMap(r => r.stops))].sort();
  fill($('pl-src'), all, all[0]); fill($('pl-dst'), all, all[all.length - 1]);
  $('planForm').onsubmit = async e => {
    e.preventDefault(); show($('plErr'), ''); $('plOut').innerHTML = '';
    try {
      const d = await api(`/api/plan?src=${encodeURIComponent($('pl-src').value)}&dst=${encodeURIComponent($('pl-dst').value)}`);
      $('plOut').innerHTML = d.options.map(o => `<div class="card ${o.status === 'On Time' ? 'g' : 'r'}"><h4>${o.bus} &middot; ${o.route}</h4><b>${Math.round(o.wait_min)} min wait</b><small>Trip ${o.trip_min} min &middot; ${o.trip_km} km &middot; Fare Rs ${o.fare}<br>${o.status}</small></div>`).join('');
    } catch (x) { show($('plErr'), x.message); }
  };
}
