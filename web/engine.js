// Portable inference for the public synthetic bundle. Training remains in Python.
export const FEATURES = ["retrieval_similarity", "content_similarity", "category_affinity", "log_popularity", "log_history_length", "recent_content_similarity"];
export const ALGORITHMS = ["auto", "ranked", "tower", "als", "content", "category_popularity", "popularity"];
const f32 = Math.fround;
const dot = (a, b) => f32(a.reduce((sum, value, i) => sum + value * b[i], 0));

export function validateModel(model) {
  if (model.schema_version !== 1 || model.synthetic !== true) throw new Error("Unsupported public model bundle");
  if (JSON.stringify(model.feature_names) !== JSON.stringify(FEATURES)) throw new Error("Feature schema mismatch");
  const n = model.items.length;
  for (const key of ["content", "vectors", "als_factors", "popularity"]) {
    if (model[key].length !== n || !model[key].flat().every(Number.isFinite)) throw new Error(`Invalid ${key}`);
  }
  if (new Set(model.items.map(item => item.item_id)).size !== n) throw new Error("Duplicate catalog IDs");
  if (!ALGORITHMS.includes(model.default_algorithm)) throw new Error("Unknown default algorithm");
  if (model.content.some(row => row.length !== model.content[0].length) || model.vectors.some(row => row.length !== model.vectors[0].length)) throw new Error("Inconsistent embedding dimensions");
  if (model.user_weights.length !== model.vectors[0].length || model.user_weights.some(row => row.length !== model.content[0].length || !row.every(Number.isFinite))) throw new Error("Invalid user projection");
  const alsDim = model.als_factors[0].length;
  if (model.als_factors.some(row => row.length !== alsDim) || model.als_gram.length !== alsDim || model.als_gram.some(row => row.length !== alsDim || !row.every(Number.isFinite))) throw new Error("Invalid collaborative factors");
  for (const profile of Object.values(model.histories)) for (const key of ["positive", "seen"]) if (!Array.isArray(profile[key]) || profile[key].some(id => !Number.isInteger(id) || id < 0 || id >= n)) throw new Error("Invalid profile history");
  return model;
}

export function context(model, history, recency = true) {
  const chosen = history.slice(-model.history_size);
  const output = Array(model.content[0].length).fill(0);
  if (!chosen.length) return output;
  const weights = chosen.map((_, i) => recency ? Math.exp(chosen.length === 1 ? -1 : -1 + i / (chosen.length - 1)) : 1);
  const total = weights.reduce((a, b) => a + b, 0);
  for (let d = 0; d < output.length; d++) output[d] = f32(chosen.reduce((sum, id, j) => sum + model.content[id][d] * weights[j], 0) / total);
  return output;
}

function normalize(vector) {
  const norm = Math.max(f32(Math.sqrt(f32(vector.reduce((sum, v) => sum + v * v, 0)))), 1e-9);
  return vector.map(value => f32(value / norm));
}

export function queryVector(model, history) {
  const ctx = context(model, history);
  return normalize(model.user_weights.map(row => dot(row, ctx)));
}

// Solve the regularized ALS system with pivoted elimination. No model fitting occurs here.
function solve(system, rhs) {
  const n = rhs.length, a = system.map((row, i) => [...row, rhs[i]]);
  for (let column = 0; column < n; column++) {
    let pivot = column;
    for (let i = column + 1; i < n; i++) if (Math.abs(a[i][column]) > Math.abs(a[pivot][column])) pivot = i;
    [a[column], a[pivot]] = [a[pivot], a[column]];
    if (Math.abs(a[column][column]) < 1e-12) throw new Error("Singular ALS system");
    for (let i = column + 1; i < n; i++) {
      const ratio = a[i][column] / a[column][column];
      for (let j = column + 1; j <= n; j++) a[i][j] -= ratio * a[column][j];
      a[i][column] = 0;
    }
  }
  const x = Array(n).fill(0);
  for (let i = n - 1; i >= 0; i--) {
    let value = a[i][n];
    for (let j = i + 1; j < n; j++) value -= a[i][j] * x[j];
    x[i] = value / a[i][i];
  }
  return x.map(f32);
}

