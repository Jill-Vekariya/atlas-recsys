import {validateModel, recommend} from "./engine.js";

const $ = id => document.getElementById(id);
const esc = value => String(value).replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[char]));
const title = value => value.charAt(0).toUpperCase() + value.slice(1);
const names = {auto: "Auto", ranked: "Two-tower + ranker", tower: "Two-tower", als: "Implicit ALS", content: "Content", category_popularity: "Category popular", popularity: "Popularity"};
const descriptions = {auto: "Uses the model selected on validation NDCG@10. This synthetic bundle selected ALS.", ranked: "Retrieves with the learned towers, then orders candidates using LightGBM features.", tower: "Projects recent user interests into the learned item embedding space.", als: "Folds your history into the collaborative item factors. Content helps when collaborative signal is absent.", content: "Matches the content embedding to your recent interests, including held-out items.", category_popularity: "Boosts popular items in the categories represented in your recent history.", popularity: "A strong non-personalized baseline based on training-window interaction counts."};
const artwork = {
  audio: {bg:"#213a3b",glow:"#4f747359",ink:"#b3d3c7",path:'<path d="M10 27V20a10 10 0 0 1 20 0v7"/><rect x="7" y="23" width="7" height="12" rx="3"/><rect x="26" y="23" width="7" height="12" rx="3"/>'},
  fitness: {bg:"#38352e",glow:"#96835442",ink:"#dfd1a9",path:'<path d="M13 12v16M9 15v10M27 12v16M31 15v10M13 20h14"/>'},
  books: {bg:"#353046",glow:"#79729448",ink:"#d6c9e9",path:'<path d="M20 12v21M20 15c-4-5-9-4-14-3v20c5-1 10-2 14 2 4-4 9-3 14-2V12c-5-1-10-2-14 3Z"/>'},
  kitchen: {bg:"#3b302c",glow:"#a9755550",ink:"#e5c0a9",path:'<path d="M10 17h19v11a7 7 0 0 1-7 7h-5a7 7 0 0 1-7-7ZM29 20h3a4 4 0 0 1 0 8h-3M15 7v5M21 5v7M27 7v5"/>'},
  outdoors: {bg:"#283c2d",glow:"#7c975c46",ink:"#c9d8a9",path:'<path d="M4 34 17 10l13 24ZM20 16l4-7 12 25H26M12 19l5 4 5-4"/>'},
  gaming: {bg:"#253743",glow:"#6191a548",ink:"#b6d4e4",path:'<path d="M10 16h20l5 15c1 4-3 6-6 3l-5-5h-8l-5 5c-3 3-7 1-6-3ZM13 19v8M9 23h8"/><circle cx="27" cy="21" r="1"/><circle cx="30" cy="25" r="1"/>'},
};
let model, evidence, mode = "existing", preferences = new Set();
let feedback = {};
try {const stored = JSON.parse(localStorage.getItem("atlas.browser.feedback.v1") || "{}"); feedback = stored && typeof stored === "object" && !Array.isArray(stored) ? stored : {};} catch {feedback = {};}

function activateTab(name) {
  if (!["explore", "evidence", "system"].includes(name)) name = "explore";
  for (const id of ["explore", "evidence", "system"]) $(id).hidden = id !== name;
  document.querySelectorAll(".nav").forEach(button => {const selected = button.dataset.tab === name; button.classList.toggle("active", selected); button.setAttribute("aria-pressed", String(selected));});
  if (location.hash !== `#${name}`) history.replaceState(null, "", `#${name}`);
}
document.querySelectorAll(".nav").forEach(button => button.addEventListener("click", () => activateTab(button.dataset.tab)));
window.addEventListener("hashchange", () => activateTab(location.hash.slice(1)));
activateTab(location.hash.slice(1));

