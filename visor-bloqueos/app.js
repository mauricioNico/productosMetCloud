"use strict";
const base =
  "https://raw.githubusercontent.com/mauricioNico/productosMetCloud/datos-bloqueos/";
const regions = [
  ["PSW", "Pacífico sudoeste", -180, -120],
  ["PSE", "Pacífico sudeste", -120, -80],
  ["ATL", "Atlántico Sur", -80, 10],
  ["IND", "Océano Índico", 10, 100],
  ["OCN", "Oceanía", 100, 180],
];
const views = [
  ["sinoptico", "Dominio sinóptico · 110° O a 20° O", -110, -20],
  ["all", "Hemisferio Sur", -180, 180],
  ...regions,
];
const colors = ["#e1ebef", "#efb547", "#16988c", "#86448b", "#788793"];
const legends = [
  "Sin señal",
  "Señal local",
  "Continuidad espacial",
  "Persistencia prevista",
  "Sin datos",
];
const deltas = [0, -2.5, -5, -7.5, -10];
const $ = (id) => document.getElementById(id);
const lonAt = (j) => -180 + 2.5 * j;
const lonText = (x) => Math.abs(x).toLocaleString("es-AR") + "°" + (x < 0 ? " O" : x > 0 ? " E" : "");
const utc = (t) => t.slice(0, 16).replace("T", " ");
const fmt = (n) =>
  n.toLocaleString("es-AR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
let catalog,
  land,
  models = [],
  records = [],
  products = [],
  validities = [],
  generation = 0;
const element = (tag, content = "") =>
  Object.assign(document.createElement(tag), { textContent: content });
function options(select, pairs, preferred = select.value) {
  select.replaceChildren(
    ...pairs.map(([value, label]) => new Option(label, value)),
  );
  if ([...select.options].some((o) => o.value === String(preferred)))
    select.value = preferred;
}
function label(parent, title, id) {
  const node = element("label", title),
    select = element("select");
  select.id = id;
  node.append(select);
  parent.append(node);
  return select;
}
function detail(grid, j, d) {
  const z = [40, 55, 50, 65].map((lat) => grid[(lat + d - 30) / 2.5][j]);
  const n = z[1] - z[0],
    s = z[3] - z[2];
  return { z, n, s, pass: n > 0 && s < -10 };
}
function classify(grid) {
  const flags = Array.from({ length: 144 }, (_, j) =>
    Number(deltas.some((d) => detail(grid, j, d).pass)),
  );
  const spans = [];
  for (const [region, , west, east] of regions) {
    const end = (east + 180) / 2.5;
    for (let j = (west + 180) / 2.5; j < end;) {
      if (!flags[j]) {
        j++;
        continue;
      }
      const start = j;
      while (j < end && flags[j] === 1) j++;
      if (j - start >= 3) {
        flags.fill(2, start, j);
        spans.push({ region, start, end: j - 1 });
      }
    }
  }
  return { grid, flags, spans };
}
function prepare(data) {
  for (const mode of ["instant", "daily"]) {
    data[mode] = Object.fromEntries(
      Object.entries(data[mode]).map(([t, g]) => [t, classify(g)]),
    );
  }
  // Dos pasadas marcan cada segmento que participa en una trayectoria de cinco días.
  const days = Object.keys(data.daily).sort();
  for (const direction of [1, -1]) {
    const key = direction === 1 ? "before" : "after";
    let previous = [],
      last;
    for (const day of direction === 1 ? days : [...days].reverse()) {
      if (Math.abs(Date.parse(day) - last) !== 86400000) previous = [];
      const spans = data.daily[day].spans;
      for (const s of spans) {
        const linked = previous.filter(
          (p) => p.region === s.region && p.start <= s.end && s.start <= p.end,
        );
        s[key] = 1 + Math.max(0, ...linked.map((p) => p[key]));
      }
      previous = spans;
      last = Date.parse(day);
    }
  }
  for (const frame of Object.values(data.daily)) {
    for (const s of frame.spans)
      if (s.before + s.after - 1 >= 5) frame.flags.fill(3, s.start, s.end + 1);
  }
  return data;
}
async function request(url) {
  const resp = await fetch(url, { cache: "no-cache" });
  if (!resp.ok) throw Error("HTTP " + resp.status);
  return resp;
}
async function loadRecord(r) {
  const resp = await request(base + r.file + "?v=" + r.job);
  const stream = resp.body.pipeThrough(new DecompressionStream("gzip"));
  const data = await new Response(stream).json();
  if (data.run !== r.run || data.model !== r.model)
    throw Error("Corrida incompatible con catálogo");
  return prepare(data);
}
function setCycles() {
  models = $("model").value.split("+");
  $("cycles").replaceChildren();
  for (const m of models) {
    const runs = catalog.runs.filter((r) => r.model === m);
    const day = label($("cycles"), m + " · inicialización", m + "day");
    const hour = label($("cycles"), m + " · hora UTC", m + "hour");
    options(
      day,
      [...new Set(runs.map((r) => r.run.slice(0, 10)))].map((t) => [t, t]),
    );
    const hours = () =>
      options(
        hour,
        runs
          .filter((r) => r.run.startsWith(day.value))
          .map((r) => [r.run, r.run.slice(11, 16)]),
      );
    hours();
    day.onchange = () => {
      hours();
      changeRuns();
    };
    hour.onchange = changeRuns;
  }
  changeRuns();
}
async function changeRuns() {
  const version = ++generation;
  $("result").hidden = true;
  $("notice").textContent = "Cargando campos de altura geopotencial…";
  records = models.map((m) =>
    catalog.runs.find((r) => r.model === m && r.run === $(m + "hour").value),
  );
  try {
    const result = await Promise.all(records.map(loadRecord));
    if (version !== generation) return;
    products = result;
    options(
      $("mode"),
      [
        ["instant", "Instantáneo"],
        ["daily", "Media diaria UTC"],
      ].filter(([mode]) =>
        Object.keys(result[0][mode]).some((t) =>
          result.every((p) => p[mode][t]),
        ),
      ),
    );
    changeMode();
  } catch (e) {
    if (version === generation)
      $("notice").textContent = "No se pudo cargar la selección. " + e.message;
  }
}
function applyType() {
  const type = $("type").value;
  return validities.filter(
    (t) =>
      type === "all" ||
      records.every((r) =>
        type === "initial"
          ? Date.parse(t) === Date.parse(r.run)
          : Date.parse(t) > Date.parse(r.run),
      ),
  );
}
function changeMode() {
  const mode = $("mode").value;
  validities = mode
    ? Object.keys(products[0][mode])
        .filter((t) => products.every((p) => p[mode][t]))
        .sort()
    : [];
  $("type").parentNode.hidden = mode !== "instant";
  const types = [
    ["all", "Todos"],
    ["initial", "Campo inicial (+0 h)"],
    ["forecast", "Pronóstico (>0 h)"],
  ];
  options(
    $("type"),
    types.filter(
      ([type]) =>
        type === "all" ||
        validities.some((t) =>
          records.every((r) =>
            type === "initial"
              ? Date.parse(t) === Date.parse(r.run)
              : Date.parse(t) > Date.parse(r.run),
          ),
        ),
    ),
  );
  if (mode === "instant") validities = applyType();
  options(
    $("valid"),
    validities.map((t) => [t, utc(t)]),
  );
  options(
    $("step"),
    mode === "instant"
      ? validities.map((t) => [
          t,
          records
            .map(
              (r) =>
                r.model +
                " +" +
                (Date.parse(t) - Date.parse(r.run)) / 3600000 +
                " h",
            )
            .join(" / "),
        ])
      : [],
  );
  $("step").parentNode.hidden = mode !== "instant";
  $("notice").textContent = validities.length
    ? ""
    : "No hay una validez común para estas inicializaciones.";
  $("result").hidden = !validities.length;
  if (validities.length) render();
}
function bounds() {
  return views.find((v) => v[0] === $("region").value).slice(2);
}
function lastLongitude(east) {
  return $("region").value === "sinoptico" ? east : east - 2.5;
}
function changeRegion() {
  const [a, b] = bounds(),
    old = $("lon").value || "-60";
  options(
    $("lon"),
    Array.from({ length: 1 + (lastLongitude(b) - a) / 2.5 }, (_, i) => [
      a + i * 2.5,
      lonText(a + i * 2.5),
    ]),
    old,
  );
  if (validities.length) render();
}
function canvas(parent, height, label) {
  const c = element("canvas");
  c.className = "plot";
  c.setAttribute("aria-label", label);
  parent.append(c);
  const width = Math.max(1, c.clientWidth),
    ratio = window.devicePixelRatio || 1;
  c.style.height = height + "px";
  c.width = Math.round(width * ratio);
  c.height = Math.round(height * ratio);
  const ctx = c.getContext("2d");
  ctx.scale(ratio, ratio);
  ctx.font = "11px system-ui";
  return { c, ctx, width, height };
}
function contour(ctx, grid, x, y, west, east) {
  ctx.strokeStyle = "#233c52";
  ctx.lineWidth = 1.1;
  ctx.globalAlpha = 0.95;
  ctx.beginPath();
  for (let j = (west + 180) / 2.5; j < (east + 180) / 2.5; j++) {
    for (let i = 0; i < 14; i++) {
      const next = (j + 1) % 144,
        X = lonAt(j),
        Y = -30 - i * 2.5;
      const a = [X, Y, grid[i][j]],
        b = [X + 2.5, Y, grid[i][next]],
        c = [X + 2.5, Y - 2.5, grid[i + 1][next]],
        d = [X, Y - 2.5, grid[i + 1][j]];
      for (const tri of [
        [a, b, c],
        [a, c, d],
      ]) {
        const zs = tri.map((p) => p[2]);
        for (
          let level = Math.ceil(Math.min(...zs) / 60) * 60;
          level <= Math.max(...zs);
          level += 60
        ) {
          const points = [];
          tri.forEach((p, k) => {
            const q = tri[(k + 1) % 3];
            if (p[2] < level !== q[2] < level) {
              const f = (level - p[2]) / (q[2] - p[2]);
              points.push([
                x(p[0] + f * (q[0] - p[0])),
                y(p[1] + f * (q[1] - p[1])),
              ]);
            }
          });
          if (points.length === 2) {
            ctx.moveTo(...points[0]);
            ctx.lineTo(...points[1]);
          }
        }
      }
    }
  }
  ctx.stroke();
  ctx.globalAlpha = 1;
}
function map(parent, frame) {
  const [west, east] = bounds();
  const mapWidth = Math.max(1, parent.clientWidth);
  const { c, ctx, width, height } = canvas(parent, 35 + mapWidth * 35 / (east - west), "Mapa de meridianos y Z500");
  c.classList.add("map-plot");
  const x = (lon) => ((lon - west) / (east - west)) * width,
    y = (lat) => 15 + ((-30 - lat) / 35) * (height - 35);
  ctx.fillStyle = "#a9d8ef"; ctx.fillRect(0,0,width,height);
  ctx.save(); ctx.beginPath(); ctx.rect(0,y(-30),width,y(-65)-y(-30)); ctx.clip();
  for (let j = 0; j < 144; j++) {
    if (frame.flags[j] === 0) continue;
    ctx.globalAlpha = 0.38;
    ctx.fillStyle = colors[frame.flags[j]];
    ctx.fillRect(
      x(lonAt(j) - 1.25),
      y(-30),
      (width * 2.5) / (east - west) + 0.4,
      y(-65) - y(-30),
    );
  }
  ctx.globalAlpha = 1;
  ctx.fillStyle = "#d8b58b";
  ctx.strokeStyle = "#795b40";
  ctx.lineWidth = 0.8;
  for (const ring of land) {
    ctx.beginPath();
    ring.forEach(([lon, lat], i) =>
      i ? ctx.lineTo(x(lon), y(lat)) : ctx.moveTo(x(lon), y(lat)),
    );
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
  }
  ctx.save();
  ctx.strokeStyle = "#607d8b"; ctx.globalAlpha = .25; ctx.lineWidth = .6;
  ctx.beginPath();
  for(let l = Math.ceil(west / 15)*15; l <= east; l += 15){ctx.moveTo(x(l),y(-30));ctx.lineTo(x(l),y(-65));}
  for(let l = -30; l >= -65; l -= 5){ctx.moveTo(x(west),y(l));ctx.lineTo(x(east),y(l));}
  ctx.stroke(); ctx.restore();
  contour(ctx, frame.grid, x, y, west, east);
  ctx.restore();
  for (let j = (west + 180) / 2.5; j <= (lastLongitude(east) + 180) / 2.5; j++) {
    ctx.fillStyle = colors[frame.flags[j]];
    ctx.fillRect(
      x(lonAt(j) - 1.25),
      0,
      (2.5 * width) / (east - west) + 0.5,
      10,
    );
  }
  ctx.strokeStyle = "#153145";
  ctx.setLineDash([5, 3]);
  const selected = x(+$("lon").value);
  ctx.beginPath();
  ctx.moveTo(selected, 0);
  ctx.lineTo(selected, height - 16);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = "#153145";
  for (const lat of [-30, -50, -65])
    ctx.fillText(Math.abs(lat) + "° S", 5, y(lat) + (lat === -30 ? 12 : -3));
  for (let i = 0; i <= 4; i++) {
    ctx.textAlign = i === 4 ? "right" : "left";
    const l = west + (i * (east - west)) / 4;
    ctx.fillText(lonText(l), x(l) + (i === 4 ? -2 : 2), height - 3);
  }
  c.onclick = (e) => { const rect = c.getBoundingClientRect(); pick(west + (east - west) * (e.clientX - rect.left) / rect.width); };
}
function pick(lon) {
  const [a, b] = bounds();
  $("lon").value = Math.max(a, Math.min(lastLongitude(b), Math.round(lon / 2.5) * 2.5));
  $("notice").textContent = "";
  render();
}
function selectTime(time) {
  if (!validities.includes(time)) {
    $("notice").textContent = "La hora elegida carece de campos para esta selección.";
    return;
  }
  $("valid").value = time;
  $("notice").textContent = "";
  render();
}
function timeTable(mode, selected, j) {
  $("timeLongitude").textContent = lonText(lonAt(j));
  const head = element("tr");
  for (const title of ["Validez UTC", ...models]) head.append(element("th", title));
  $("timesHead").replaceChildren(head);
  const rows = validities.map((time) => {
    const row = element("tr");
    const date = time.slice(0, 10).split("-").reverse().join("/");
    const button = element("button", date + (mode === "instant" ? " · " + time.slice(11, 16) : ""));
    button.type = "button";
    button.value = time;
    button.setAttribute("aria-pressed", String(time === selected));
    row.classList.toggle("active-time", time === selected);
    row.insertCell().append(button);
    for (const data of products) {
      const cell = row.insertCell();
      if (mode === "instant") {
        const hours = (Date.parse(time) - Date.parse(data.run)) / 3600000;
        cell.append(element("strong", "+" + hours + " h "));
      }
      const flag = data[mode][time].flags[j];
      const signal = element("span", legends[flag]);
      signal.style.setProperty("--signal", colors[flag]);
      cell.append(signal);
    }
    row.onclick = () => {
      const hadFocus = document.activeElement === button;
      selectTime(time);
      if (hadFocus) $("timesBody").querySelector('[aria-pressed="true"]').focus({preventScroll: true});
    };
    return row;
  });
  $("timesBody").replaceChildren(...rows);
}
function hov(parent, data) {
  const [west, east] = bounds(),
    mode = $("mode").value,
    inst = mode === "instant";
  const dates = inst
    ? data.expected.map((s) =>
        new Date(Date.parse(data.run) + s * 3600000)
          .toISOString()
          .replace(".000Z", "+00:00"),
      )
    : [
        ...new Set(
          data.expected.map((s) =>
            new Date(Date.parse(data.run) + s * 3600000)
              .toISOString()
              .slice(0, 10),
          ),
        ),
      ];
  dates.sort().reverse();
  const row = 16,
    left = 110,
    top = 4;
  const { c, ctx, width, height } = canvas(
    parent,
    top + row * dates.length + 18,
    "Hovmöller de señales por validez UTC",
  );
  const last = lastLongitude(east);
  const dx = (width - left) / (1 + (last - west) / 2.5);
  dates.forEach((t, i) => {
    ctx.fillStyle = "#243f50";
    ctx.fillText(utc(t).replace(/^\d{4}-/, ""), 3, top + i * row + 12);
    for (let j = (west + 180) / 2.5; j <= (lastLongitude(east) + 180) / 2.5; j++) {
      const xx = left + ((lonAt(j) - west) / 2.5) * dx,
        yy = top + i * row;
      ctx.fillStyle = colors[data[mode][t]?.flags[j] ?? 4];
      ctx.fillRect(xx, yy, dx + 0.1, row - 1);
      if (t === $("valid").value && lonAt(j) === +$("lon").value) {
        ctx.strokeStyle = "#162d40";
        ctx.strokeRect(xx, yy, dx, row - 1);
      }
    }
  });
  ctx.fillStyle = "#243f50";
  for (let i = 0; i <= 4; i++) {
    const col = Math.round(((last - west) * i) / (2.5 * 4));
    ctx.textAlign = i === 4 ? "right" : "left";
    ctx.fillText(lonText(west + col * 2.5), left + (col + 0.5) * dx, height - 2);
  }
  c.onclick = (e) => {
    const i = Math.floor((e.offsetY - top) / row);
    if (dates[i]) selectTime(dates[i]);
  };
}
function table(parent, frame, j) {
  const scroll = element("div");
  scroll.className = "scroll";
  const grid = element("table");
  const head = grid.createTHead().insertRow();
  for (const title of [
    "Δ",
    "Latitudes N / 01 / 02 / S (° S)",
    "ZN (dam)",
    "Z01",
    "Z02",
    "ZS",
    "GHGN (m)",
    "> 0",
    "GHGS (m)",
    "< −10",
    "Señal",
  ]) {
    head.append(element("th", title));
  }
  const body = grid.createTBody();
  for (const d of deltas) {
    const v = detail(frame.grid, j, d),
      row = body.insertRow();
    if (v.pass) row.className = "pass";
    for (const value of [
      d + "°",
      [40, 55, 50, 65].map((l) => l + d).join(" / "),
      ...v.z.map((z) => fmt(z / 10)),
      fmt(v.n),
      v.n > 0 ? "Sí" : "No",
      fmt(v.s),
      v.s < -10 ? "Sí" : "No",
      v.pass ? "Sí" : "No",
    ])
      row.insertCell().textContent = value;
  }
  scroll.append(grid);
  parent.append(scroll);
}
function render() {
  const mode = $("mode").value,
    time = $("valid").value,
    j = (+$("lon").value + 180) / 2.5;
  $("step").value = time;
  for (const id of ["maps", "hov", "details"]) $(id).replaceChildren();
  $("selection").textContent =
    lonText(lonAt(j)) +
    " · " +
    utc(time) +
    " UTC · " +
    $("mode").selectedOptions[0].text;
  timeTable(mode, time, j);
  const states = [];
  products.forEach((data, i) => {
    const frame = data[mode][time],
      step = (Date.parse(time) - Date.parse(data.run)) / 3600000;
    const title =
      data.model +
      " · corrida " +
      utc(data.run) +
      " UTC · " +
      (mode === "daily"
        ? "media diaria prevista"
        : step
          ? "pronóstico +" + step + " h"
          : "campo inicial +0 h");
    for (const id of ["maps", "details"])
      $(id).append(element("h3", title));
    map($("maps"), frame);
    if ($("showHov").open) {
      $("hov").append(element("h3", title));
      hov($("hov"), data);
    }
    table($("details"), frame, j);
    const [west, east] = bounds();
    const spans = frame.spans.filter(
      (s) => lonAt(s.end) >= west && lonAt(s.start) <= lastLongitude(east),
    );
    $("details").append(
      element(
        "p",
        "Sectores continuos: " +
          (spans
            .map(
              (s) =>
                s.region +
                " " +
                lonText(lonAt(s.start)) +
                " a " +
                lonText(lonAt(s.end)) +
                " (" +
                (s.end - s.start + 1) +
                " meridianos)" +
                (frame.flags[s.start] === 3 ? " · persistente" : ""),
            )
            .join(" · ") || "ninguno") +
          ".",
      ),
    );
    states.push({
      flag: frame.flags[j],
      deltas:
        deltas.filter((d) => detail(frame.grid, j, d).pass).join(", ") ||
        "ninguno",
    });
  });
  $("agreement").textContent =
    states.length === 2
      ? (states[0].flag === states[1].flag ? "Coincidencia" : "Discrepancia") +
        " en el meridiano. " +
        states
          .map(
            (s, i) =>
              models[i] + ": " + legends[s.flag] + " (Δ: " + s.deltas + ").",
          )
          .join(" ")
      : legends[states[0].flag];
}
async function start() {
  try {
    [catalog, land] = await Promise.all([
      request(base + "catalog.json").then((r) => r.json()),
      request("tierra.json").then((r) => r.json()),
    ]);
    $("updated").textContent =
      "Última actualización del catálogo · " + utc(catalog.updated) + " UTC";
    for (const m of ["GFS", "ECMWF"]) {
      const r = catalog.runs.find((r) => r.model === m),
        state = catalog.status[m]?.state || "sin información";
      const node = element("article");
      node.className = "card";
      node.append(
        element("strong", m),
        element(
          "span",
          r ? "Corrida " + utc(r.run) + " UTC" : "Sin corrida disponible",
        ),
      );
      const age = r && Date.now() - Date.parse(r.run) > 86400000;
      const status = element(
        "small",
        state +
          (r
            ? " · " +
              r.steps.length +
              " campos · horizonte +" +
              Math.max(...r.steps) +
              " h"
            : "") +
          (age ? " · corrida desactualizada" : "") +
          (r?.missing.length
            ? " · faltan +" + r.missing.join(", +") + " h"
            : ""),
      );
      if (age || state !== "completo") status.className = "warn";
      node.append(status);
      $("status").append(node);
    }
    const available = ["GFS", "ECMWF"].filter((m) =>
      catalog.runs.some((r) => r.model === m),
    );
    if (!available.length) throw Error("Sin corridas válidas publicadas.");
    const choices = available.map((m) => [m, m]);
    if (available.length === 2)
      choices.push(["GFS+ECMWF", "Comparar GFS y ECMWF"]);
    options($("model"), choices);
    options(
      $("region"),
      views.map((v) => v.slice(0, 2)),
      "sinoptico",
    );
    changeRegion();
    const explanations = [
      "Ninguno de los cinco desplazamientos Δ cumple simultáneamente GHGN > 0 m y GHGS < −10 m.",
      "Al menos un desplazamiento Δ cumple ambas condiciones en el meridiano analizado.",
      "Al menos tres meridianos consecutivos, separados por 2,5°, presentan señal dentro de una misma región.",
      "En medias diarias, continuidad durante al menos cinco días consecutivos de una corrida, con solapamiento longitudinal entre días. No confirma un bloqueo mediante análisis.",
      "Información insuficiente para el diagnóstico; no equivale a ausencia de bloqueo."
    ];
    for (const key of document.querySelectorAll(".key")) {
      const guide = element("details");
      guide.className = "signal-guide";
      guide.open = true;
      guide.append(element("summary", "Cómo interpretar los indicadores de bloqueo"));
      const list = element("dl");
      legends.forEach((t, i) => {
        const s = element("span", t);
        s.style.setProperty("--c", colors[i]);
        key.append(s);
        const term = element("dt", t);
        term.style.setProperty("--c", colors[i]);
        list.append(term, element("dd", explanations[i]));
      });
      guide.append(list);
      key.after(guide);
    }
    $("type").onchange = changeMode;
    $("showHov").ontoggle = () => { if (!$("result").hidden) render(); };
    $("model").onchange = setCycles;
    $("mode").onchange = changeMode;
    $("region").onchange = changeRegion;
    $("valid").onchange = $("lon").onchange = render;
    $("step").onchange = () => {
      $("valid").value = $("step").value;
      render();
    };
    setCycles();
    let timer;
    window.addEventListener("resize", () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        if (!$("result").hidden) render();
      }, 120);
    });
  } catch (e) {
    $("notice").textContent =
      "No se pudo abrir el catálogo o la cartografía. " + e.message;
  }
}
start();
