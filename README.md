# Pulse Atlas — PhonePe Pulse dashboard (Streamlit)

https://phonepe-pulse-project-jxfi8z7ab7rqqrujeqyn6n.streamlit.app/

```bash
pip install -r requirements.txt
streamlit run app.py
```

All data lives in `data/` (your 6 CSVs + a simplified India state boundary file).

## What makes it different
- **Time machine** – animated map across all 20 quarters (2018 Q1 → 2022 Q4)
- **Pulse Score** – composite 0-100 index per state (depth, merchant share, ticket size, growth)
- **Growth matrix** – Stars / Rising / Cash cows / Sleepers
- **Payment DNA** – mix evolution + state archetypes (P2P-led vs Merchant-led)
- **Reach vs depth** – registered users vs transactions per user
- **District concentration curve**, **Hall of fame** (top_* tables), **Head-to-head radar**
- Auto-written **Briefing** tab with insights

## 13 sidebar selectors
Metric · Year · Quarter · Payment category · State focus · Map style · Map mode ·
Colour palette · Scale · Top-N · Growth basis · Time grain · Device brand
(+ Contender A / B in the Head-to-head tab)

## Data notes
- `aggregated_user` (brands) ends at 2022 Q1; the app uses the latest available quarter.
- Registered users is cumulative, so multi-quarter views use the last quarter.
- Ladakh is drawn inside J&K on the map only (boundary file predates the split).