function profileKey() {return mode === "new" ? "new-user" : $("profile").value;}
function stateForProfile() {
  const base = mode === "new" ? {positive: [], seen: []} : model.histories[$("profile").value];
  const stored = feedback[profileKey()];
  const events = (Array.isArray(stored) ? stored : []).filter(event => event && Number.isInteger(event.index) && event.index >= 0 && event.index < model.items.length && ["like", "skip"].includes(event.signal));
  return {positive: [...base.positive, ...events.filter(event => event.signal === "like").map(event => event.index)], seen: [...base.seen, ...events.map(event => event.index)]};
}
function historyPreview() {
  if (!model) return;
  const state = stateForProfile(), recent = state.positive.slice(-model.history_size), counts = {};
  for (const index of recent) counts[model.items[index].category] = (counts[model.items[index].category] || 0) + 1;
  const top = Object.entries(counts).sort((a,b) => b[1] - a[1]).slice(0,3);
  $("history-preview").innerHTML = `${state.positive.length} positive interactions · ${new Set(state.seen).size} seen items<br>${top.map(([category]) => `<span class="pill">${esc(title(category))}</span>`).join("")}`;
}
function changeMode(newMode) {
  mode = newMode;
  document.querySelectorAll("[data-mode]").forEach(button => {const selected = button.dataset.mode === mode; button.classList.toggle("selected", selected); button.setAttribute("aria-pressed", String(selected));});
  $("existing-controls").hidden = mode !== "existing";
  $("new-controls").hidden = mode !== "new";
  $("feedback-toast").hidden = true;
  run();
}
document.querySelectorAll("[data-mode]").forEach(button => button.addEventListener("click", () => changeMode(button.dataset.mode)));

function card(item) {
  const art = artwork[item.category] || artwork.audio;
  return `<article class="item-card"><div class="item-art" style="--art-bg:${art.bg};--art-glow:${art.glow};--art-ink:${art.ink}"><span class="rank-number">${String(item.rank).padStart(2,"0")}</span>${item.controlled_cold ? '<span class="cold-badge" title="All item events were withheld from both training windows">HELD OUT</span>' : ""}<svg viewBox="0 0 40 40" aria-hidden="true">${art.path}</svg></div><div class="item-body"><p class="item-category">${esc(item.category)}</p><h3>${esc(title(item.title))}</h3><div class="item-meta"><span>${esc(item.item_id)}</span><span class="score">${item.score.toFixed(3)} score</span></div><div class="item-actions"><button data-like="${item.index}" aria-label="Like ${esc(item.title)}"><span aria-hidden="true">♡</span> Like</button><button data-skip="${item.index}" aria-label="Skip ${esc(item.title)}">Skip <span aria-hidden="true">→</span></button></div><details><summary>Inspect feature signals</summary><dl class="diagnostics"><dt>Content similarity</dt><dd>${item.contentSimilarity.toFixed(4)}</dd><dt>Training positives</dt><dd>${item.popularity}</dd><dt>Controlled cold item</dt><dd>${item.controlled_cold ? "Yes" : "No"}</dd><dt>Retrieval score</dt><dd>${item.retrievalScore.toFixed(4)}</dd>${item.features ? item.features.map((value,i) => `<dt>${esc(model.feature_names[i].replaceAll("_"," "))}</dt><dd>${value.toFixed(4)}</dd>`).join("") : ""}</dl><p class="diagnostic-note">Feature measurements, not a causal explanation or predicted purchase probability.</p></details></div></article>`;
}

