// Loaded only with ?selftest=1 on the compare page: scripts/e2e.sh reads <body data-selftest="...">.
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
export async function run() {
  const log = [];
  try {
    const countries = await (await fetch(new URL("../data/countries.json", import.meta.url))).json();
    const pick = [countries[0], countries[Math.floor(countries.length / 2)], countries.at(-1)].map((c) => c.slug);
    const selects = document.querySelectorAll("#compare select");
    pick.forEach((slug, i) => { selects[i].value = slug; });
    selects[0].dispatchEvent(new Event("change", { bubbles: true }));
    const out = document.getElementById("compare-chart");
    const t0 = Date.now();
    while (out.dataset.drawn !== "3" && Date.now() - t0 < 8000) await wait(25);
    if (out.dataset.drawn !== "3") throw new Error("comparison chart did not draw three countries");
    if (out.querySelectorAll("polyline").length !== 3) throw new Error("expected three lines");
    if (!location.search.includes("c=" + pick.join("%2C")) && !location.search.includes("c=" + pick.join(","))) throw new Error("URL does not keep the choice: " + location.search);
    log.push(`compare: ${pick.join(", ")} drawn and kept in the URL`);
    const page = await (await fetch(new URL(`../countries/${pick[1]}/`, location.href))).text();
    const doc = new DOMParser().parseFromString(page, "text/html");
    if (!doc.querySelector("svg.chart polyline")) throw new Error("country page has no chart");
    if (!/CC BY-SA 4\.0/.test(doc.body.textContent) || !/not endorsed by V-Dem/.test(doc.body.textContent)) throw new Error("country page lacks V-Dem attribution");
    log.push(`country page ${pick[1]}: chart and V-Dem attribution present`);
    document.body.dataset.selftest = "pass";
  } catch (err) {
    log.push("FAIL: " + err.message);
    document.body.dataset.selftest = "fail: " + err.message;
  }
  const pre = document.createElement("pre");
  pre.id = "selftest";
  pre.textContent = log.join("\n");
  document.body.appendChild(pre);
}
