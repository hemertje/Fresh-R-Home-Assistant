/**
 * Fresh-r Dashboard Card with Multi-language Support
 * Replicates the fresh-r.me dashboard in Home Assistant Lovelace.
 * 
 * Language support: English, Dutch, German, French (auto-detected from Home Assistant)
 */

// Language translations
const TRANSLATIONS = {
  en: {
    tabs: {
      oxygen: 'Oxygen',
      humidity: 'Humidity',
      dust: 'Dust'
    },
    chartLabels: {
      temperature: 'Temperature',
      flow: 'Flow',
      heat: 'Heat',
      humidity: 'Humidity',
      pm25: 'PM2.5'
    },
    legend: {
      co2_good: 'CO2 good',
      co2_moderate: 'CO2 moderate',
      co2_bad: 'CO2 bad',
      flow: 'Flow',
      indoor_air: 'Indoor Air',
      outdoor_air: 'Outdoor Air',
      supply_air: 'Supply Air',
      exhaust_air: 'Exhaust Air',
      heat_recovery: 'Heat Recovery',
      energy_loss: 'Energy Loss',
      pm25: 'PM2.5'
    },
    stats: {
      indoor_temp: 'Indoor Temp',
      outdoor_temp: 'Outdoor Temp',
      flow: 'Flow',
      co2: 'CO2',
      humidity: 'Humidity',
      dew_point: 'Dew Point',
      heat_recovery: 'Heat Recovery',
      energy_loss: 'Energy Loss'
    },
    no_data: 'No data',
    outside: 'outside'
  },
  nl: {
    tabs: {
      oxygen: 'Zuurstof',
      humidity: 'Vochtigheid',
      dust: 'Fijnstof'
    },
    chartLabels: {
      temperature: 'Temperatuur',
      flow: 'Debiet',
      heat: 'Warmte',
      humidity: 'Vochtigheid',
      pm25: 'PM2.5'
    },
    legend: {
      co2_good: 'CO2 goed',
      co2_moderate: 'CO2 matig',
      co2_bad: 'CO2 slecht',
      flow: 'Debiet',
      indoor_air: 'Binnenlucht',
      outdoor_air: 'Buitenlucht',
      supply_air: 'Aanvoer',
      exhaust_air: 'Afvoer',
      heat_recovery: 'Warmteterugwinning',
      energy_loss: 'Energieverlies',
      pm25: 'Fijnstof'
    },
    stats: {
      indoor_temp: 'Binnentemp',
      outdoor_temp: 'Buitentemp',
      flow: 'Debiet',
      co2: 'CO2',
      humidity: 'Vochtigheid',
      dew_point: 'Dauwpunt',
      heat_recovery: 'Warmteterugwinning',
      energy_loss: 'Energieverlies'
    },
    no_data: 'Geen data',
    outside: 'buiten'
  },
  de: {
    tabs: {
      oxygen: 'Sauerstoff',
      humidity: 'Feuchtigkeit',
      dust: 'Feinstaub'
    },
    chartLabels: {
      temperature: 'Temperatur',
      flow: 'Volumenstrom',
      heat: 'Wärme',
      humidity: 'Feuchtigkeit',
      pm25: 'PM2.5'
    },
    legend: {
      co2_good: 'CO2 gut',
      co2_moderate: 'CO2 moderat',
      co2_bad: 'CO2 schlecht',
      flow: 'Volumenstrom',
      indoor_air: 'Innenluft',
      outdoor_air: 'Außenluft',
      supply_air: 'Zuluft',
      exhaust_air: 'Abluft',
      heat_recovery: 'Wärmerückgewinnung',
      energy_loss: 'Energieverlust',
      pm25: 'Feinstaub'
    },
    stats: {
      indoor_temp: 'Innentemperatur',
      outdoor_temp: 'Außentemperatur',
      flow: 'Volumenstrom',
      co2: 'CO2',
      humidity: 'Feuchtigkeit',
      dew_point: 'Taupunkt',
      heat_recovery: 'Wärmerückgewinnung',
      energy_loss: 'Energieverlust'
    },
    no_data: 'Keine Daten',
    outside: 'außen'
  },
  fr: {
    tabs: {
      oxygen: 'Oxygène',
      humidity: 'Humidité',
      dust: 'Particules fines'
    },
    chartLabels: {
      temperature: 'Température',
      flow: 'Débit',
      heat: 'Chaleur',
      humidity: 'Humidité',
      pm25: 'PM2.5'
    },
    legend: {
      co2_good: 'CO2 bon',
      co2_moderate: 'CO2 modéré',
      co2_bad: 'CO2 mauvais',
      flow: 'Débit',
      indoor_air: 'Air intérieur',
      outdoor_air: 'Air extérieur',
      supply_air: 'Air soufflé',
      exhaust_air: 'Air évacué',
      heat_recovery: 'Récupération de chaleur',
      energy_loss: 'Perte d\'énergie',
      pm25: 'PM2.5'
    },
    stats: {
      indoor_temp: 'Température intérieure',
      outdoor_temp: 'Température extérieure',
      flow: 'Débit',
      co2: 'CO2',
      humidity: 'Humidité',
      dew_point: 'Point de rosée',
      heat_recovery: 'Récupération de chaleur',
      energy_loss: 'Perte d\'énergie'
    },
    no_data: 'Aucune donnée',
    outside: 'extérieur'
  }
};