function run() {
  if (!model) return;
  try {
    const state = stateForProfile(), algorithm = $("algorithm").value;
    $("algorithm-description").textContent = descriptions[algorithm];
    historyPreview();
    const start = performance.now();
    const result = recommend(model, {userId: profileKey(), history: state.positive, seen: state.seen, preferences: [...preferences], algorithm, candidateCount: Number($("budget").value), category: $("category").value || null, coldOnly: $("cold-only").checked});
    const elapsed = performance.now() - start;
    $("run-stats").hidden = false;
    $("inference-time").textContent = `${elapsed.toFixed(1)} ms`;
    $("effective-model").textContent = names[result.algorithm];
    $("cold-count").textContent = `${result.items.filter(item => item.controlled_cold).length} / ${result.items.length}`;
    $("run-badge").textContent = `${result.candidates} candidates · ${result.historyLength} history`;
    $("fallback-notice").hidden = !result.fallback;
    $("fallback-notice").textContent = result.fallback === "als_no_signal" ? "Content fallback: this profile has no collaborative signal yet. Your selected interests still guide the recommendations." : "Popularity fallback: add preferences or like an item to personalize this new profile.";
    $("recommendations").innerHTML = result.items.length ? result.items.map(card).join("") : '<div class="empty-state"><h3>No eligible items in this selection</h3><p>Try another category or reset this profile’s feedback.</p></div>';
    $("load-error").hidden = true;
  } catch (error) {$("load-error").textContent = `Unable to generate this selection: ${error.message}. Reset this profile or reload the page.`; $("load-error").hidden = false;}
}

function addFeedback(index, signal) {
  const key = profileKey();
  feedback[key] = [...(Array.isArray(feedback[key]) ? feedback[key] : []), {index, signal, at: Date.now()}].slice(-500);
  let saved = true;
  try {localStorage.setItem("atlas.browser.feedback.v1", JSON.stringify(feedback));} catch {saved = false;}
  run();
  $("feedback-toast").textContent = `${signal === "like" ? "Liked" : "Skipped"} ${model.items[index].title}. Session recommendations updated. ${saved ? "Feedback stays in this browser." : "Storage is unavailable; feedback stays in this open session."}`;
  $("feedback-toast").hidden = false;
}
$("recommendations").addEventListener("click", event => {
  const liked = event.target.closest("[data-like]"), skipped = event.target.closest("[data-skip]");
  if (liked) addFeedback(Number(liked.dataset.like), "like");
  if (skipped) addFeedback(Number(skipped.dataset.skip), "skip");
});
$("recommend").addEventListener("click", run);
for (const id of ["profile", "algorithm", "budget", "category", "cold-only"]) $(id).addEventListener("change", run);
$("reset").addEventListener("click", () => {
  if (!model) return;
  delete feedback[profileKey()];
  try {localStorage.setItem("atlas.browser.feedback.v1", JSON.stringify(feedback));} catch {}
  run(); $("feedback-toast").textContent = "Feedback for this profile was reset. The original trained model is unchanged."; $("feedback-toast").hidden = false;
});

function renderEvidence() {
  if (!evidence) return;
  const data = evidence[$("dataset").value];
  const entries = Object.entries(data.results), max = Math.max(...entries.map(([,r]) => r.ndcg_at_10));
  $("dataset-summary").textContent = `${data.catalog_size.toLocaleString()} items · ${data.population.sampled_users} evaluated users · chronological test window`;
  $("quality-chart").innerHTML = entries.map(([name,r]) => `<div class="bar-row ${r.ndcg_at_10 === max ? "best" : ""}"><span>${esc(names[name])}</span><div class="bar-track"><div class="bar-fill" style="width:${r.ndcg_at_10 / max * 100}%"></div></div><span class="bar-value">${r.ndcg_at_10.toFixed(4)}</span></div>`).join("");
  $("quality-table").innerHTML = entries.map(([name,r]) => `<tr class="${r.ndcg_at_10 === max ? "best" : ""}"><td>${esc(names[name])}</td><td>${r.recall_at_100.toFixed(4)}</td><td>${r.ndcg_at_10.toFixed(4)}</td><td>${(r.catalog_coverage_at_10*100).toFixed(2)}%</td><td>${r.controlled_cold_recall_at_100.toFixed(4)}</td></tr>`).join("");
  $("finding").innerHTML = $("dataset").value === "movielens" ? `<strong>The popularity baseline won overall test NDCG@10.</strong> The two-tower model reached some controlled cold items, but that did not establish an overall ranking improvement. This is a measured tradeoff, not an assumed win for a more complex model.` : `<strong>This Amazon sample is too sparse for a strong personalization conclusion.</strong> The full reports retain label sparsity, ranker-training counts, and model comparisons. Treat this as a protocol and engineering experiment, not evidence of business lift.`;
  const load = evidence.http_load;
  $("benchmark-context").textContent = `${load.requests} measured requests over ${load.requested_duration_seconds} seconds; ${load.catalog_size.toLocaleString()} MovieLens items; ${load.user_mix}. Local CPU host, one API worker. These are not GitHub Pages latency measurements.`;
  $("benchmark-stats").innerHTML = `<div><strong>${load.p95_ms.toFixed(1)}<small> ms</small></strong><span>local HTTP p95</span></div><div><strong>${load.achieved_rps.toFixed(1)}</strong><span>achieved requests/sec</span></div><div><strong>${(load.error_rate*100).toFixed(0)}%</strong><span>error rate</span></div>`;
}
$("dataset").addEventListener("change", renderEvidence);