export function alsQuery(model, history) {
  const dim = model.als_factors[0].length;
  if (!history.length) return Array(dim).fill(0);
  const counts = new Map();
  for (const id of history) counts.set(id, (counts.get(id) || 0) + 1);
  const ids = [...counts.keys()].sort((a, b) => a - b);
  const system = model.als_gram.map(row => [...row]);
  const rhs = Array(dim).fill(0);
  for (let i = 0; i < dim; i++) {
    rhs[i] = f32(ids.reduce((sum, id) => sum + model.als_factors[id][i] * (20 * counts.get(id)), 0));
    for (let j = 0; j < dim; j++) {
      const adjustment = f32(ids.reduce((sum, id) => sum + f32(model.als_factors[id][i] * (20 * counts.get(id) - 1)) * model.als_factors[id][j], 0));
      system[i][j] = f32(system[i][j] + adjustment);
      if (i === j) system[i][j] = f32(system[i][j] + f32(0.1));
    }
  }
  return solve(system, rhs);
}

export function retrievalScores(model, history, algorithm) {
  if (algorithm === "popularity") return [...model.popularity];
  if (algorithm === "category_popularity") {
    const counts = {};
    for (const id of history.slice(-model.history_size)) counts[model.items[id].category] = (counts[model.items[id].category] || 0) + 1;
    const boost = 1 + Math.max(...model.popularity);
    return model.popularity.map((score, i) => score + (counts[model.items[i].category] || 0) * boost);
  }
  const vectors = algorithm === "content" ? model.content : algorithm === "als" ? model.als_factors : model.vectors;
  const query = algorithm === "content" ? normalize(context(model, history)) : algorithm === "als" ? alsQuery(model, history) : queryVector(model, history);
  return vectors.map(row => dot(row, query));
}

export function rankFeatures(model, history, index, retrievalScore) {
  const chosen = history.slice(-model.history_size);
  const ctx = normalize(context(model, history));
  const recent = history.length ? model.content[history.at(-1)] : ctx.map(() => 0);
  const matches = chosen.filter(id => model.items[id].category === model.items[index].category).length;
  return [retrievalScore, dot(model.content[index], ctx), matches / Math.max(1, chosen.length), Math.log1p(model.popularity[index]), Math.log1p(history.length), dot(model.content[index], recent)].map(f32);
}

export function rankScore(model, features) {
  return model.trees.reduce((sum, tree) => {
    let node = tree;
    while (node.v === undefined) node = features[node.f] <= node.t ? node.l : node.r;
    return sum + node.v;
  }, 0);
}

export function recommend(model, options = {}) {
  const requested = options.algorithm || "auto";
  if (!ALGORITHMS.includes(requested)) throw new Error("Unknown recommendation algorithm");
  const state = model.histories[options.userId] || {positive: [], seen: []};
  const history = [...(options.history || state.positive)];
  const seen = new Set(options.seen || state.seen);
  let onboarding = false;
  if (!history.length) for (const category of options.preferences || []) {
    const index = model.items.findIndex(item => item.category === category);
    if (index >= 0) {history.push(index); onboarding = true;}
  }
  if ([...history, ...seen].some(id => !Number.isInteger(id) || id < 0 || id >= model.items.length)) throw new Error("Invalid history item");
  let algorithm = requested === "auto" ? model.default_algorithm : requested;
  let fallback = null;
  if (!history.length && algorithm !== "popularity") {algorithm = "popularity"; fallback = "no_positive_history";}
  let cachedScores;
  if (algorithm === "als") {
    const query = alsQuery(model, history);
    if (Math.sqrt(query.reduce((sum, value) => sum + value * value, 0)) < 1e-9) {algorithm = "content"; fallback = "als_no_signal";}
    else cachedScores = model.als_factors.map(row => dot(row, query));
  }
  const budget = Math.min(model.items.length, Math.max(1, options.candidateCount || 100));
  const scores = cachedScores || retrievalScores(model, history, algorithm);
  let candidates = model.items.map((item, index) => ({index, score: scores[index], retrievalScore: scores[index]})).filter(({index}) => !seen.has(index) && (!options.category || model.items[index].category === options.category) && (!options.coldOnly || model.items[index].controlled_cold));
  // Explicit, reproducible ties: descending score, then ascending catalog ID.
  candidates.sort((a, b) => b.score - a.score || a.index - b.index);
  candidates = candidates.slice(0, budget);
  if (algorithm === "ranked") {
    for (const item of candidates) {item.features = rankFeatures(model, history, item.index, item.retrievalScore); item.score = rankScore(model, item.features);}
    candidates.sort((a, b) => b.score - a.score || b.retrievalScore - a.retrievalScore || a.index - b.index);
  }
  const ctx = normalize(context(model, history));
  return {
    requested, algorithm, fallback, onboarding, historyLength: history.length, candidates: candidates.length,
    items: candidates.slice(0, options.k || 10).map((candidate, i) => ({...model.items[candidate.index], ...candidate, rank: i + 1, contentSimilarity: dot(model.content[candidate.index], ctx), popularity: model.popularity[candidate.index]})),
  };
}