// Color scheme (unchanged)
const COLORS = {
  co2_good:     '#4caf50',
  co2_moderate: '#ff9800',
  co2_bad:      '#f44336',
  flow:         '#2196f3',
  temp_indoor:  '#ff5722',
  temp_outdoor: '#03a9f4',
  temp_supply:  '#8bc34a',
  temp_exhaust: '#9c27b0',
  heat:         '#ff9800',
  loss:         '#607d8b',
  energy:       '#e91e63',
  pm25:         '#795548',
  bg:           '#1a1a2e',
  panel:        '#16213e',
  card:         '#0f3460',
  text:         '#e0e0e0',
  muted:        '#90a4ae',
  accent:       '#00bcd4',
};

const CO2_GOOD     = 1000;
const CO2_MODERATE = 1200;

function co2Color(ppm) {
  if (ppm <= CO2_GOOD)     return COLORS.co2_good;
  if (ppm <= CO2_MODERATE) return COLORS.co2_moderate;
  return COLORS.co2_bad;
}

// Language detection from Home Assistant
function getLanguage() {
  // Try to get language from Home Assistant
  if (window.hass && window.hass.language) {
    const lang = window.hass.language.split('-')[0];
    if (TRANSLATIONS[lang]) return lang;
  }
  
  // Fallback to browser language
  const browserLang = navigator.language.split('-')[0];
  return TRANSLATIONS[browserLang] ? browserLang : 'en';
}

// Get translation for current language
function t(key, subkey = null) {
  const lang = getLanguage();
  const translations = TRANSLATIONS[lang];
  
  if (subkey) {
    return translations[key]?.[subkey] || TRANSLATIONS.en[key]?.[subkey] || key;
  }
  return translations[key] || TRANSLATIONS.en[key] || key;
}

// ─── Radial 24h clock ─────────────────────────────────────────────────────────────
class RadialChart {
  constructor(canvas, data) {
    this.canvas = canvas;
    this.data   = data;
  }