async function init() {
  try {
    const [modelResponse, evidenceResponse] = await Promise.all([fetch(new URL("./model.json", import.meta.url)), fetch(new URL("./evidence.json", import.meta.url))]);
    if (!modelResponse.ok || !evidenceResponse.ok) throw new Error("The model files did not load");
    model = validateModel(await modelResponse.json());
    evidence = await evidenceResponse.json();
    const users = Object.keys(model.histories).filter(id => model.histories[id].positive.length).sort();
    $("profile").innerHTML = users.map(id => `<option value="${esc(id)}">Profile ${esc(id.split("-").at(-1))}</option>`).join("");
    const categories = [...new Set(model.items.map(item => item.category))].sort();
    $("category").innerHTML = '<option value="">All categories</option>' + categories.map(category => `<option value="${esc(category)}">${esc(title(category))}</option>`).join("");
    $("preferences").innerHTML = categories.map(category => `<button class="preference" data-preference="${esc(category)}" aria-pressed="false">${esc(title(category))}</button>`).join("");
    $("preferences").addEventListener("click", event => {const button = event.target.closest("[data-preference]"); if (!button) return; const category = button.dataset.preference; if (preferences.has(category)) preferences.delete(category); else preferences.add(category); const selected = preferences.has(category); button.classList.toggle("selected", selected); button.setAttribute("aria-pressed", String(selected)); run();});
    $("profile").disabled = false; $("algorithm").disabled = false; $("recommend").disabled = false;
    $("catalog-count").innerHTML = `${model.items.length}<span>items to explore</span>`;
    $("profile-count").textContent = users.length; $("tree-count").textContent = model.trees.length;
    $("model-status").textContent = "Model ready · browser inference"; $("status-dot").classList.add("ready");
    $("provenance").innerHTML = `<dt>Bundle version</dt><dd>${esc(model.version)}</dd><dt>Bundle manifest SHA-256</dt><dd>${esc(model.source_bundle_sha256)}</dd><dt>Content / retrieval dimensions</dt><dd>${model.content[0].length} / ${model.vectors[0].length}</dd><dt>Validation-selected default</dt><dd>${esc(names[model.default_algorithm])}</dd><dt>Catalog / profiles</dt><dd>${model.items.length} / ${users.length} · synthetic only</dd><dt>Feedback storage</dt><dd>Browser local storage · no central collection</dd>`;
    renderEvidence(); run();
  } catch (error) {$("model-status").textContent = "Model unavailable"; $("load-error").textContent = `${error.message}. Reload this page or open the repository for source and reports.`; $("load-error").hidden = false; $("recommendations").innerHTML = '<div class="empty-state"><h3>The bundle could not load</h3><p>Reload the page to retry. The permanent GitHub source link remains available.</p></div>';}
}
init();
