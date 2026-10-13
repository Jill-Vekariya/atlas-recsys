"""Recommendation lab UI; diagnostics are explicitly non-causal."""

import json
import os
import uuid
from pathlib import Path

import httpx
import streamlit as st

st.set_page_config(page_title="Atlas | Recommendation Lab", page_icon="🧭", layout="wide")
st.title("Atlas · Recommendation Lab")
st.caption("Cold-start personalization, measured tradeoffs, and reliable serving")
if os.getenv("ATLAS_EPHEMERAL", "false").lower() == "true":
    st.caption(
        "Hosted demonstration: anonymous feedback is temporary and resets when the service restarts."
    )
url = os.getenv("ATLAS_API_URL", "http://127.0.0.1:8000")
headers = {"X-API-Key": os.getenv("ATLAS_API_KEY", "")}
bundle_path = Path(os.getenv("ATLAS_DEMO_BUNDLE", "artifacts/synthetic-v1"))
manifest = json.loads((bundle_path / "bundle.json").read_text())
items = json.loads((bundle_path / "items.json").read_text())
histories = json.loads((bundle_path / "histories.json").read_text())
users = [u for u, h in histories.items() if h["positive"]]
categories = sorted({i["category"] for i in items})
if manifest["dataset"]["synthetic"]:
    st.info(
        "Synthetic demonstration catalog and users. These outputs are not real-world performance evidence."
    )
else:
    st.info(
        "Research dataset and later catalog snapshot. Scores represent ranking signals, not purchase probabilities."
    )
with st.sidebar:
    st.subheader("Your recommendation session")
    mode = st.radio("User", ["Existing history", "New user"])
    user = (
        st.selectbox("Example user", users)
        if mode == "Existing history" and users
        else "new-demo-user"
    )
    preferences = (
        st.multiselect("Preferences for a new user", categories) if mode == "New user" else []
    )
    algorithm = st.selectbox(
        "Algorithm",
        ["auto", "ranked", "tower", "content", "als", "category_popularity", "popularity"],
    )
    count = st.select_slider("Candidate budget", [50, 100, 200, 500], value=100)
    category = st.selectbox("Limit to category", ["All"] + categories)
    run = st.button("Recommend", type="primary", use_container_width=True)
    st.caption(
        "Auto uses the validation-selected model. Explicit modes allow controlled comparisons."
    )
if run:
    try:
        response = httpx.post(
            url + "/recommend",
            headers=headers,
            timeout=30,
            trust_env=False,
            json={
                "user_id": user,
                "preferred_categories": preferences,
                "algorithm": algorithm,
                "candidate_count": count,
                "category_filter": None if category == "All" else category,
                "source": "demo",
            },
        )
        response.raise_for_status()
        st.session_state["result"] = response.json()
    except httpx.HTTPError as exc:
        st.error(f"API request failed: {exc}")
result = st.session_state.get("result")
if result:
    a, b, c = st.columns(3)
    a.metric("Processing time", f"{result['processing_ms']:.1f} ms")
    b.metric("Algorithm", result.get("effective_algorithm", result["algorithm"]))
    c.metric("Serving route", result["experiment_slot"])
    st.caption(f"Version: {result['model_version']} · {result['score_meaning']}")
    if result["fallback"]:
        st.warning("Fallback: " + result["fallback_reason"])
    for item in result["recommendations"]:
        with st.container(border=True):
            st.markdown(f"**{item['rank']}. {item['title']}**")
            st.caption(f"{item['item_id']} · score {item['score']:.4f}")
            with st.expander("Inspect recommendation features"):
                st.json(item["diagnostics"])
            if st.button("Useful recommendation", key=result["request_id"] + item["item_id"]):
                response = httpx.post(
                    url + "/feedback",
                    headers=headers,
                    timeout=10,
                    trust_env=False,
                    json={
                        "event_id": str(uuid.uuid4()),
                        "request_id": result["request_id"],
                        "item_id": item["item_id"],
                        "signal": "like",
                    },
                )
                if response.status_code == 200:
                    st.success("Feedback recorded separately from the imported training dataset.")
                else:
                    st.error("Feedback failed: " + response.text)
else:
    st.markdown(
        "Select an existing user or choose preferences for a new user, then request recommendations."
    )
    st.markdown("Use the feature inspector to examine cold-start items and compare algorithms.")