  draw() {
    const ctx  = this.canvas.getContext('2d');
    const cx   = this.canvas.width / 2;
    const cy   = this.canvas.height / 2;
    const R    = Math.min(cx, cy) * 0.9;
    const size = this.canvas.width;

    // Clear
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    // Background rings
    ctx.strokeStyle = COLORS.card;
    ctx.lineWidth   = 1;
    for (let i = 1; i <= 3; i++) {
      ctx.beginPath();
      ctx.arc(cx, cy, R * (i * 0.27), 0, 2 * Math.PI);
      ctx.stroke();
    }

    // Hour markers
    for (let h = 0; h < 24; h++) {
      const a = (h / 24) * 2 * Math.PI - Math.PI / 2;
      const x1 = cx + Math.cos(a) * (R * 0.95);
      const y1 = cy + Math.sin(a) * (R * 0.95);
      const x2 = cx + Math.cos(a) * (R * 0.92);
      const y2 = cy + Math.sin(a) * (R * 0.92);
      
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.strokeStyle = COLORS.muted;
      ctx.lineWidth   = h % 6 === 0 ? 2 : 1;
      ctx.stroke();
    }

    // Normalise ranges
    const co2Max  = Math.max(...this.data.map(d => d.co2 || 0), 2000);
    const flowMax = Math.max(...this.data.map(d => d.flow || 0), 100);
    const tMin    = Math.min(...this.data.map(d => d.t2 || 20), 0);
    const tMax    = Math.max(...this.data.map(d => d.t1 || 25), 30);

    this.data.forEach(point => {
      const h   = point.time.getHours() + point.time.getMinutes() / 60;
      const a0  = (h / 24) * 2 * Math.PI - Math.PI / 2;
      const a1  = a0 + (10 / (24 * 60)) * 2 * Math.PI;

      // CO2 spike (outer ring)
      const co2Ratio  = Math.min((point.co2 || 0) / co2Max, 1);
      const spikeR    = R * 0.82 + co2Ratio * R * 0.16;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(a0) * (R * 0.82), cy + Math.sin(a0) * (R * 0.82));
      ctx.arc(cx, cy, spikeR, a0, a1);
      ctx.lineTo(cx + Math.cos(a1) * (R * 0.82), cy + Math.sin(a1) * (R * 0.82));
      ctx.arc(cx, cy, R * 0.82, a1, a0, true);
      ctx.fillStyle = co2Color(point.co2 || 0) + 'cc';
      ctx.fill();

      // Flow surface (middle ring)
      const flowRatio = Math.min((point.flow || 0) / flowMax, 1);
      const flowR     = R * 0.58 + flowRatio * R * 0.20;
      ctx.beginPath();
      ctx.arc(cx, cy, flowR, a0, a1);
      ctx.arc(cx, cy, R * 0.58, a1, a0, true);
      ctx.closePath();
      ctx.fillStyle = COLORS.flow + '99';
      ctx.fill();

      // Temperature (inner ring)
      const t1     = point.t1 || 20;
      const t2     = point.t2 || 10;
      const tRange = tMax - tMin || 1;
      const t1R    = R * 0.36 + ((t1 - tMin) / tRange) * R * 0.18;
      const t2R    = R * 0.36 + ((t2 - tMin) / tRange) * R * 0.18;
      // Indoor
      ctx.beginPath();
      ctx.arc(cx, cy, t1R, a0, a1);
      ctx.arc(cx, cy, R * 0.36, a1, a0, true);
      ctx.closePath();
      ctx.fillStyle = COLORS.temp_indoor + '88';
      ctx.fill();
      // Outdoor
      ctx.beginPath();
      ctx.arc(cx, cy, t2R, a0, a1);
      ctx.arc(cx, cy, R * 0.36, a1, a0, true);
      ctx.closePath();
      ctx.fillStyle = COLORS.temp_outdoor + '88';
      ctx.fill();
    });

    // Center bg
    ctx.beginPath();
    ctx.arc(cx, cy, R * 0.32, 0, 2 * Math.PI);
    ctx.fillStyle = COLORS.panel;
    ctx.fill();

    ctx.textAlign    = 'center';
    ctx.textBaseline = 'middle';

    const size = this.canvas.width;

    if (t1 !== null) {
      // Temperature
      ctx.fillStyle = COLORS.temp_indoor;
      ctx.font      = `bold ${size * 0.072}px sans-serif`;
      ctx.fillText((+t1).toFixed(1) + '°C', cx, cy - size * 0.085);

      // Flow
      ctx.fillStyle = COLORS.flow;
      ctx.font      = `bold ${size * 0.055}px sans-serif`;
      ctx.fillText((+flow).toFixed(0) + ' m³/h', cx, cy - size * 0.018);

      // CO2
      ctx.fillStyle = co2Color(+co2);
      ctx.font      = `bold ${size * 0.05}px sans-serif`;
      ctx.fillText((+co2).toFixed(0) + ' ppm', cx, cy + size * 0.045);

      // Outdoor temp
      ctx.fillStyle = COLORS.temp_outdoor;
      ctx.font      = `${size * 0.035}px sans-serif`;
      ctx.fillText(t('outside') + ' ' + (+t2).toFixed(1) + '°C', cx, cy + size * 0.095);
    } else {
      ctx.fillStyle = COLORS.muted;
      ctx.font      = `${size * 0.04}px sans-serif`;
      ctx.fillText(t('no_data'), cx, cy);
    }
  }
}

