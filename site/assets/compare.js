// Compare up to three countries' scores since 1900. Loads small per-country JSON files; the URL keeps the choice.
const form = document.getElementById("compare");
const out = document.getElementById("compare-chart");
const base = new URL("../", import.meta.url);
const cache = new Map();
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

async function load(slug) {
  if (!cache.has(slug)) cache.set(slug, fetch(new URL(`data/countries/${slug}.json`, base)).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }));
  return (await cache.get(slug)).country;
}

export function lines(countries, width = 720, height = 280) {
  const pl = 34, pr = 10, pt = 10, pb = 26;
  const y1 = Math.max(...countries.flatMap((c) => c.history.map((p) => p.year)));
  const sx = (y) => pl + ((y - 1900) / Math.max(1, y1 - 1900)) * (width - pl - pr);
  const sy = (v) => pt + (1 - v / 100) * (height - pt - pb);
  let svg = "";
  for (const v of [0, 25, 50, 75, 100]) svg += `<line class="grid" x1="${pl}" x2="${width - pr}" y1="${sy(v)}" y2="${sy(v)}"/><text class="ax" x="${pl - 6}" y="${sy(v) + 4}">${v}</text>`;
  for (let y = 1900; y <= y1; y += 25) svg += `<text class="ax" x="${sx(y)}" y="${height - 6}" text-anchor="middle">${y}</text>`;
  countries.forEach((c, i) => {
    const pts = c.history.map((p) => `${sx(p.year).toFixed(1)},${sy(p.score).toFixed(1)}`).join(" ");
    svg += `<polyline class="line l${i + 1}" points="${pts}"/>`;
  });
  return `<svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Democracys Score by year: ${esc(countries.map((c) => c.name).join(", "))}">${svg}</svg>`;
}

async function draw() {
  const slugs = [...form.querySelectorAll("select")].map((s) => s.value).filter(Boolean);
  const url = new URL(location.href);
  if (slugs.length) url.searchParams.set("c", slugs.join(",")); else url.searchParams.delete("c");
  history.replaceState(null, "", url);
  if (!slugs.length) { out.innerHTML = ""; return; }
  try {
    const countries = await Promise.all(slugs.map(load));
    const colors = ["#245fa8", "#b4561f", "#1f7a52"];
    out.innerHTML = lines(countries) + `<p class="legend">${countries.map((c, i) => `<span><i style="background:${colors[i]}"></i><a href="../countries/${esc(c.slug)}/">${esc(c.name)}</a> ${c.latest.score.toFixed(1)}</span>`).join("")}</p>`;
    out.dataset.drawn = String(countries.length);
  } catch (err) {
    out.textContent = "Could not load that country's data. Please try again.";
  }
}

if (form) {
  form.addEventListener("change", draw);
  const pre = (new URLSearchParams(location.search).get("c") || "").split(",").filter(Boolean).slice(0, 3);
  pre.forEach((slug, i) => { const s = form.querySelector(`select[name="c${i + 1}"]`); if (s) s.value = slug; });
  if (pre.length) draw();
  if (new URLSearchParams(location.search).has("selftest")) import("./selftest.js").then((m) => m.run());
}
