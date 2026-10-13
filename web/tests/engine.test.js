import {readFileSync, writeFileSync} from "node:fs";
import {test} from "node:test";
import assert from "node:assert/strict";
import {validateModel, queryVector, retrievalScores, rankFeatures, rankScore, recommend} from "../engine.js";

const model = validateModel(JSON.parse(readFileSync(new URL("../model.json", import.meta.url))));
const fixtures = JSON.parse(readFileSync(new URL("./parity.json", import.meta.url))).fixtures;
const errors = {query: 0, tower: 0, als: 0, features: 0, ranker: 0, end_to_end_ranker: 0};
function compare(actual, expected, tolerance, name) {
  assert.equal(actual.length, expected.length, name);
  for (let i = 0; i < actual.length; i++) {
    const error = Math.abs(actual[i] - expected[i]);
    errors[name] = Math.max(errors[name], error);
    assert.ok(error <= tolerance, `${name}[${i}] differs by ${error}; expected ${expected[i]}, got ${actual[i]}`);
  }
}

test("browser inference matches independent NumPy and LightGBM reference outputs", () => {
  for (const fixture of fixtures) {
    compare(queryVector(model, fixture.history), fixture.query_vector, 2e-6, "query");
    const tower = retrievalScores(model, fixture.history, "tower");
    compare(tower, fixture.tower_scores, 3e-6, "tower");
    compare(retrievalScores(model, fixture.history, "als"), fixture.als_scores, 3e-4, "als");
    const scores = model.items.map((_, i) => {
      const features = rankFeatures(model, fixture.history, i, tower[i]);
      compare(features, fixture.features[i], 3e-6, "features");
      // Isolate tree interpretation from float32 reductions at nearby split thresholds.
      return rankScore(model, fixture.features[i]);
    });
    compare(scores, fixture.ranker_scores, 1e-10, "ranker");
    compare(model.items.map((_, i) => rankScore(model, rankFeatures(model, fixture.history, i, tower[i]))), fixture.ranker_scores, 1e-7, "end_to_end_ranker");
  }
  const report = {passed: true, reference: "Python NumPy/FAISS serving arrays and LightGBM Booster.predict", profiles: fixtures.length, catalog_size: model.items.length, max_absolute_errors: errors, retrieval: "Exact exhaustive scoring; not the Docker HNSW implementation", tie_rule: "Descending score, then catalog index; near-tied rankings may differ from FAISS"};
  writeFileSync(new URL("./verification.json", import.meta.url), JSON.stringify(report, null, 2) + "\n");
});

test("new users fall back safely and preferences enable personalization", () => {
  const noHistory = recommend(model, {userId: "new", algorithm: "tower"});
  assert.equal(noHistory.algorithm, "popularity");
  assert.equal(noHistory.fallback, "no_positive_history");
  assert.equal(noHistory.items.length, 10);
  const onboarding = recommend(model, {userId: "new", preferences: ["audio"], algorithm: "tower"});
  assert.equal(onboarding.onboarding, true);
  assert.equal(onboarding.fallback, null);
  assert.ok(onboarding.items.filter(item => item.category === "audio").length >= 7);
  const coldSeed = recommend(model, {userId: "new", preferences: ["books"], algorithm: "als"});
  assert.equal(coldSeed.algorithm, "content");
  assert.equal(coldSeed.fallback, "als_no_signal");
  assert.ok(coldSeed.items.filter(item => item.category === "books").length >= 7);
});

test("all algorithms exclude seen items and respect catalog filters", () => {
  const userId = Object.keys(model.histories).find(id => model.histories[id].positive.length);
  for (const algorithm of ["auto", "ranked", "tower", "content", "als", "category_popularity", "popularity"]) {
    const result = recommend(model, {userId, algorithm, category: "gaming", candidateCount: 50});
    assert.ok(result.items.length > 0);
    for (const item of result.items) {
      assert.equal(item.category, "gaming");
      assert.ok(!model.histories[userId].seen.includes(item.index));
      assert.ok(Number.isFinite(item.score));
    }
  }
  assert.equal(recommend(model, {userId, category: "absent-category"}).items.length, 0);
  assert.ok(recommend(model, {userId, coldOnly: true}).items.every(item => item.controlled_cold));
});

test("session histories support likes without changing learned model weights", () => {
  const initial = recommend(model, {userId: "new", algorithm: "popularity"});
  const liked = initial.items[0].index;
  const next = recommend(model, {history: [liked], seen: [liked], algorithm: "content"});
  assert.equal(next.fallback, null);
  assert.ok(!next.items.some(item => item.index === liked));
  assert.throws(() => recommend(model, {history: [-1]}), /Invalid history/);
  assert.throws(() => recommend(model, {algorithm: "invented"}), /Unknown/);
});

test("the public exporter cannot silently serve a real or incompatible catalog", () => {
  assert.throws(() => validateModel({...model, synthetic: false}), /Unsupported/);
  assert.throws(() => validateModel({...model, feature_names: []}), /schema/);
  const popularity = [...model.popularity]; popularity[0] = NaN;
  assert.throws(() => validateModel({...model, popularity}), /Invalid/);
});