// ─── Mini line chart ──────────────────────────────────────────────────────────
function drawLineChart(canvas, datasets, ylabel) {
  const ctx  = canvas.getContext('2d');
  const W    = canvas.width;
  const H    = canvas.height;
  const pad  = { t: 10, r: 10, b: 25, l: 42 };
  const iW   = W - pad.l - pad.r;
  const iH   = H - pad.t - pad.b;

  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = COLORS.panel;
  ctx.fillRect(0, 0, W, H);

  if (!datasets || !datasets[0] || !datasets[0].data.length) {
    ctx.fillStyle = COLORS.muted;
    ctx.font      = '12px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(t('no_data'), W / 2, H / 2);
    return;
  }

  // Value range
  const allVals = datasets.flatMap(ds => ds.data.map(p => p.y));
  const yMin    = Math.min(...allVals);
  const yMax    = Math.max(...allVals);
  const yRange  = yMax - yMin || 1;

  const allTimes = datasets[0].data.map(p => p.x.getTime());
  const tMin  = Math.min(...allTimes);
  const tMax  = Math.max(...allTimes);
  const tRange = tMax - tMin || 1;

  const tx = t => pad.l + ((t.getTime() - tMin) / tRange) * iW;
  const ty = v => pad.t + iH - ((v - yMin) / yRange) * iH;

  // Grid
  ctx.strokeStyle = '#1e3a5f';
  ctx.lineWidth   = 1;
  for (let i = 0; i <= 4; i++) {
    const y = pad.t + (i / 4) * iH;
    ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(pad.l + iW, y); ctx.stroke();
    const val = yMax - (i / 4) * yRange;
    ctx.fillStyle    = COLORS.muted;
    ctx.font         = '9px sans-serif';
    ctx.textAlign    = 'right';
    ctx.textBaseline = 'middle';
    ctx.fillText(val.toFixed(0), pad.l - 4, y);
  }

  // Lines
  datasets.forEach(ds => {
    if (!ds.data.length) return;
    ctx.beginPath();
    ctx.strokeStyle = ds.color;
    ctx.lineWidth   = 1.5;
    ctx.lineJoin    = 'round';
    ds.data.forEach((p, i) => {
      const x = tx(p.x);
      const y = ty(p.y);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.stroke();
  });

  // X axis labels (hours)
  ctx.fillStyle    = COLORS.muted;
  ctx.font         = '9px sans-serif';
  ctx.textAlign    = 'center';
  ctx.textBaseline = 'top';
  for (let h = 0; h <= 23; h += 4) {
    const d = new Date(datasets[0].data[0].x);
    d.setHours(h, 0, 0, 0);
    if (d.getTime() >= tMin && d.getTime() <= tMax) {
      ctx.fillText(String(h).padStart(2,'0') + ':00', tx(d), pad.t + iH + 4);
    }
  }

  // Legend
  let lx = pad.l;
  ctx.textAlign    = 'left';
  ctx.textBaseline = 'top';
  ctx.font = '9px sans-serif';
  datasets.forEach(ds => {
    ctx.fillStyle = ds.color;
    ctx.fillRect(lx, 1, 14, 7);
    ctx.fillStyle = COLORS.text;
    ctx.fillText(ds.label, lx + 16, 1);
    lx += ctx.measureText(ds.label).width + 28;
  });
}

// ─── Web Component ────────────────────────────────────────────────────────────
class FreshRCard extends HTMLElement {
  constructor() {
    super();
    this._hass     = null;
    this._config   = null;
    this._history  = {};         // {entityId: [{time, value}]}
    this._tab      = 'oxygen';
    this._shadow   = this.attachShadow({ mode: 'open' });
    this._rendered = false;
    this._refreshTimer = null;
  }

  setConfig(config) {
    if (!config.entities) throw new Error('Fresh-r card: "entities" required');
    this._config = config;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._rendered) {
      this._build();
      this._rendered = true;
    }
    this._update();
  }

  _build() {
    this._shadow.innerHTML = `
      <style>
        :host { display: block; font-family: 'Nunito', sans-serif; }
        .card { background: ${COLORS.bg}; color: ${COLORS.text}; border-radius: 12px; overflow: hidden; }
        .tabs { display: flex; border-bottom: 1px solid ${COLORS.card}; }
        .tab  { flex: 1; padding: 10px; text-align: center; cursor: pointer; color: ${COLORS.muted};
                font-weight: 600; font-size: 13px; transition: all .2s; text-transform: uppercase; }
        .tab.active { color: ${COLORS.accent}; border-bottom: 2px solid ${COLORS.accent}; }
        .tab:hover  { color: ${COLORS.text}; }
        .body { display: flex; flex-wrap: wrap; padding: 8px; gap: 8px; }
        .polar-wrap { flex: 1; min-width: 240px; display: flex; justify-content: center; }
        .polar-wrap canvas { width: 100%; max-width: 360px; height: auto; }
        .charts { flex: 1.2; min-width: 260px; display: flex; flex-direction: column; gap: 8px; }
        .chart-wrap { background: ${COLORS.panel}; border-radius: 8px; padding: 6px; }
        .chart-label { font-size: 11px; color: ${COLORS.muted}; margin-bottom: 4px; text-transform: uppercase; letter-spacing: .5px; }
        .chart-wrap canvas { width: 100%; display: block; }
        .stats { display: flex; flex-wrap: wrap; gap: 8px; padding: 0 8px 8px; }
        .stat { background: ${COLORS.panel}; border-radius: 8px; padding: 10px 14px; flex: 1; min-width: 100px; }
        .stat-value { font-size: 22px; font-weight: 700; }
        .stat-label { font-size: 11px; color: ${COLORS.muted}; margin-top: 2px; }
        .legend { display: flex; flex-wrap: wrap; gap: 8px; padding: 0 8px 8px; }
        .leg-item { display: flex; align-items: center; gap: 5px; font-size: 11px; color: ${COLORS.muted}; }
        .leg-dot  { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
      </style>
      <div class="card">
        <div class="tabs">
          <div class="tab active" data-tab="oxygen">${t('tabs', 'oxygen')}</div>
          <div class="tab"        data-tab="humidity">${t('tabs', 'humidity')}</div>
          <div class="tab"        data-tab="dust">${t('tabs', 'dust')}</div>
        </div>
        <div class="body">
          <div class="polar-wrap">
            <canvas id="polar" width="360" height="360"></canvas>
          </div>
          <div class="charts">
            <div class="chart-wrap">
              <div class="chart-label" id="c1-label">${t('chartLabels', 'temperature')}</div>
              <canvas id="c1" width="500" height="120"></canvas>
            </div>
            <div class="chart-wrap">
              <div class="chart-label">${t('chartLabels', 'flow')} (m³/h)</div>
              <canvas id="c2" width="500" height="100"></canvas>
            </div>
            <div class="chart-wrap">
              <div class="chart-label">${t('chartLabels', 'heat')} (W)</div>
              <canvas id="c3" width="500" height="100"></canvas>
            </div>
          </div>
        </div>
        <div class="stats" id="stats"></div>
        <div class="legend" id="legend"></div>
      </div>
    `;

    this._shadow.querySelectorAll('.tab').forEach(t =>
      t.addEventListener('click', () => { this._tab = t.dataset.tab; this._setActiveTab(); this._draw(); })
    );

    this._polar = this._shadow.getElementById('polar');
    this._c1    = this._shadow.getElementById('c1');
    this._c2    = this._shadow.getElementById('c2');
    this._c3    = this._shadow.getElementById('c3');
  }

  _setActiveTab() {
    this._shadow.querySelectorAll('.tab').forEach(t =>
      t.classList.toggle('active', t.dataset.tab === this._tab)
    );
  }

  _val(key, fallback = null) {
    const eid = this._config.entities?.[key];
    if (!eid || !this._hass) return fallback;
    const s = this._hass.states[eid];
    if (!s || s.state === 'unavailable' || s.state === 'unknown') return fallback;
    const v = parseFloat(s.state);
    return isNaN(v) ? fallback : v;
  }

  _update() {
    if (!this._rendered) return;
    this._loadHistory().then(() => this._draw());
  }

  async _loadHistory() {
    if (!this._hass) return;
    const now   = new Date();
    const start = new Date(now); start.setHours(0, 0, 0, 0);

    const keys = ['t1','t2','t3','t4','flow','co2','hum','dp',
                  'd5_25','d4_25','d1_25','heat_recovered','vent_loss','energy_loss'];
    const eids = keys.map(k => this._config.entities?.[k]).filter(Boolean);
    if (!eids.length) return;

    try {
      const url = '/api/history/period/' + start.toISOString() + '?filter_entity_id=' + eids.join(',') + '&minimal_response=true';
      const r   = await this._hass.callApi('GET', url.slice(5));
      if (!Array.isArray(r)) return;
      r.forEach((series, i) => {
        const eid = eids[i];
        if (!eid || !series.length) return;
        this._history[eid] = series
          .filter(s => s.state !== 'unavailable' && s.state !== 'unknown')
          .map(s => ({ time: new Date(s.last_changed), value: parseFloat(s.state) }))
          .filter(p => !isNaN(p.value));
      });
    } catch (e) {
      // History API not accessible — draw without history
    }
  }

  _histSeries(key) {
    const eid = this._config.entities?.[key];
    if (!eid) return [];
    return (this._history[eid] || []).map(p => ({ x: p.time, y: p.value }));
  }

  _draw() {
    if (!this._rendered) return;
    this._drawPolar();
    this._drawLineCharts();
    this._drawStats();
    this._drawLegend();
  }

  _drawPolar() {
    // Build radial data from today's history
    const co2Data  = this._histSeries('co2');
    const flowData = this._histSeries('flow');
    const t1Data   = this._histSeries('t1');
    const t2Data   = this._histSeries('t2');

    // Align by closest timestamp
    const data = co2Data.map(p => {
      const find = (arr, t) => arr.reduce((a, b) =>
        Math.abs(b.x - t) < Math.abs(a.x - t) ? b : a, arr[0]);
      return {
        time: p.x,
        co2:  p.y,
        flow: flowData.length ? find(flowData, p.x).y : this._val('flow', 0),
        t1:   t1Data.length   ? find(t1Data,   p.x).y : this._val('t1', 20),
        t2:   t2Data.length   ? find(t2Data,   p.x).y : this._val('t2', 10),
      };
    });

    // Add current reading
    const now = new Date();
    data.push({
      time: now,
      co2:  this._val('co2', 0),
      flow: this._val('flow', 0),
      t1:   this._val('t1', 20),
      t2:   this._val('t2', 10),
    });

    new RadialChart(this._polar, data).draw();
  }

  _drawLineCharts() {
    const tab = this._tab;

    if (tab === 'oxygen') {
      // Chart 1: Indoor vs Outdoor temperature
      this._shadow.getElementById('c1-label').textContent = t('chartLabels', 'temperature') + ' (°C)';
      drawLineChart(this._c1, [
        { label: t('legend', 'indoor_air') + ' (t1)',  color: COLORS.temp_indoor,  data: this._histSeries('t1') },
        { label: t('legend', 'outdoor_air') + ' (t2)', color: COLORS.temp_outdoor, data: this._histSeries('t2') },
        { label: t('legend', 'supply_air') + ' (t3)',      color: COLORS.temp_supply,  data: this._histSeries('t3') },
        { label: t('legend', 'exhaust_air') + ' (t4)',       color: COLORS.temp_exhaust, data: this._histSeries('t4') },
      ]);
      // Chart 2: Flow
      drawLineChart(this._c2, [
        { label: t('legend', 'flow') + ' (m³/h)', color: COLORS.flow, data: this._histSeries('flow') },
      ]);
      // Chart 3: Heat
      drawLineChart(this._c3, [
        { label: t('legend', 'heat_recovery'), color: COLORS.heat,   data: this._histSeries('heat_recovered') },
        { label: 'Reference Ventilation Loss', color: COLORS.loss,   data: this._histSeries('vent_loss') },
        { label: t('legend', 'energy_loss'),     color: COLORS.energy, data: this._histSeries('energy_loss') },
      ]);

    } else if (tab === 'humidity') {
      this._shadow.getElementById('c1-label').textContent = t('chartLabels', 'humidity') + ' (%)';
      drawLineChart(this._c1, [
        { label: t('stats', 'humidity'), color: COLORS.flow, data: this._histSeries('hum') },
        { label: t('stats', 'dew_point') + ' (°C)',          color: COLORS.temp_outdoor, data: this._histSeries('dp') },
      ]);
      drawLineChart(this._c2, [
        { label: t('legend', 'flow') + ' (m³/h)', color: COLORS.flow, data: this._histSeries('flow') },
      ]);
      drawLineChart(this._c3, [
        { label: 'CO2 (ppm)', color: COLORS.co2_good, data: this._histSeries('co2') },
      ]);

    } else if (tab === 'dust') {
      this._shadow.getElementById('c1-label').textContent = t('chartLabels', 'pm25') + ' (µg/m³)';
      drawLineChart(this._c1, [
        { label: t('legend', 'supply_air') + ' PM2.5',   color: COLORS.temp_supply,  data: this._histSeries('d5_25') },
        { label: t('legend', 'outdoor_air') + ' PM2.5',    color: COLORS.temp_outdoor, data: this._histSeries('d4_25') },
        { label: t('legend', 'indoor_air') + ' PM2.5',    color: COLORS.temp_indoor,  data: this._histSeries('d1_25') },
      ]);
      drawLineChart(this._c2, [
        { label: t('legend', 'flow') + ' (m³/h)', color: COLORS.flow, data: this._histSeries('flow') },
      ]);
      drawLineChart(this._c3, [
        { label: 'CO2 (ppm)', color: COLORS.co2_good, data: this._histSeries('co2') },
      ]);
    }
  }

  _drawStats() {
    const t1   = this._val('t1');
    const t2   = this._val('t2');
    const flow = this._val('flow');
    const co2  = this._val('co2');
    const hum  = this._val('hum');
    const dp   = this._val('dp');
    const hr   = this._val('heat_recovered');
    const el   = this._val('energy_loss');

    const stats = [
      { label: t('stats', 'indoor_temp'),        value: t1   !== null ? t1.toFixed(1)   + ' °C' : '–', color: COLORS.temp_indoor },
      { label: t('stats', 'outdoor_temp'),        value: t2   !== null ? t2.toFixed(1)   + ' °C' : '–', color: COLORS.temp_outdoor },
      { label: t('stats', 'flow'),            value: flow !== null ? flow.toFixed(0) + ' m³/h' : '–', color: COLORS.flow },
      { label: t('stats', 'co2'),               value: co2  !== null ? co2.toFixed(0)  + ' ppm' : '–', color: co2 !== null ? co2Color(co2) : COLORS.muted },
      { label: t('stats', 'humidity'),       value: hum  !== null ? hum.toFixed(0)  + ' %'   : '–', color: COLORS.accent },
      { label: t('stats', 'dew_point'),          value: dp   !== null ? dp.toFixed(1)   + ' °C'  : '–', color: COLORS.muted },
      { label: t('stats', 'heat_recovery'),value: hr   !== null ? hr.toFixed(0)   + ' W'   : '–', color: COLORS.heat },
      { label: t('stats', 'energy_loss'),    value: el   !== null ? el.toFixed(0)   + ' W'   : '–', color: COLORS.energy },
    ];

    const container = this._shadow.getElementById('stats');
    container.innerHTML = stats.map(s => 
      '<div class="stat">' +
        '<div class="stat-value" style="color:' + s.color + '">' + s.value + '</div>' +
        '<div class="stat-label">' + s.label + '</div>' +
      '</div>'
    ).join('');
  }

  _drawLegend() {
    const legendContainer = this._shadow.getElementById('legend');
    const legendItems = [
      { color: COLORS.co2_good, text: t('legend', 'co2_good') + ' (<1000)' },
      { color: COLORS.co2_moderate, text: t('legend', 'co2_moderate') },
      { color: COLORS.co2_bad, text: t('legend', 'co2_bad') + ' (>1200)' },
      { color: COLORS.flow, text: t('legend', 'flow') },
      { color: COLORS.temp_indoor, text: t('legend', 'indoor_air') },
      { color: COLORS.temp_outdoor, text: t('legend', 'outdoor_air') },
      { color: COLORS.temp_supply, text: t('legend', 'supply_air') },
      { color: COLORS.temp_exhaust, text: t('legend', 'exhaust_air') },
      { color: COLORS.heat, text: t('legend', 'heat_recovery') },
      { color: COLORS.energy, text: t('legend', 'energy_loss') },
      { color: COLORS.pm25, text: t('legend', 'pm25') }
    ];

    legendContainer.innerHTML = legendItems.map(item => 
      '<div class="leg-item">' +
        '<div class="leg-dot" style="background:' + item.color + '"></div>' +
        item.text +
      '</div>'
    ).join('');
  }

  static getStubConfig() {
    return { entities: {} };
  }
}

customElements.define('fresh-r-card', FreshRCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type:        'fresh-r-card',
  name:        'Fresh-r Dashboard',
  description: 'Replicates the fresh-r.me dashboard with radial clock, line charts and stats (multi-language)',
  preview:     true,
});
