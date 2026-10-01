# ACTION.md — Spotter "Fuel Route API" Backend Django Assessment

> **Purpose of this file.** This is a complete, self-contained briefing. Any AI
> agent or human that reads *only this file* should be able to understand the
> situation, the requirements, the research, the traps, the design decisions,
> and then build, test, document, and submit the project.
>
> **Status of facts.** Everything in this file is tagged by how sure it is:
> - **[GIVEN]** — stated by the recruiter's email or the job post (verbatim or near-verbatim).
> - **[VERIFIED]** — measured directly (dataset profile, PyPI version lookups, optimizer test run).
> - **[RESEARCH]** — found in public web sources (job post, public GitHub submissions by other candidates).
> - **[INFERENCE]** — reasoned guess. Not proven. Treat as hypothesis.
> - **[DECISION]** — a choice this plan makes on purpose; may be changed if reasons are documented.
>
> Date context: written Wed 30 Sept 2026. Assessment email received Tue 29 Sept 2026 ~11:10.

---

## TABLE OF CONTENTS

1. TL;DR (read this if nothing else)
2. Situation and history
3. The assignment, verbatim, and what each line really means
4. Company and role research
5. What other candidates built (public submissions)
6. Retrospective: what was probably missed last time
7. The dataset: full profile
8. THE TRAP CATALOGUE (data, geo, algorithm, API, ops, presentation)
9. Assumptions and decisions (with reasoning)
10. Architecture
11. Repository layout
12. Data model (PostgreSQL)
13. The import pipeline (offline, run once)
14. The request pipeline (online, per call)
15. Corridor matching (stations near the route)
16. The optimizer (spec, reference code, proof strategy)
17. API contract (request, response, errors)
18. The map page
19. Caching and performance budget
20. Testing plan
21. Configuration
22. Docker and local run
23. README requirements
24. The Loom video script
25. Submission checklist and reply email
26. Timeline
27. Definition of Done
28. Instructions for an AI agent implementing this
29. FAQ / objections
30. Appendix A: verified numbers
31. Appendix B: sources
32. Appendix C: cheat-sheet of formulas and constants

---

## 1. TL;DR

**Who:** Candidate "Anukul" (applied to Spotter, Backend Django Engineer). Passed initial screening.
**What:** Build a Django API: input = start + finish location in the USA. Output = route
(with a map), the optimal (cheapest) fuel stops along it, and the total money spent on fuel.
Vehicle: **500-mile max range, 10 miles per gallon** (so a **50-gallon** tank).
**Data:** the provided CSV `fuel-prices-for-be-assessment.csv` (8,151 rows, OPIS truck-stop retail prices).
**Constraints:** latest stable Django, fast responses, **1 map/route API call ideal (2–3 acceptable)**,
Loom video ≤ 5 min with Postman demo + code overview, share GitHub repo, within 3 days.
**Reward:** $100 bonus on successful completion (and, more importantly, the next hiring step).
**History:** the candidate already submitted a similar assessment before and was **rejected**. Cause unknown.

**The five ideas that decide success:**

1. The CSV has **no latitude/longitude**. Geocode stations **once, offline, at import time**. Never at request time.
2. Make **exactly one** routing call per request (OSRM), and resolve start/finish **locally** (gazetteer) so the total external calls are 1, worst case 3.
3. The optimization is *where to buy fuel*, not how much to burn. Gallons burned = miles ÷ 10, fixed. Use the classic **gas-station greedy**, and **prove** it against a dynamic-programming oracle in tests. (This plan already verified that: 364 random feasible cases, 0 mismatches. See §16.)
4. The dataset is **dirty and sparse**: Canadian rows, duplicate IDs with different prices, a $6.40 outlier, and a nearly empty California/Oregon. Handle each **explicitly and visibly**, never silently.
5. The submission is judged as a *product*: fast, correct, honest about assumptions, tested, documented, with a tight ≤5-minute Loom. Presentation is half the grade.

---

## 2. Situation and history

- **[GIVEN]** The recruiter (Ena, Spotter) emailed "Backend Django Engineer | Assessment" on Tue 29 Sept, 11:10, after the candidate passed initial screening.
- **[GIVEN]** Deadline: "within 3 days of receiving the exercise" → roughly **Fri 2 Oct 2026** (treat the safe deadline as Thu 1 Oct evening).
- **[GIVEN by candidate]** The candidate previously took an assessment "of the same type" (for Spotter or a similar company) and was rejected. The candidate wants to (a) research the company and role, (b) study other participants' public submissions, (c) find what the reviewers actually want, and (d) plan accordingly.
- **[INFERENCE]** Because there was no feedback, the rejection reason is unknown. §6 lists the most probable causes; the plan is designed to eliminate **all** of them, not just one.
- **[RESEARCH]** No public candidate report describing Spotter reviewers' actual feedback on this assessment was found. Glassdoor "Spotter" reviews found belong to a *different* company (a creator-economy business in Los Angeles) and must not be used to draw conclusions about this hiring process.

### 2.1 Which "Spotter"?
The hiring company is **Spotter AI** — "a fast growing trucking startup based in the US" (per its own careers page, hosted on Teamtailor). It is *not* the LA creator-funding company. The role is remote, listed for locations Argentina, Colombia, India, Mexico, Pakistan. The candidate is in India (Patna, Bihar).

---

## 3. The assignment, verbatim, and what each line really means

### 3.1 Verbatim from the recruiter email

> Build an API that takes inputs of start and finish location both within the USA
>
> Return a map of the route along with optimal location to fuel up along the route -- optimal mostly means cost effective based on fuel prices
>
> Assume the vehicle has a maximum range of 500 miles so multiple fuel ups might need to be displayed on the route
>
> Also return the total money spent on fuel assuming the vehicle achieves 10 miles per gallon
>
> Use the attached file below for a list of fuel prices
>
> Find a free API yourself for the map and routing
>
> Requirements:
> - Build the app in latest stable Django
> - Send your results for this project within 3 days of receiving the exercise
> - The API should return results quickly, the quicker the better
> - The API shouldn't need to call the free map/routing API you found too much. One call to the map/route API is ideal, two or three is acceptable
> - Make a Loom where you use Postman or similar API platform to demonstrate the API working while also giving a quick overview of your code (5 minutes max)
> - Share the Github code with us
>
> After completing, please attach the Github code and a Loom video in the question in this message.
> $100 bonus will be awarded only upon successful completion of the coding assessment.

### 3.2 Line-by-line interpretation table

| # | Requirement line | What it really tests | How this plan satisfies it |
|---|---|---|---|
| R1 | API taking start & finish, both in USA | Input validation, geocoding, scoping | Accept place names *or* `lat,lng`; reject non-US with HTTP 400 and a helpful message |
| R2 | "Return a map of the route" | Can the consumer *see* the route? | GeoJSON LineString in JSON **plus** a Leaflet HTML page `/map/` that draws route and numbered stops |
| R3 | "optimal location to fuel up… cost effective" | The core algorithm | Minimum-cost refuelling optimizer with proof-by-oracle tests |
| R4 | 500-mile max range → multiple fuel-ups | Hard constraint handling | No leg may exceed 500 mi; infeasible → HTTP 422 naming the gap |
| R5 | Total money at 10 MPG | Correct arithmetic | Gallons burned = miles ÷ 10; cost = Σ (gallons bought × station price); conservation tested |
| R6 | Use the attached CSV | Data handling | Clean, dedupe, geocode once at import; document every rule |
| R7 | Free map/routing API | Pragmatism | OSRM public server (no key). Backup: OpenRouteService (free key). Verify usage terms yourself |
| R8 | Latest stable Django | Currency | **Django 6.1.1** [VERIFIED on PyPI, 30 Sept 2026] |
| R9 | Fast responses | Performance engineering | In-memory KD-tree, cached results, no per-request geocoding; publish measured latency |
| R10 | 1 (ideal) to 3 external calls | Call discipline | 1 OSRM call; start/finish resolved from a local gazetteer; Nominatim only as a fallback (so ≤3) |
| R11 | Loom, Postman, ≤5 min | Communication | Script in §24, rehearse to 4:30 |
| R12 | GitHub code | Deliverable hygiene | Clean repo, README, tests, `.env.example`, no secrets |

**Critical reading:** the phrase *"optimal mostly means cost effective"* tells you optimality is
judged on **price**, but "mostly" hints they will also look kindly on sanity (not detouring 100 miles for 2 cents).
Also *"shouldn't need to call the API too much"* is a hard, checkable engineering constraint: the reviewer will
literally count outbound calls.

---

## 4. Company and role research

### 4.1 Spotter AI — the company [RESEARCH]
- A US-based, fast-growing **trucking startup** (AI/algorithm-driven products).
- Remote-first, small distributed team "across several countries", "high energy environment".
- Uses Teamtailor as the applicant tracking system (this is why the email says "Recruiting powered by Teamtailor").
- Trucking domain ⇒ **fuel cost optimization on routes is a real product problem for them**, not a toy. Reviewers are likely to care about realism: diesel truck stops, 500-mile range, cost per gallon, multi-stop plans.

### 4.2 The job post — "Remote Backend Django Engineer – AI & Algorithmic Systems" [RESEARCH]
Published on Spotter's careers site (modified 27 Sept 2026). Key lines, paraphrased:

**What you'll do**
- Design/implement backend services and APIs with Python + Django (and DRF or similar).
- Model the domain in the database with clean, well-structured schemas and relationships.
- Implement **algorithmic/AI logic** in the backend — scoring, ranking, **routing**, decision rules.
- Write pragmatic, production-ready code that is easy to reason about and iterate on.
- Optimize for correctness and performance: efficient queries, smart indexing, lean responses.
- Turn product ideas into concrete technical designs and endpoints; help shape patterns and conventions.

**What they're looking for**
- Strong Python + Django.
- Relational modeling and SQL — **they use PostgreSQL**.
- RESTful API design (DRF a plus).
- **Non-trivial business logic or algorithms** (decision flows, scoring, **optimization logic**).
- **Performance instincts**: query behavior, avoiding obvious pitfalls, **caching where it counts**.
- **Startup mindset**: ambiguity, speed, iterating.
- Independent remote work and **clear communication**.

**Bonus**
- Startups / side projects / hackathons (scrappy shipping).
- Algorithms, optimization, data-heavy systems.
- **GCP** in production.
- **Redis** (caching, queues) and PostgreSQL at scale.
- Docker/Kubernetes and/or serverless on GCP.

**Also:** "$100 bonus after successfully completing the assessment"; "central piece of our backend roadmap"; they want to fill it quickly.

### 4.3 What the role implies about how the assessment is graded [INFERENCE, well-supported]
Map each job-post signal to something visible in the submission:

| Job-post signal | Visible evidence to put in the repo/video |
|---|---|
| Algorithmic/optimization logic | A clean optimizer module + oracle-based tests + a paragraph on why it's optimal |
| Clean schemas / indexing | A `FuelStation` model with proper types and DB indexes, a documented import command |
| Performance + caching | Latency table (cold vs warm) in README; cache layer; no per-request geocoding |
| Production-ready, easy to reason about | Small modules, pure functions, type hints, docstrings, error contract |
| PostgreSQL | docker-compose with Postgres (SQLite fallback for zero-friction review) |
| Redis (bonus) | Optional Redis cache backend via env var; locmem default |
| Docker (bonus) | Dockerfile + docker-compose |
| GCP (bonus) | One README paragraph: "deploys to Cloud Run" — do not over-engineer |
| Clear communication | README + tight Loom + an explicit assumptions table |
| Startup mindset / ambiguity | The assumptions are *stated and configurable*, not hidden |

---

## 5. What other candidates built (public submissions) [RESEARCH]

Roughly a dozen public GitHub repos for this exact assessment exist (fuel-route-optimizer / Spotter). Names are given only so an
agent can *read them for patterns*. **Do not copy code.** Reviewers have seen this pattern many times; identical
solutions do not stand out, and copying is a hiring risk.

Repos observed: `anilkumara9/asignment`, `arpan-jain-2006/spotter-fuel-route-api`, `M-Shehzam/spotter-fuel-route-api`,
`Mohamed-Fasidh/Spotter-Backend-Django`, `kalishhhh/Fuel-Route-API`, `Arpit-3000/SpotterAI`, `0ye0m/fuel-route-optimizer-spotter`,
`JUSTMEETPATEL/spotter-truck-route-optimization`, `Ramshak278/Assignment`, `SrijanShi/Spotter-backend`.

### 5.1 Patterns shared by the strongest ones
1. **Django 6.x** (6.0/6.1). "Latest stable" is taken literally.
2. **Station coordinates prepared at import**, not per request. One repo bundled 6,625 stations as pre-geocoded JSON; another imports via a management command.
3. **One routing call** (OSRM) per request; start/finish resolved from a local city table where possible; results cached.
4. **Spatial pruning** before optimizing: KD-tree, grid cells (0.5° buckets), or corridor distance; then thin candidates (e.g., keep the cheapest few per 25-mile bucket).
5. **Greedy optimizer** for refuelling, **cross-checked** against a DP/brute-force/linear-program oracle in tests. This is the single strongest differentiator.
6. **422 when infeasible** (gap > 500 miles) instead of returning a wrong plan; one repo discovered LA → Seattle has an **877-mile** station-free stretch in this dataset.
7. **US-only enforcement** so "Toronto, ON" doesn't silently become Toronto, Ohio. One repo uses a US outline polygon with a fallback "within 25 mi of a dataset station".
8. **Leaflet map page** (`/map/`) in addition to GeoJSON in the JSON.
9. **README with a requirement → file traceability table** and a "known limitations" section.
10. **Demo docs**: Postman guide + Loom script in `docs/`.
11. **Explicit cost model**: e.g., "vehicle starts with a full tank; cost counts only fuel *purchased*".
12. **Mocked routing in tests** so the suite runs offline.

### 5.2 Weaknesses visible in weaker public repos [INFERENCE from repo READMEs]
- Recomputing or geocoding at request time.
- Optimizing only "cheapest station per 500-mile window" (not a true global optimum).
- No proof of optimality.
- Returning only raw coordinates with no map.
- Older Django (4.x/5.x) in a "latest stable" assignment.
- No tests / no error handling / no US validation.
- README that does not state assumptions.

### 5.3 Consequence for this project
Baseline quality (features 1–12 above) is now **table stakes**. To stand out:
- prove optimality, measure and publish latency,
- handle the ugly data cases visibly,
- present concise, confident, honest documentation and a great Loom.


---

## 6. Retrospective: what was probably missed last time

> **Honesty note [INFERENCE]:** the actual rejection reason was never communicated. The list below is a set of
> hypotheses ranked by likelihood, built from the assessment wording, the job post, and patterns in public submissions.
> The remedy column is what this plan does about each. Use it as a pre-submission audit: for each row, be able to answer "how do I know this is fixed?"

| # | Probable miss | Why reviewers punish it | Remedy in this plan | Proof to show |
|---|---|---|---|---|
| M1 | Geocoded stations (or called a geocoder) **per request** | Violates "shouldn't call the API too much"; slow | Import-time geocoding from an offline gazetteer; stations live in memory | Log/README: "external calls per request: 1" |
| M2 | **More than 3** external calls (e.g., one per leg or per stop) | Explicit requirement | Exactly 1 OSRM call; start/finish from local table; Nominatim fallback only for unknown text | A test asserting `routing_client.call_count == 1` |
| M3 | Slow first response (loading CSV per request) | "quicker the better" | Load once at startup into KD-tree; cache full results | Latency table in README |
| M4 | **Wrong cost math** — e.g. `stops × 50 gal × price`, or ignoring partial fills | Money is the headline output | Buy only what's needed; Σ gallons purchased + start fuel − end fuel = miles ÷ 10 | Conservation unit test |
| M5 | Not truly **optimal** (e.g., cheapest station per fixed 500-mi window) | The core of the assignment | Global greedy with lookahead; oracle-verified | Randomized oracle test (0 mismatches) |
| M6 | Ignored the **500-mile constraint** on some leg | Hard requirement | Explicit feasibility; each leg ≤ range; else 422 with named gap | Test with an artificial gap |
| M7 | No **map** — only coordinates or a text list | Requirement R2 | GeoJSON + Leaflet page | Screenshot in Loom |
| M8 | Accepted **non-US** input, or geocoded "Toronto" to the US | Requirement R1 | US-only geocoding filter + validation | Tests for CA/MX inputs |
| M9 | Not the **latest Django** | Requirement R8 | Django 6.1.1 pinned | `requirements.txt` + `python -m django --version` in Loom |
| M10 | Crashes/500s on edge cases (short trip, same city, sparse West, unknown city) | "Production-ready" | Explicit error contract, tested | Error-case demo in Loom |
| M11 | **No tests**, or tests that hit the real network | Reliability | Offline mocked test suite | `pytest` green output |
| M12 | Weak/absent README, no assumptions stated | Communication | README with assumptions & traceability | README review |
| M13 | **Loom too long / doesn't show code / doesn't show Postman** | Explicit requirement (≤5 min) | Scripted, timed | Rehearsed run ≤ 4:45 |
| M14 | Secrets or junk committed, no `.env.example`, venv committed | Hygiene | `.gitignore`, `.env.example` | Repo skim |
| M15 | Dirty data used raw (Canada rows, duplicates, outlier) | Data-heavy role | Explicit cleaning rules, logged counts | Import command summary output |
| M16 | Submitted **late** or link broken/private | Process | Submit early; test links in an incognito window | Checklist §25 |
| M17 | Output not *explainable* (no reason why stops chosen) | Trust | Each stop includes `reason` (e.g., "cheapest within range ahead") | Response sample |
| M18 | Over-engineering (Celery, K8s manifests, microservices) that hides the algorithm | Distracts | Keep scope tight; mention GCP/Redis as *options* | Repo size stays small |
| M19 | Public routing server rate-limited/failed during review | Demo fails | Cache + graceful 502 + documented fallback provider + saved sample responses | `docs/sample_responses/` |
| M20 | Demo used a route that hides problems (e.g., short trip, no stops) | Weak evidence | Demo a long cross-country trip, a short trip, and an error | Loom script §24 |

### 6.1 Meta-lesson
Many rejections in take-home assessments come from *reviewability*, not just correctness: the reviewer has minutes per
submission. Make correctness **obvious** — tables, one-line curl examples, a passing test run, and a clear statement of
assumptions. A reviewer who has to guess will assume the worst.

---

## 7. The dataset: full profile

**File:** `fuel-prices-for-be-assessment.csv` (uploaded to `/mnt/user-data/uploads/`; keep a copy in the repo under `data/`).

### 7.1 Schema [VERIFIED]
CSV header (CRLF line endings):

```
OPIS Truckstop ID,Truckstop Name,Address,City,State,Rack ID,Retail Price
```

| Column | Type | Example | Notes |
|---|---|---|---|
| OPIS Truckstop ID | int | `7` | Station identifier; **not unique per row** (see traps) |
| Truckstop Name | str | `WOODSHED OF BIG CABIN` | Same ID can have different name strings (`PILOT TRAVEL CENTER #1243` vs `PILOT #1243`) |
| Address | str | `I-44, EXIT 283 & US-69` | Highway exit text. **Not geocodable** by normal geocoders |
| City | str | `Big Cabin` | Usable for geocoding |
| State | str | `OK` | Two-letter; includes Canadian provinces |
| Rack ID | int | `307` | OPIS rack (pricing terminal region). Not needed |
| Retail Price | float | `3.00733333` | **USD per gallon** (diesel truck stops; `$2.687–$6.399`) |

Sample rows:
```
7,WOODSHED OF BIG CABIN,"I-44, EXIT 283 & US-69",Big Cabin,OK,307,3.00733333
9,KWIK TRIP #796,"I-94, EXIT 143 & US-12 & SR-21",Tomah,WI,420,3.28733333
20,PILOT TRAVEL CENTER #1243,"I-8, EXIT 119 & SR-85",Gila Bend,AZ,930,3.899
20,PILOT #1243,"I-8, EXIT 119 & SR-85",Gila Bend,AZ,930,3.899
```

### 7.2 Measured statistics [VERIFIED]
| Metric | Value |
|---|---|
| Total data rows | 8,151 |
| Distinct "State" values | 57 = **48 US states** (lower 48 only — **no AK, HI, or DC**) + **9 Canadian provinces/territories** |
| Canadian rows (AB, BC, MB, NB, NS, ON, QC, SK, YT) | **620** |
| US rows | **7,531** |
| Unique OPIS IDs (US) | **6,626** |
| IDs with >1 price row (US) | **568** |
| Max price spread inside one ID | **$0.90** |
| Unique (Address, City, State) in US | 6,325 |
| Price min / median / mean / max (all rows) | $2.687 / $3.432 / $3.499 / $6.399 |
| Cheapest row | `7-ELEVEN #218`, Harrold, TX, $2.687 |
| Priciest row | `CHEVRON #352416`, Jacumba, CA, $6.399 (outlier) |
| Another high outlier | `PILOT #1194`, Phoenix, AZ, $6.039 |
| Missing values | none (0 NaN) |
| Fully duplicated rows | 26 |
| Rows per state (top) | TX 790, IL 774, MI 327, GA 311, WI 297, OH 263, MO 250, IN 238 |

### 7.3 Geographic coverage (unique US station IDs) [VERIFIED]
| State | Stations | Comment |
|---|---|---|
| CA | **8** | Extremely sparse — almost certainly incomplete for realistic routing |
| OR | 29 | Sparse |
| WA | 52 | Sparse-ish |
| NV | 71 | |
| AZ | 132 | |
| NM | 107 | |
| MT | 44 | |
| WY | 64 | |
| ND | 59 | |
| TX | (many; 790 rows) | Dense |

Implication: **west-coast routes may be infeasible with a 500-mile tank** (public repo reported LA → Seattle has an 877-mile stretch with no station in range). This is a dataset property, not a bug. Design for it.

### 7.4 What the data is NOT
- Not geocoded. No lat/lng anywhere.
- Not one-price-per-station.
- Not guaranteed US-only.
- Not guaranteed to represent the same fuel product across duplicate rows (unknown — could be grades/products/effective dates). The file does not say.

---

## 8. THE TRAP CATALOGUE

Every trap has: **what it is → how it bites → how to handle → how to test**.
An implementing agent should tick every box.

### 8.A DATA TRAPS

**A1. No coordinates.**
- *Bites:* You cannot decide which stations lie on a route. Naive fix — geocode 8,000 stations per request — violates R9/R10 and is unusably slow (public geocoders are ~1 req/s).
- *Handle:* Geocode **once**, offline, at import. See §13.
- *Test:* The route endpoint test asserts it performs **zero** geocoder calls for stations.

**A2. Addresses are highway-exit strings** (`I-44, EXIT 283 & US-69`).
- *Bites:* Address-level geocoders (Census, Nominatim) fail on these.
- *Handle:* Geocode by **City + State** using a gazetteer (city centroid). Accuracy ≈ a few miles, sufficient at 500-mile scale. Document this approximation as a limitation. Optionally refine: nothing else needed.
- *Test:* ≥ 99% of unique US (city,state) resolve; report unresolved count and list.

**A3. Canadian stations (620 rows).**
- *Bites:* A US-only product would recommend a Canadian station near the border, or the KD-tree would include them.
- *Handle:* Filter to US states in the import (allow-list of the 48 lower-48 state codes present in the file). Log how many dropped.
- *Test:* Import unit test: Canadian provinces excluded.

**A4. Duplicate IDs with different prices (568 IDs; spread up to $0.90).**
- *Bites:* Which price is "the" price? Choosing the minimum may under-quote the real cost; one public repo explicitly warned the minimum quotes a total the route cannot achieve.
- *Handle:* **[DECISION]** Choose a *single, documented, configurable* rule. Recommended default: **median** of the ID's prices (robust to one odd row, not optimistic). Alternative modes: `min`, `max`, `mean`, `latest-row`. Keep the rule in `settings.PRICE_AGGREGATION` and print it in the import summary and README.
- *Test:* Given an ID with prices [3.2, 3.4, 3.6], the median rule yields 3.4; config switch changes it.
- *Note:* If the interviewer asks, say plainly: "The file doesn't say what duplicate rows mean, so I chose the median and made it configurable."

**A5. Same ID, different name strings.** (`PILOT TRAVEL CENTER #1243` / `PILOT #1243`)
- *Handle:* Keep the **longest** (or first) name per ID as display name.
- *Test:* dedupe test.

**A6. Fully duplicate rows (26).** Removed naturally by ID aggregation.

**A7. Price outliers ($6.399 Jacumba CA; $6.039 Phoenix AZ).**
- *Bites:* Could distort tests or demos, but the optimizer avoids expensive stations anyway. However if the *only* station in a sparse area is expensive, you must still use it.
- *Handle:* Do **not** delete outliers silently. Optionally *flag* stations with price > (median + 3×MAD) as `is_price_outlier` and still allow them. Mention in README.

**A8. Rack ID irrelevant.** Ignore; do not model it (or store as raw).

**A9. Encoding / line endings.** File is CRLF; use `csv` module with `newline=""` or pandas. Strip whitespace from all string fields.

**A10. State abbreviations vs. names.** CSV uses 2-letter codes. The gazetteer must use the same codes.

**A11. Case sensitivity of city names.** Normalize (`casefold`, collapse whitespace, strip punctuation like `St.` vs `Saint`). Keep a small alias table for tricky ones. Report unresolved cities.

**A12. City centroid ≠ station location.**
- *Bites:* A station "in Tomah, WI" may be several miles from Tomah's centroid; corridor matching may include/exclude wrong ones.
- *Handle:* Use a corridor radius with tolerance (e.g., 5–8 miles) and *report* `distance_from_route_miles` per stop, based on approximate coordinates; state the limitation.

### 8.B GEO / ROUTING TRAPS

**B1. Geocoding "within the USA."**
- *Bites:* "Toronto" → Toronto, Ohio? "Paris" → Paris, TX? "Springfield" → ambiguous.
- *Handle:* Accept `City, ST` format primarily; resolve against a **US-only** gazetteer; require state disambiguation when a name is ambiguous, or choose highest-population match and *return which one was chosen* (`resolved_start`). Reject non-US with 400. Accept `lat,lng` directly and validate it lies within the US (bounding box + proximity to a station or US polygon).
- *Test:* "Toronto, ON" → 400; "Springfield" (no state) → either 400 with candidate list or documented default.

**B2. Border/coastal points falling outside a coarse US polygon** (El Paso, Manhattan).
- *Handle:* If you use a polygon, add a fallback: "within N miles of a US station or gazetteer city". Simpler: validate by gazetteer + bounding box (lower 48 + AK + HI). **[DECISION]** Prefer the simple approach; document that HI is unroutable (no road route to the mainland).

**B3. Alaska/Hawaii.** OSRM returns no route (or a silly one) between mainland and Hawaii; Alaska requires Canada crossing. Return 422 "no drivable route". Don't crash.

**B4. Route geometry size.** Cross-country geometry can have tens of thousands of points.
- *Bites:* Slow JSON, slow spatial checks.
- *Handle:* Request `overview=full&geometries=geojson` **once**, then create (a) a **densified/thinned** internal polyline (~1 mile resolution) for spatial work, (b) a **simplified** polyline for the response by default (e.g., Douglas–Peucker ~ 0.001–0.005°), with `?geometry=full` to get everything.

**B5. Route distance mismatch.** OSRM distance (meters) vs. summed haversine of the geometry can differ slightly.
- *Handle:* **Scale mile markers so the final one equals the OSRM total distance.** Fuel math uses the OSRM total.

**B6. Meters vs miles.** OSRM returns meters. `miles = meters / 1609.344`. Do it once, in one function.

**B7. Lon/lat order.** GeoJSON and OSRM use **[lon, lat]**; humans and Leaflet use **[lat, lon]**. Mixing them is the #1 silent geo bug. Have a single `LatLng` dataclass and convert at the edges only. Add a test with a known coordinate (e.g., Dallas ≈ lat 32.78, lon −96.80).

**B8. OSRM URL format.** `.../route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson&steps=false`. Coordinates are **lon,lat**.

**B9. Public OSRM demo limits.** The public demo server is best-effort and not meant for heavy production use **[from general knowledge; verify current terms before relying on it]**.
- *Handle:* Set a `User-Agent`, timeout (e.g., 10 s), one retry on network error only, **cache** identical trips, and keep a documented fallback provider (OpenRouteService free key, ~ a few thousand requests/day **[verify current limits]**). Implement a `RoutingProvider` interface so swapping is a config change.
- *Note:* For the demo, also save real responses in `docs/sample_responses/` so the reviewer can see results even if the public server is down.

**B10. Routing "through" a waypoint.** Not needed. The plan uses one origin→destination call. Detours to stations are **not** re-routed (that would need additional calls). See D-decision on detours in §9.

**B11. Very short routes** (e.g., 30 miles) and **same start/finish**.
- *Handle:* Short: no stops needed (start full ≥ trip) → `fuel_stops: []`, cost `0.00` under the full-tank assumption (see §9.1) — but still return route, distance, and clear explanation. Same start/finish: 400 or trivial 0-mile route.

### 8.C ALGORITHM TRAPS

**C1. Confusing "how much fuel to burn" with "where to buy."** Gallons burned = miles ÷ 10 is *fixed*. The only decision is the purchase location/amount.

**C2. "Cheapest station in each 500-mile window."** Not optimal: you may not need to fill at all in a window, or a slightly-farther cheaper station is better. Use the **lookahead greedy**.

**C3. Always filling the tank at every stop.** Wastes money if a cheaper station is ahead within range. Correct rule: *if a cheaper (or equal) station is reachable ahead, buy only enough to get there; else fill up (or just enough to finish).*

**C4. Ignoring the final leg.** The destination behaves like a station with price 0 and infinite demand end: you should arrive with **as little fuel as possible** — buy only what's needed to reach the destination.

**C5. Starting fuel ambiguity.** See §9.1. Must be stated and configurable.

**C6. Floating-point range checks.** `500.0000001 > 500` triggers false infeasibility. Use epsilon `1e-6` on range comparisons and gallon arithmetic.

**C7. Ties and equal prices.** Use `<=` (next station with price ≤ current) so ties don't cause needless full fills.

**C8. Off-route stations (detour).** A station 15 miles off the highway costs real miles. This plan restricts to a narrow corridor and reports offset; it does not add detour miles to fuel burn (see §9.3). Do not silently include stations 50 miles away.

**C9. Stations "behind" you or beyond the destination.** Project onto the route and keep only `0 ≤ mile ≤ total`.

**C10. Projection ambiguity on looping/parallel routes.** A station near two parts of the route (e.g., a highway loop) could be projected to the wrong mile marker. Use nearest route point; for robustness, restrict to a small corridor (≤ 8 mi). Note as limitation.

**C11. Optimality proof.** A greedy claim without a check is a claim. Include an **oracle test** (DP over discretized fuel) — already verified to agree on 364/364 random cases (§16.4).

**C12. Complexity.** Sorting candidates by mile marker is O(n log n); the greedy scan with "next cheaper station" can be O(n·k) naive; use a monotonic-stack "next cheaper within range" or a bounded scan (≤ ~500 mi window). n is a few hundred after corridor filtering → trivially fast.

**C13. Candidate thinning is allowed only if provably safe.** Keeping "the cheapest 4 per 25-mile bucket" throws away candidates that could matter in edge cases; it's a heuristic. If you thin, run the oracle test with and without thinning and report. Simplest: *don't thin* — after a ~5-mile corridor, a cross-country route has only a few hundred candidates.

### 8.D API TRAPS

**D1. Contract drift.** Decide the response schema once (§17) and freeze it; tests assert the schema.

**D2. Money as float.** `0.1 + 0.2 ≠ 0.3`. Compute with `Decimal` or round to cents at the *edge*; keep internal math in float but round each stop cost to 2 dp and make `total = sum(rounded stop costs)` so the numbers on screen add up. **[DECISION]** total is the sum of the rounded stop costs.

**D3. Units unlabeled.** Every numeric field carries its unit in the name: `distance_miles`, `price_per_gallon_usd`, `gallons`, `cost_usd`.

**D4. Inconsistent HTTP codes.** 400 bad input, 404 unknown route path, 422 valid input but infeasible plan, 502 upstream routing failure, 504 upstream timeout. Never a bare 500 for an expected condition.

**D5. GET vs POST.** Support both: `GET /api/route/?start=...&finish=...` (easy in a browser & Postman) and `POST /api/route/` with JSON. Same handler.

**D6. CSRF on POST.** DRF `APIView` with no session auth is fine; confirm POST works from Postman without a CSRF token.

**D7. Unbounded response size.** Full geometry can be MBs. Default to simplified geometry.

**D8. Leaking exceptions/stack traces.** `DEBUG=False` in the demo config; a global exception handler returns JSON errors.

**D9. Trailing slashes / URL conventions.** Pick `/api/route/` and be consistent.

### 8.E OPERATIONS / ENGINEERING TRAPS

**E1. Loading the CSV or building the KD-tree per request.** Build once per process at startup (AppConfig `ready()` or lazy singleton with a lock).

**E2. Multi-worker memory duplication.** Under gunicorn with N workers each builds its own KD-tree (~6.6k points ≈ trivial). Fine.

**E3. Startup with an empty DB.** If the importer has not run, fail *loudly* (health check says "fuel data not loaded"; route returns 503 with instruction), not a mysterious empty result.

**E4. Cache key collisions.** Normalize input before hashing (`casefold`, collapse spaces, round coords to 4 dp). Include model params (`mpg`, `range`, `starting_fuel`, `price_rule`) in the key.

**E5. Stale cache after re-import.** Include a `data_version` (e.g., import timestamp/hash) in the key.

**E6. Secrets.** `SECRET_KEY` from env; `.env` gitignored; provide `.env.example`.

**E7. Tests that need the internet.** Mock the routing client; feed coordinates so no geocoding is needed.

**E8. Timezone/locale quirks.** None needed, but set `USE_TZ = True` anyway.

**E9. `ALLOWED_HOSTS` / DEBUG misconfig** on the demo machine.

**E10. Windows path/line-ending issues** (candidate may develop on Windows): use `pathlib`, `newline=""`, `.gitattributes` with `* text=auto`.

### 8.F PRESENTATION / PROCESS TRAPS

**F1. Loom > 5 minutes.** Auto-fail vibe. Rehearse; target 4:30.
**F2. Loom without Postman** or without code overview. Both are mandatory.
**F3. Demoing only the happy path.** Show error cases.
**F4. Private GitHub repo / private Loom.** Test both links logged out.
**F5. Submitting at the last minute.** Aim to submit ≥ 12 hours early.
**F6. Not replying in the requested place.** The email says "attach the Github code and a Loom video in the question in this message" — i.e. answer inside the Teamtailor/Gmail question thread for that message. Reply there, not somewhere else.
**F7. Copying a public repo.** Reviewers may have seen it; also unethical. Read for ideas, write your own.
**F8. Overclaiming.** Do not say "optimal" for something not proven, do not say "no external calls" when there are 1–3. Be exact.


---

## 9. Assumptions and decisions (with reasoning)

Every ambiguity in the brief is resolved here on purpose. Each must appear in the README "Assumptions" table and be
mentioned in one sentence in the Loom. Where practical, make it a **request parameter or a setting** so a reviewer with a
different opinion can flip it in seconds.

### 9.1 Starting fuel — **[DECISION]**
Two defensible readings:
- **(A) Start with a full tank (50 gal), cost counts only fuel purchased.** A 400-mile trip → 0 stops, `$0.00`.
- **(B) Start empty / price every gallon burned.** Total cost = miles ÷ 10 × price paid. Requires a station at mile 0 (often infeasible).

**Default: (A)**, because it is physically consistent with "500-mile max range", avoids infeasibility at the origin,
and most strong public submissions use it. **But** to defuse the risk that a reviewer expects (B)'s "trip cost":
- Parameter `starting_fuel_gallons` (default `50`; `0` gives reading B, and then the origin must be within reach of a station — otherwise 422 with a clear message).
- Response always includes: `gallons_consumed` (= miles ÷ 10), `gallons_purchased`, `starting_fuel_gallons`, `ending_fuel_gallons`, `average_price_paid_per_gallon_usd`, and an `assumptions` object.
- README states plainly: "`total_fuel_cost_usd` is the money spent at stations. Fuel already in the tank at the start is not billed."
- Loom: say it in one sentence.

### 9.2 Vehicle constants — [GIVEN] + configurable
`MAX_RANGE_MILES = 500`, `MPG = 10` → `TANK_GALLONS = 50`. Overridable via query params (`range_miles`, `mpg`) within sane bounds (e.g. range 50–1500, mpg 1–50) — a reviewer can then test `range_miles=1000` to plan Los Angeles → Seattle.

### 9.3 Detours — **[DECISION]**
Stations within a **corridor** (default **5 miles**, configurable up to ~15) of the route are treated as "on the route". The plan does **not** reroute through them (that would need extra routing calls, violating the call budget). Reported: `distance_from_route_miles`. Detour fuel is **not** charged. Documented limitation. (Optionally add a tiny penalty: `effective_price = price + detour_penalty` — leave as a stretch goal; default off.)

### 9.4 Price per station — **[DECISION]** median across duplicate rows of an ID (§8 A4), configurable.

### 9.5 Geocoding stations — **[DECISION]** city+state centroid from an offline gazetteer (§13). Accuracy ± several miles; stated.

### 9.6 Geocoding endpoints — **[DECISION]** order of resolution:
1. `lat,lng` string → parse, validate inside the US.
2. `City, ST` → local gazetteer (0 external calls).
3. Free text (address, landmark) → **Nominatim** (`countrycodes=us`, 1 call each; adds up to 2 calls) — total ≤ 3 external calls including OSRM. Cache results in DB/cache.

### 9.7 Map delivery — **[DECISION]**
- JSON contains `route.geometry` as a **GeoJSON LineString** ([lon,lat]).
- `GET /map/?start=…&finish=…` returns an HTML page using **Leaflet + OpenStreetMap tiles** (loaded from a CDN in the browser — this is the user's browser fetching tiles, not the server calling a map API, so it doesn't count toward the server-side call budget; say so in README).
- Response includes `map_url` pointing to that page.

### 9.8 Scope guard — **[DECISION]** Not doing: auth, user accounts, Celery, Kubernetes, multi-fuel-type logic, real-time prices, toll/truck-restriction routing. Mentioned in "Future work" only.

### 9.9 Rounding — 2 dp for money, 2–3 dp for gallons/miles; total = sum of rounded stop costs.

### 9.10 Time — return `duration_hours` from OSRM as a bonus; not required.

---

## 10. Architecture

### 10.1 Stack
| Layer | Choice | Reason |
|---|---|---|
| Language | Python 3.12+ (3.13 fine) | Django 6.1 requires modern Python |
| Framework | **Django 6.1.1** [VERIFIED latest on PyPI, 30 Sept 2026] | "Latest stable" requirement |
| API | **Django REST Framework 3.18.1** [VERIFIED] | Job post: "DRF or similar" |
| DB | **PostgreSQL** (docker-compose) with **SQLite fallback** | Job post uses Postgres; SQLite = zero-friction review |
| Spatial index | `scipy.spatial.cKDTree` (or `numpy` grid) in memory | Fast, no PostGIS needed |
| HTTP client | `requests` (or `httpx`) with timeouts | Routing/geocoding |
| Cache | Django cache: **locmem default**, **Redis optional** via env | Bonus item in job post |
| Map | Leaflet (CDN) | No key required |
| Tests | `pytest`, `pytest-django`, `responses`/`unittest.mock` | Offline |
| Lint/format | `ruff` (optional) | Hygiene |
| Server | `gunicorn` in Docker | Production-realistic |

Pin versions in `requirements.txt` (e.g., `Django==6.1.1`, `djangorestframework==3.18.1`).
Confirm with `pip index versions django` again on the day of submission — "latest stable" can move.

### 10.2 Component diagram (text)

```
                      OFFLINE (run once)
  fuel-prices.csv ─┐
  us_cities.csv  ──┼─► import_fuel_prices ─► clean/dedupe/geocode ─► DB: FuelStation
  (gazetteer)     ─┘

                      ONLINE (per request)
 client ─► /api/route/?start=&finish=
             │
             ▼
        [validate params]
             │
             ▼
        [cache lookup] ──hit──► response
             │miss
             ▼
        [resolve start/finish]  (gazetteer; Nominatim fallback ≤2 calls)
             │
             ▼
        [ONE OSRM call] ► geometry + distance + duration
             │
             ▼
        [prepare polyline: densify ~1mi, cumulative miles, scale to OSRM distance]
             │
             ▼
        [corridor match: KD-tree query around route ► candidate stations with mile markers]
             │
             ▼
        [optimizer: greedy min-cost refuelling; feasibility check]
             │
             ▼
        [assemble response: stops, totals, GeoJSON, map_url, assumptions]
             │
             ▼
        [cache store] ► JSON out
```

### 10.3 Module boundaries (keep pure where possible)
- `geo.py` — haversine, projection to local miles, polyline densify, cumulative distance, point-to-polyline. **Pure.**
- `optimizer.py` — `plan_refuelling(stops, total_miles, ...)`. **Pure. No Django, no network.**
- `corridor.py` — selects candidates and their mile markers given geometry + KD-tree. **Pure** (takes arrays).
- `providers/osrm.py` — the *only* place that talks to the routing service.
- `providers/geocode.py` — gazetteer lookup + Nominatim fallback.
- `services/planner.py` — orchestrates the pipeline.
- `views.py` — thin: validate → call planner → serialize.
- `management/commands/import_fuel_prices.py` — offline pipeline.

Rule: **the optimizer never imports Django.** That is what makes it testable and "easy to reason about" (a phrase from the job post).

---

## 11. Repository layout

```
spotter-fuel-route/
├── README.md                     # overview, assumptions table, traceability, latency table, limitations
├── ACTION.md                     # (this file — optional to commit; useful as design doc)
├── requirements.txt              # pinned
├── requirements-dev.txt
├── manage.py
├── Dockerfile
├── docker-compose.yml            # web + postgres (+ optional redis)
├── .env.example
├── .gitignore
├── .gitattributes                # * text=auto
├── pytest.ini
├── data/
│   ├── fuel-prices-for-be-assessment.csv
│   └── us_cities.csv             # offline gazetteer: city,state,lat,lng,population (see §13)
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py / asgi.py
├── routing/                      # Django app
│   ├── apps.py                   # AppConfig.ready(): lazy index warm-up hook
│   ├── models.py                 # FuelStation, (GeocodeCache optional)
│   ├── admin.py
│   ├── views.py                  # RouteView, MapView, HealthView
│   ├── serializers.py            # request validation + response schema
│   ├── urls.py
│   ├── errors.py                 # domain exceptions → HTTP mapping
│   ├── conf.py                   # typed accessors for settings (range, mpg, corridor, ...)
│   ├── geo.py
│   ├── corridor.py
│   ├── optimizer.py
│   ├── station_index.py          # in-memory KD-tree singleton
│   ├── providers/
│   │   ├── base.py               # RoutingProvider Protocol
│   │   ├── osrm.py
│   │   ├── ors.py                # optional fallback provider
│   │   └── geocode.py
│   ├── services/
│   │   └── planner.py
│   ├── management/commands/
│   │   ├── import_fuel_prices.py
│   │   └── smoke_test.py         # calls the running API for 4 canned scenarios
│   ├── templates/routing/
│   │   ├── map.html
│   │   └── docs.html             # optional human-readable landing page
│   └── tests/
│       ├── test_optimizer.py
│       ├── test_optimizer_oracle.py
│       ├── test_geo.py
│       ├── test_corridor.py
│       ├── test_import.py
│       ├── test_api.py           # mocked OSRM
│       └── fixtures/
├── docs/
│   ├── POSTMAN_GUIDE.md
│   ├── LOOM_SCRIPT.md
│   ├── postman_collection.json
│   └── sample_responses/
│       ├── dallas_chicago.json
│       ├── ny_la.json
│       ├── short_trip.json
│       └── la_seattle_422.json
└── scripts/
    └── smoke.sh
```

Keep it tidy. A reviewer opening the repo should see intent in ten seconds.

---

## 12. Data model (PostgreSQL)

The job post emphasizes "clean, well-structured schemas" and "smart indexing". Show that here without over-engineering.

### 12.1 `FuelStation`
```python
class FuelStation(models.Model):
    opis_id      = models.PositiveIntegerField(unique=True)          # natural key from CSV
    name         = models.CharField(max_length=200)
    address      = models.CharField(max_length=200)                  # raw exit text, display only
    city         = models.CharField(max_length=100)
    state        = models.CharField(max_length=2, db_index=True)
    latitude     = models.FloatField(null=True)                      # null if unresolved
    longitude    = models.FloatField(null=True)
    price_usd_per_gallon = models.DecimalField(max_digits=6, decimal_places=4)
    price_rows_merged    = models.PositiveSmallIntegerField(default=1)  # how many CSV rows folded in
    price_min    = models.DecimalField(max_digits=6, decimal_places=4)
    price_max    = models.DecimalField(max_digits=6, decimal_places=4)
    geocode_quality = models.CharField(max_length=12, default="city")  # city | manual | unresolved
    is_price_outlier = models.BooleanField(default=False)
    imported_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["state", "city"]),
            models.Index(fields=["latitude", "longitude"]),   # helps admin/debug & bbox fallback
            models.Index(fields=["price_usd_per_gallon"]),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(price_usd_per_gallon__gt=0), name="price_positive"),
        ]
```
Notes:
- Django 6.x `CheckConstraint` uses the keyword **`condition=`** (older versions used `check=`). Verify against the installed version's docs.
- `unique=True` on `opis_id` already indexes it.
- Storing `price_min/max` and `price_rows_merged` makes the duplicate-price decision **auditable** (impresses reviewers).

### 12.2 `GeocodeCache` (optional, for the Nominatim fallback)
```python
class GeocodeCache(models.Model):
    query_normalized = models.CharField(max_length=255, unique=True)
    latitude  = models.FloatField()
    longitude = models.FloatField()
    display_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
```

### 12.3 `ImportRun` (optional, tiny)
Stores the import timestamp, counts, `price_rule`, file hash → serves as the `data_version` used in cache keys.

### 12.4 Why the DB at all if the index is in memory?
- Source of truth + auditability + admin inspection + a realistic Django design.
- The in-memory KD-tree is a **read-through cache** of `FuelStation` rows with coordinates.
- Cheap to rebuild at startup (~6.6k rows).

---

## 13. The import pipeline (offline, run once)

Command: `python manage.py import_fuel_prices data/fuel-prices-for-be-assessment.csv [--gazetteer data/us_cities.csv] [--price-rule median]`

### 13.1 Steps
1. **Read** CSV (`csv.DictReader`, `newline=""`, `encoding="utf-8-sig"`); strip all strings.
2. **Filter to US** (48 lower-48 codes in the file). Count and log dropped Canadian rows (expect **620**).
3. **Group by `OPIS Truckstop ID`.** For each group:
   - `name` = longest name string (or first).
   - `address`, `city`, `state` = first row (verify consistency; log if a group has conflicting city/state — expect none).
   - `price` = aggregation per rule (median default); record `min`, `max`, `rows_merged`.
4. **Geocode** by `(city, state)`:
   - Normalize: lowercase, strip, collapse spaces, expand `St.`→`saint`, `Ft.`→`fort`, `Mt.`→`mount`, remove punctuation.
   - Look up in the gazetteer dict. If several entries share (city,state) pick the highest population.
   - If not found: try fuzzy match within the same state (e.g., `difflib.get_close_matches`, cutoff 0.9); mark `geocode_quality="fuzzy"`.
   - If still not found: keep `latitude=None`; count as unresolved; **print the list**.
   - Optional manual override file `data/manual_geocodes.csv` (`city,state,lat,lng`) for the handful of misses.
5. **Flag outliers:** compute median and MAD of prices; `is_price_outlier = price > median + 4*MAD` (or a simple absolute threshold, e.g. > $5). Do not remove.
6. **Upsert** into `FuelStation` in a single transaction with `bulk_create(update_conflicts=True, unique_fields=["opis_id"], update_fields=[...])`.
7. **Write `ImportRun`** and **print a summary**:

```
Rows read:                8151
Dropped (non-US):          620
US rows:                  7531
Unique stations:          6626
IDs with multiple prices:  568  (rule=median)
Geocoded (city match):    ~6600
Unresolved:                  N   (listed below)
Price outliers flagged:      K
```

### 13.2 Gazetteer sources (free) — pick one, **verify its license, and attribute it in the README**
- **GeoNames** (`cities1000` / US dump) — CC BY 4.0 (verify).
- **SimpleMaps US Cities Basic** — free tier, attribution required (verify).
- **US Census Gazetteer files** (places) — public domain, but "places" ≠ every small town; still good coverage.
- Fallback for stragglers: one-time Nominatim run (`1 req/s`, set a descriptive `User-Agent`, cache results into `manual_geocodes.csv`). Do this **at import, never at request time.**

> Sandbox note for an AI agent: some sandboxes block outbound network. If the gazetteer cannot be downloaded, write the importer to accept a
> path argument and document where to obtain the file; include a small **fixture gazetteer** for tests so the pipeline is still verifiable offline.

### 13.3 Idempotency
Re-running the import must not duplicate rows (upsert on `opis_id`) and must bump the `data_version`.

### 13.4 Tests for the importer (offline, tiny fixture CSV)
- Canadian rows dropped.
- Duplicate IDs merged with the configured rule (`median`, `min`, `max`).
- Name selection deterministic.
- Unresolved cities are reported, not crashed on.
- Re-import is idempotent (row count unchanged).

---

## 14. The request pipeline (online, per call)

Time budget guideline (warm, excluding the OSRM network call): **< 50 ms**. With one OSRM call (~100–800 ms typical, network-dependent): total typically < 1.5 s cold; **< 20 ms warm** (cache hit).

1. **Parse & validate** query/body → `start`, `finish`, optional `range_miles`, `mpg`, `starting_fuel_gallons`, `corridor_miles`, `geometry` (`simplified|full|none`).
2. **Cache lookup** with a normalized key (§19). Hit → return immediately (add `meta.cache="hit"`).
3. **Resolve endpoints** (§9.6): 0 external calls typically.
4. **Routing call** — exactly one to the provider. Errors: timeout → 504; non-200/`NoRoute` → 422 or 502 as appropriate.
5. **Build polyline arrays** (numpy): lon/lat → local planar miles; densify to ≈1-mile spacing; cumulative distance; scale so `cum[-1] == osrm_distance_miles`.
6. **Corridor match** (§15): `cKDTree.query_ball_point` from stations (or route points) → candidates with `mile_marker` and `distance_from_route_miles`.
7. **Optimize** (§16): returns purchases or raises `InfeasibleRoute(gap_start_mile, gap_end_mile)`.
8. **Assemble response** (§17).
9. **Cache store** (TTL e.g. 24h) and return.
10. **Log** one structured line: `route ms=…, osrm_ms=…, candidates=…, stops=…, external_calls=1, cache=miss`. Put a sample of this in the Loom/README as evidence of the call budget.



---

## 15. Corridor matching (stations near the route)

**Goal:** from ~6.6k stations, find the ones within `corridor_miles` of the route and give each a **mile marker**
(distance along the route from the origin) and an **offset** (distance off the route).

**Method (verified on a synthetic Dallas→Chicago route; see code below):**
1. Take the OSRM geometry ([lon,lat] list). Densify to ≤ 1-mile spacing (`densify`).
2. Cumulative distance (`cumulative_miles`) and **rescale so the last value equals OSRM's distance** (trap B5).
3. Project route points and stations to a local planar frame in miles (equirectangular around the mean route latitude; error is negligible at corridor scale).
4. Build a `cKDTree` on the **route points** (~1 per mile), query all stations with `distance_upper_bound=corridor_miles`. The nearest route point's cumulative distance is the station's mile marker.
5. Sort by mile marker.

Why index the route instead of the stations? Query cost is O(stations · log route_points) with ~6.6k stations: sub-millisecond to a few ms. No need for a persistent station tree for this step (the station arrays are kept in memory as numpy arrays: `st_lat, st_lon, st_ids, st_prices`).

Accuracy notes: station coordinates are city centroids, so `offset_miles` is approximate. Corridor default 5 mi; allow up to 15.

### 15.1 Reference code (`geo.py` + `corridor.py`) — tested

```python
from __future__ import annotations
import math
from dataclasses import dataclass, field
import numpy as np
from scipy.spatial import cKDTree

EARTH_R_MI = 3958.7613
EPS = 1e-6

# ---------- geo.py ----------
def haversine_miles(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dl = np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dphi/2)**2 + np.cos(p1)*np.cos(p2)*np.sin(dl/2)**2
    return 2*EARTH_R_MI*np.arcsin(np.sqrt(a))

def to_local_xy(lat, lon, lat0):
    """Equirectangular projection to miles around reference latitude lat0."""
    x = np.radians(lon) * EARTH_R_MI * math.cos(math.radians(lat0))
    y = np.radians(lat) * EARTH_R_MI
    return np.column_stack([x, y])

def densify(lat, lon, step_miles=1.0):
    """Insert points so consecutive spacing <= step_miles (linear in lat/lon)."""
    lat = np.asarray(lat, float); lon = np.asarray(lon, float)
    out_lat=[lat[0]]; out_lon=[lon[0]]
    for i in range(1, len(lat)):
        d = float(haversine_miles(lat[i-1], lon[i-1], lat[i], lon[i]))
        n = max(1, int(math.ceil(d/step_miles)))
        for k in range(1, n+1):
            t = k/n
            out_lat.append(lat[i-1] + t*(lat[i]-lat[i-1]))
            out_lon.append(lon[i-1] + t*(lon[i]-lon[i-1]))
    return np.array(out_lat), np.array(out_lon)

def cumulative_miles(lat, lon, total_miles=None):
    seg = haversine_miles(lat[:-1], lon[:-1], lat[1:], lon[1:])
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    if total_miles is not None and cum[-1] > 0:
        cum *= total_miles / cum[-1]      # scale so final == provider distance
    return cum

# ---------- corridor.py ----------
@dataclass
class Candidate:
    station_id: int
    mile: float
    price: float
    offset_miles: float

def match_corridor(route_lat, route_lon, cum_miles, st_lat, st_lon, st_ids, st_prices, corridor_miles=5.0):
    lat0 = float(np.mean(route_lat))
    R = to_local_xy(route_lat, route_lon, lat0)
    S = to_local_xy(st_lat, st_lon, lat0)
    tree = cKDTree(R)                       # index the ROUTE points (~1 per mile), query stations
    dist, idx = tree.query(S, k=1, distance_upper_bound=corridor_miles)
    out = []
    for j in np.where(np.isfinite(dist))[0]:
        out.append(Candidate(int(st_ids[j]), float(cum_miles[idx[j]]), float(st_prices[j]), float(dist[j])))
    out.sort(key=lambda c: c.mile)
    return out
```

Naming note: `corridor.Candidate` (has `offset_miles`) and `optimizer.Candidate` (no offset) are different classes. In the real project rename the corridor one to `CorridorHit` and convert to `optimizer.Candidate` in `planner.py`.

Known limitation (documented, trap C10): a station near two far-apart parts of a looping route is assigned to the nearest route point only.

---

## 16. The optimizer

### 16.1 Problem statement
Given a route of length `D` miles, stations `i` at mile `m_i` with price `p_i` ($/gal), tank capacity `T = range/mpg` gallons
(50), consumption `1/mpg` gal/mile, and starting fuel `f0`: choose purchase amounts `g_i ≥ 0` so the vehicle never runs dry and
never exceeds `T`, minimizing `Σ p_i · g_i`. Arrival fuel at the destination may be anything ≥ 0; at optimum it is 0 unless the start fuel was in surplus.

This is the classic **"gas station problem" on a line**.

### 16.2 Algorithm (greedy with lookahead) — optimal for this problem
At each station `i` with current fuel `f`:
1. Find the **nearest station ahead within range whose price ≤ p_i** (the destination counts as a station of price 0).
2. If it exists: buy `max(0, (distance to it)/mpg − f)` — just enough to reach it.
3. Otherwise: **fill the tank** (`T − f`); every reachable station ahead is more expensive.
4. Never buy less than needed to reach the next node; never exceed `T`.
5. If the gap to the next node (or from the origin to the first node, given start fuel) exceeds range → `InfeasibleRoute(gap_start, gap_end)`.

Why optimal (explain in README in 3 sentences): fuel bought at a station is only worth buying if no cheaper source is reachable
before it is needed; buying exactly enough to reach the next cheaper-or-equal station, or the full tank when none exists, can't be
improved by exchange argument (swapping a gallon bought here for one bought at a cheaper reachable station never costs more). Don't claim more than
that, **and back it with the oracle test below.**

### 16.3 Reference implementation — `optimizer.py` (pure, no Django) — TESTED
```python
"""Pure min-cost refuelling optimizer. No Django, no network."""
from __future__ import annotations
from dataclasses import dataclass

EPS = 1e-6


class InfeasibleRoute(Exception):
    def __init__(self, gap_start_mile: float, gap_end_mile: float, range_miles: float):
        self.gap_start_mile, self.gap_end_mile, self.range_miles = gap_start_mile, gap_end_mile, range_miles
        super().__init__(
            f"No fuel station reachable between mile {gap_start_mile:.0f} and mile {gap_end_mile:.0f} "
            f"(gap {gap_end_mile - gap_start_mile:.0f} mi > range {range_miles:.0f} mi)"
        )


@dataclass(frozen=True)
class Candidate:
    station_id: int
    mile: float            # distance from origin along the route
    price: float           # USD per gallon


@dataclass(frozen=True)
class Purchase:
    station_id: int
    mile: float
    price: float
    gallons: float
    cost: float
    arrival_gallons: float
    reason: str


@dataclass(frozen=True)
class Plan:
    purchases: list
    gallons_purchased: float
    gallons_consumed: float
    ending_gallons: float
    total_cost: float


def plan_refuelling(candidates, total_miles, range_miles=500.0, mpg=10.0, start_gallons=None):
    tank = range_miles / mpg
    fuel = tank if start_gallons is None else float(start_gallons)
    fuel = min(fuel, tank)
    stops = sorted((c for c in candidates if -EPS <= c.mile <= total_miles + EPS), key=lambda c: c.mile)
    DEST = Candidate(-1, total_miles, 0.0)       # destination = free "station", end of route
    nodes = stops + [DEST]

    # Leg from origin to first node
    first_leg = nodes[0].mile
    if first_leg > fuel * mpg + EPS:
        raise InfeasibleRoute(0.0, first_leg, fuel * mpg)
    fuel -= first_leg / mpg

    purchases, cost_total, bought = [], 0.0, 0.0
    for i, n in enumerate(nodes[:-1]):
        nxt = nodes[i + 1]
        if nxt.mile - n.mile > range_miles + EPS:
            raise InfeasibleRoute(n.mile, nxt.mile, range_miles)
        arrival = fuel
        cheaper = None
        for m in nodes[i + 1:]:
            if m.mile - n.mile > range_miles + EPS:
                break
            if m.price <= n.price + EPS:
                cheaper = m
                break
        if cheaper is not None:
            need = (cheaper.mile - n.mile) / mpg
            buy = max(0.0, need - fuel)
            reason = "buy just enough to reach a cheaper stop ahead" if cheaper.station_id != -1 \
                else "buy just enough to reach destination"
        else:
            buy = tank - fuel
            reason = "cheapest in range ahead: fill tank"
        # always be able to reach the next node
        buy = max(buy, (nxt.mile - n.mile) / mpg - fuel, 0.0)
        buy = min(buy, tank - fuel)
        if buy > EPS:
            c = buy * n.price
            purchases.append(Purchase(n.station_id, n.mile, n.price, buy, c, arrival, reason))
            cost_total += c
            bought += buy
            fuel += buy
        fuel -= (nxt.mile - n.mile) / mpg
        if fuel < -1e-6:
            raise InfeasibleRoute(n.mile, nxt.mile, range_miles)
    return Plan(purchases, bought, total_miles / mpg, max(fuel, 0.0), cost_total)
```

### 16.4 Verification harness (DP oracle) — `tests/test_optimizer_oracle.py`
Discretises fuel in 0.1-gallon units and runs an exact dynamic program. **Result when run during planning (30 Sept 2026, Python 3.12): 350 feasible random cases — all within $0.08 of the oracle (discretisation tolerance), 250 infeasible cases — oracle and optimizer agree every time, fuel conservation holds on every feasible case. 0 failures.**
Use mile markers that are multiples of 10 in the random cases so the 0.1-gal grid aligns exactly with the real arithmetic.

```python
import random, math
from optimizer import *

def oracle(cands, total, range_miles=500.0, mpg=10.0, start=None):
    tank=range_miles/mpg; start=tank if start is None else start
    U=10; cap=int(round(tank*U))
    nodes=sorted(cands,key=lambda c:c.mile)+[Candidate(-1,total,0.0)]
    INF=1e18; dp=[INF]*(cap+1); dp[int(round(start*U))]=0.0; prev=0.0
    for n in nodes:
        u=math.ceil((n.mile-prev)/mpg*U-1e-9)
        nd=[INF]*(cap+1)
        for f in range(cap+1):
            if dp[f]<INF and f-u>=0: nd[f-u]=min(nd[f-u],dp[f])
        dp=nd
        for f in range(1,cap+1):
            if dp[f-1]<INF: dp[f]=min(dp[f],dp[f-1]+n.price/U)
        prev=n.mile
    return min(dp)

random.seed(7); ok=bad=infeas_match=0
for t in range(600):
    total=random.choice([300,700,1200,2000,2800])
    k=random.randint(1,45)
    cands=[Candidate(i,round(random.uniform(0,total)/10)*10,round(random.uniform(2.7,4.5),3)) for i in range(k)]
    start=random.choice([None,0.0,20.0])
    try:
        p=plan_refuelling(cands,total,start_gallons=start)
    except InfeasibleRoute:
        p=None
    o=oracle(cands,total,start=start)
    if p is None:
        if o>=1e17: infeas_match+=1
        else: bad+=1; print("false infeasible",t)
        continue
    ok+=1
    # conservation
    start_g=50.0 if start is None else start
    assert abs(start_g+p.gallons_purchased-p.gallons_consumed-p.ending_gallons)<1e-6, "conservation"
    assert all(0<=x.arrival_gallons+x.gallons<=50+1e-6 for x in p.purchases)
    if abs(p.total_cost-o)>0.08: bad+=1; print("MISMATCH",p.total_cost,o)
print("feasible matched",ok,"| infeasible agreed",infeas_match,"| failures",bad)
```

Convert the script into pytest (`def test_...`) form; keep the seed fixed for reproducibility, and add a second parametrization with `range_miles=1000`.

### 16.5 Required unit tests (beyond the oracle)
1. **Short trip:** D=300, start full → `purchases == []`, cost 0.
2. **One-stop:** D=700, one cheap station at mile 400 → buys exactly enough to finish (≥ `700/10 − 50 + ...` computed), not a full tank.
3. **Cheaper ahead:** station A $4.00 at mile 100, B $3.00 at mile 300 → at A buy only enough to reach B.
4. **Cheapest first:** A $3.00 at mile 100, B $4.00 at mile 300 → at A fill the tank.
5. **Equal prices** → no needless fill (tie rule `<=`).
6. **Infeasible gap:** stations at mile 100 and mile 700 (range 500) → `InfeasibleRoute` with `gap_start≈100`, `gap_end≈700`.
7. **Origin gap:** first station at mile 600, start full → infeasible; with `start_gallons=0` and first station at 10 → infeasible.
8. **Conservation:** `start + purchased − consumed == ending` everywhere.
9. **Capacity:** `arrival + purchased ≤ tank` at every stop.
10. **Candidates beyond the destination / behind the origin** are ignored.
11. **Range parameter respected** (`range_miles=1000` makes LA→Seattle feasible if the real gap is 877 mi).

---

## 17. API contract

### 17.1 Endpoints
| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/api/route/` | Main endpoint: plan route + fuel stops + cost |
| GET | `/map/` | HTML Leaflet page; same params; renders the plan |
| GET | `/api/health/` | `{"status":"ok","stations_loaded":6xxx,"data_version":"..."}`; 503 if no data |
| GET | `/` | Tiny landing page with examples |

### 17.2 Request
```
GET /api/route/?start=Dallas,TX&finish=Chicago,IL
GET /api/route/?start=32.7767,-96.7970&finish=Chicago,IL&range_miles=500&mpg=10&starting_fuel_gallons=50&corridor_miles=5&geometry=simplified
POST /api/route/   {"start":"Dallas, TX","finish":"Chicago, IL"}
```
| Param | Type | Default | Bounds |
|---|---|---|---|
| `start` | str | required | `City, ST` or `lat,lng` or free text |
| `finish` | str | required | same |
| `range_miles` | float | 500 | 50–1500 |
| `mpg` | float | 10 | 1–50 |
| `starting_fuel_gallons` | float | tank size | 0–tank |
| `corridor_miles` | float | 5 | 1–15 |
| `geometry` | enum | `simplified` | `simplified`/`full`/`none` |

### 17.3 Success response (200) — FROZEN schema
```json
{
  "start":  {"input": "Dallas, TX", "resolved": "Dallas, TX", "lat": 32.7767, "lng": -96.797, "source": "gazetteer"},
  "finish": {"input": "Chicago, IL", "resolved": "Chicago, IL", "lat": 41.8781, "lng": -87.6298, "source": "gazetteer"},
  "route": {
    "distance_miles": 925.4,
    "duration_hours": 14.2,
    "geometry": {"type": "LineString", "coordinates": [[-96.797, 32.7767], "..."]},
    "geometry_points": 420,
    "provider": "osrm"
  },
  "vehicle": {"range_miles": 500, "mpg": 10, "tank_gallons": 50, "starting_fuel_gallons": 50},
  "fuel_stops": [
    {
      "order": 1,
      "station_id": 1234,
      "name": "PILOT TRAVEL CENTER #1243",
      "address": "I-44, EXIT 283 & US-69",
      "city": "Big Cabin",
      "state": "OK",
      "lat": 36.54,
      "lng": -95.22,
      "mile_marker": 276.3,
      "distance_from_route_miles": 0.8,
      "price_per_gallon_usd": 3.007,
      "arrival_fuel_gallons": 22.4,
      "gallons_purchased": 27.6,
      "cost_usd": 83.00,
      "reason": "cheapest in range ahead: fill tank"
    }
  ],
  "summary": {
    "total_fuel_cost_usd": 241.17,
    "gallons_purchased": 76.4,
    "gallons_consumed": 92.54,
    "ending_fuel_gallons": 33.86,
    "average_price_paid_per_gallon_usd": 3.157,
    "number_of_stops": 2
  },
  "map_url": "/map/?start=Dallas,TX&finish=Chicago,IL",
  "assumptions": {
    "starting_fuel": "Vehicle starts with a full tank; fuel already in the tank is not billed.",
    "price_rule": "median of duplicate CSV rows per station ID",
    "station_locations": "approximate: city centroid",
    "corridor_miles": 5,
    "detours": "Stations within the corridor are treated as on-route; detour miles are not charged."
  },
  "meta": {"external_calls": 1, "cache": "miss", "compute_ms": 12, "total_ms": 640, "data_version": "2026-10-01T10:00:00Z"}
}
```
(Numbers above are illustrative, not real output.)

### 17.4 Errors — JSON, never HTML, never bare 500
```json
{"error": {"code": "NO_FUEL_STATION_IN_RANGE", "message": "No fuel station reachable between mile 100 and mile 977 ...", "details": {"gap_start_mile": 100, "gap_end_mile": 977, "range_miles": 500}}}
```
| HTTP | `code` | When |
|---|---|---|
| 400 | `INVALID_PARAMS` | missing/invalid params, out-of-bounds values |
| 400 | `LOCATION_NOT_IN_US` / `LOCATION_NOT_FOUND` / `AMBIGUOUS_LOCATION` | geocoding failures |
| 422 | `NO_ROUTE` | provider says no drivable route (e.g. mainland → Hawaii) |
| 422 | `NO_FUEL_STATION_IN_RANGE` | infeasible gap |
| 502 | `ROUTING_PROVIDER_ERROR` | upstream bad response |
| 503 | `FUEL_DATA_NOT_LOADED` | importer not run |
| 504 | `ROUTING_PROVIDER_TIMEOUT` | upstream timeout |

---

## 18. The map page (`/map/`)

- Single template `map.html`; Leaflet from a CDN (unpkg or cdnjs); OSM tiles.
- The page fetches `/api/route/` with the same query string (fetch in browser JS), then:
  - draws the GeoJSON polyline,
  - numbered markers for start (green), stops (orange, numbered), finish (red),
  - popups: station name, city/state, price, gallons, cost, mile marker,
  - side panel: totals (distance, stops, gallons, **total cost**), and the assumptions list,
  - error banner when the API returns an error.
- No API keys. No server-side map calls. Mention in README: tiles are loaded by the viewer's browser.
- Add a small form (start, finish, Go) so the reviewer can try other routes without Postman.
- Test: GET `/map/` returns 200 and contains `leaflet`.

---

## 19. Caching and performance budget

### 19.1 Cache key
`sha256(json.dumps({s: norm(start), f: norm(finish), range, mpg, start_fuel, corridor, geometry, price_rule, data_version}, sort_keys=True))`.
`norm()` = casefold, collapse whitespace, round coordinates to 4 dp.
TTL 24 h. Backend: `LocMemCache` default; Redis if `REDIS_URL` is set.

### 19.2 Optional second cache
Cache the **routing provider response** separately (key = start/end coords rounded to 3 dp, TTL 7 days) so changing `mpg`/`range` doesn't cost another OSRM call. This is a real, defensible optimisation: "vehicle params change the plan, not the road."

### 19.3 Targets (publish measured values in README)
| Scenario | Target |
|---|---|
| Cache hit | < 20 ms |
| Cache miss, provider response cached | < 100 ms |
| Cache miss, OSRM call | provider latency + < 100 ms of compute |
| Compute only (corridor + optimizer) for ~2,800-mile route | < 100 ms |

Measure with `time.perf_counter()` around each stage, expose `meta.compute_ms`, `meta.total_ms`, and run 20 repetitions in `scripts/bench.py`; paste p50/p95 in the README.

### 19.4 Other performance notes
- Load station arrays once (module-level singleton guarded by a lock) — trap E1.
- numpy for vector math; no Python loops over all 6.6k stations per request.
- Simplify geometry for the response (Douglas–Peucker / `shapely.simplify` or a tiny hand-rolled one) — trap B4.
- `requests.Session` with connection reuse for OSRM.

---

## 20. Testing plan

Run: `pytest -q`. Zero network. Target: all green, < 10 s.

| File | Covers |
|---|---|
| `test_optimizer.py` | §16.5 unit cases |
| `test_optimizer_oracle.py` | randomized comparison to the DP oracle, feasible + infeasible |
| `test_geo.py` | haversine (Dallas–Chicago ≈ 800 mi crow-flies), densify spacing ≤ 1 mi, cumulative scaling equals provider distance, lon/lat order regression |
| `test_corridor.py` | stations on route included; stations 50 mi away excluded; mile markers monotonic; offsets ≤ corridor |
| `test_import.py` | fixture CSV: Canada dropped, duplicates merged by rule, unresolved listed, idempotent |
| `test_api.py` | with a mocked provider: 200 happy path (schema), `external_calls == 1`, 400 non-US, 400 missing params, 422 gap, 502/504 mapping, cache hit (provider called once for two identical requests), `GET` and `POST` equivalence, `/map/` 200, `/api/health/` |
| `test_geocode.py` | gazetteer lookup, ambiguity handling, `lat,lng` parsing, US bounding validation |

Mock the provider by injecting it (dependency injection through `planner.plan(start, finish, provider=...)`, default from settings) — no monkeypatch hacks.

CI (optional, nice): GitHub Actions workflow running `pytest` on push. Add a badge to the README.

---

## 21. Configuration (`.env.example`)

```
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgres://postgres:postgres@db:5432/fuel      # or sqlite:///db.sqlite3
REDIS_URL=                                                   # empty => locmem cache
ROUTING_PROVIDER=osrm                                        # osrm | ors
OSRM_BASE_URL=https://router.project-osrm.org
ORS_API_KEY=
ROUTING_TIMEOUT_SECONDS=10
NOMINATIM_USER_AGENT=spotter-fuel-route-assessment (your-email@example.com)
PRICE_AGGREGATION=median                                     # median|min|max|mean
DEFAULT_RANGE_MILES=500
DEFAULT_MPG=10
DEFAULT_CORRIDOR_MILES=5
```
Settings read these via `os.environ`/`django-environ`. No secrets in the repo.

---

## 22. Docker and local run

### 22.1 Windows-friendly local run (candidate uses Windows + PowerShell; project dir `D:\Projects\Backend Django`)
```powershell
cd "D:\Projects\Backend Django"
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope Process Bypass
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py import_fuel_prices data\fuel-prices-for-be-assessment.csv --gazetteer data\us_cities.csv
python manage.py runserver
```
SQLite is the zero-setup default (`DATABASE_URL` unset → `sqlite:///db.sqlite3`).

### 22.2 Docker
`docker compose up --build` → web (gunicorn) + Postgres (+ optional Redis profile). Entry script runs `migrate` and, if the table is empty, the import.
Keep the Dockerfile small (python:3.12-slim, non-root user, `PYTHONUNBUFFERED=1`).

### 22.3 GCP (bonus, one paragraph only)
"Container-ready for Cloud Run; Postgres → Cloud SQL; Redis → Memorystore." Do not build infra.

---

## 23. README requirements
Sections, in order:
1. One-paragraph pitch + a screenshot/GIF of `/map/`.
2. **Quick start** (3 commands) for SQLite, and Docker.
3. **Example request/response** (trimmed).
4. **How it works** (the pipeline diagram from §10.2, 6 lines).
5. **Requirement → implementation traceability table** (copy §3.2, filled with real file paths).
6. **Assumptions table** (§9) — each with the setting that changes it.
7. **Data handling** (Canada dropped, duplicates → median, outliers flagged, geocoding approach, unresolved count).
8. **Optimality**: the 3-sentence argument + "verified against a DP oracle on N random cases".
9. **Performance**: measured latency table; external call count per request (1).
10. **Error contract** table.
11. **Testing**: how to run, what's covered.
12. **Known limitations** (city-centroid accuracy; no detour costing; public OSRM best-effort; sparse West-coast stations → some routes infeasible at 500 mi).
13. **Future work** (PostGIS, truck-specific routing, real-time prices, detour-aware planning, Redis).
14. Attribution (gazetteer, OSM, OSRM).

Tone: precise, no hype, no claims you cannot demonstrate (trap F8).

---

## 24. The Loom video script (≤ 5:00; target 4:30)

Setup: Loom with screen + camera, Postman collection open, VS Code open, browser tab on `/map/`. Rehearse twice. Say everything *once*.

| Time | Content |
|---|---|
| 0:00–0:20 | "Hi, I'm Anukul. This is my fuel-route API in Django 6.1. Input: two US locations. Output: route, cheapest fuel stops with a 500-mile range at 10 mpg, and total fuel cost." |
| 0:20–1:30 | **Postman, long trip** (e.g. New York, NY → Los Angeles, CA, or a sparse-West-safe one like Dallas → Chicago). Show request, response, point out `fuel_stops`, `total_fuel_cost_usd`, `meta.external_calls: 1`, and `meta.total_ms`. |
| 1:30–2:00 | **Map page**: same trip drawn on Leaflet with numbered stops. |
| 2:00–2:30 | **Cache hit**: re-send; show `cache: "hit"` and milliseconds. **Short trip**: no stops needed. |
| 2:30–2:50 | **Error case**: LA → Seattle with default range → 422 naming the gap; then `range_miles=1000` succeeds. |
| 2:50–4:00 | **Code tour**: `import_fuel_prices.py` (geocoded once, Canada dropped, duplicates → median), `optimizer.py` (greedy + why optimal), `test_optimizer_oracle.py` (DP oracle), `services/planner.py` (single routing call). |
| 4:00–4:30 | **Run `pytest`** — green. State assumptions: starts full, price rule, city-centroid accuracy. |
| 4:30–4:50 | Close: limitations + what I'd do next (PostGIS, detour-aware). "Thanks for watching." |

Do's: speak plainly, show real numbers. Don'ts: scroll through huge files, read code line by line, apologise, exceed 5:00.
Publish the Loom link as "anyone with link can view" and test it in an incognito window.

---

## 25. Submission checklist and reply email

### 25.1 Checklist (tick all)
- [ ] Django **6.1.x** latest (`pip index versions django` rechecked on submission day)
- [ ] `pytest` green offline; oracle test included
- [ ] Verified exactly **1** OSRM call per uncached request (log line + test)
- [ ] 400/422/502/504 paths demonstrated
- [ ] README complete (§23) with measured latency numbers
- [ ] `.env.example` present, no secrets, no `.venv`, no `db.sqlite3`, no `__pycache__` in git
- [ ] `data/` contains the CSV and the gazetteer (or clear download instructions)
- [ ] Repo **public** (or access granted) and cloned fresh to confirm the quick start works
- [ ] Loom ≤ 5:00, public link, tested logged out
- [ ] Postman collection exported to `docs/`
- [ ] Replied **in the thread/question the email says** with both links
- [ ] Submitted ≥ 12 hours before the deadline (target: Thu 1 Oct)

### 25.2 Reply email template
```
Subject: Re: Backend Django Engineer | Assessment — Fuel Route API (Anukul)

Hi Ena,

Here is my submission for the Backend Django assessment.

GitHub: <repo link>
Loom (≤5 min): <loom link>

Summary: Django 6.1 + DRF API that takes a US start/finish, makes a single OSRM routing call,
finds fuel stations along the route from the provided CSV (geocoded once at import), and plans
the lowest-cost fuel stops for a 500-mile range at 10 mpg. It returns the route (GeoJSON + a
Leaflet map page), the stops, and total fuel cost. The optimizer is verified against an exact
dynamic-programming oracle in the test suite. Assumptions and limitations are listed in the README.

Happy to walk through anything.

Thanks,
Anukul
```

---

## 26. Timeline (deadline Fri 2 Oct; plan to finish Thu 1 Oct)

| When | Work | Exit criteria |
|---|---|---|
| **Wed 30 Sept (today), evening** | Phase 0–2: scaffold, importer, gazetteer, geo/corridor/optimizer + oracle tests | `pytest` green for pure modules; DB loaded; unresolved cities reviewed |
| **Thu 1 Oct, morning** | Phase 3–4: OSRM provider, planner, API, errors, cache, `/map/`, health | Postman works end-to-end for 4 scenarios; external_calls = 1 |
| **Thu 1 Oct, afternoon** | Phase 5: tests complete, benchmark, README, Docker, Postman collection, sample responses | README measured numbers filled |
| **Thu 1 Oct, evening** | Loom (2 takes), push, clean-clone verification, submit | Checklist §25 all ticked |
| **Fri 2 Oct** | Buffer only | — |

---

## 27. Definition of Done
1. Fresh clone → 3 commands → `/api/route/?start=Dallas,TX&finish=Chicago,IL` returns the frozen schema.
2. Optimizer matches the DP oracle in tests (feasible and infeasible).
3. Exactly 1 routing call per uncached request; 0 per cached.
4. All error codes in §17.4 reachable and tested.
5. README honest and complete; Loom ≤ 5 min; links public.

---

## 28. Instructions for an AI agent implementing this

You are a coding agent (e.g. OpenAI Codex CLI) working in `D:\Projects\Backend Django` on Windows/PowerShell.
Files present at the start: `action.md` (this file), `fuel-prices-for-be-assessment.csv`.

**Rules of engagement**
1. Read this entire file first. It is the specification and the context. **Do not treat it as a to-do list to execute in one go.** Work only on the phase the human asks for, then stop and report.
2. Do not invent requirements; if something is ambiguous, pick the documented default (§9), note it, and continue. Ask only if blocked.
3. Do not call external services (OSRM, Nominatim, geocoders) from tests. Mock them.
4. Never commit secrets. Never download datasets without saying what/where from.
5. Keep modules small and pure (§10.3). The optimizer imports nothing from Django.
6. After each phase: run tests, run `python manage.py check`, show a short summary of files created and results, list any deviations from this document.
7. Use the reference code in §15 and §16 as the starting point — it is already tested; do not "improve" the algorithm without re-running the oracle test.
8. Prefer boring, readable code with type hints and docstrings. No over-engineering (no Celery/K8s).
9. Pin: `Django==6.1.1`, `djangorestframework==3.18.1` (re-check with `pip index versions`).
10. Windows: use `pathlib`, `newline=""`, UTF-8; no bash-only commands in docs unless also giving PowerShell.

**Phases**
- **Phase 0** — Scaffold: venv instructions, `requirements.txt`, Django project `config`, app `routing`, settings from env, `.gitignore`, `.gitattributes`, `.env.example`, `pytest.ini`, move CSV into `data/`.
- **Phase 1** — Data: `FuelStation` model + migration; `import_fuel_prices` command (§13) + tests with a small fixture; gazetteer handling (download instructions or fixture); summary output.
- **Phase 2** — Pure logic: `geo.py`, `corridor.py`, `optimizer.py` from §15/§16 + all unit tests + oracle test.
- **Phase 3** — Integration: `providers/osrm.py`, `providers/geocode.py`, `station_index.py`, `services/planner.py`, `views.py`, `serializers.py`, `errors.py`, cache, `/api/health/`; mocked API tests.
- **Phase 4** — Presentation: `/map/` page, landing page, Postman collection, sample responses, `scripts/bench.py`.
- **Phase 5** — Packaging: Dockerfile, docker-compose, README (§23), CI workflow (optional), final audit against §6 and §25.

---

## 29. FAQ / objections

**Q: Why not PostGIS?** Overkill for 6.6k points; a KD-tree meets the latency goal with fewer moving parts. Mention as future work.
**Q: Why city-centroid geocoding?** The CSV only has exit strings; centroids are the only offline, reproducible, zero-call option. Accuracy is a few miles against a 500-mile range.
**Q: Why median for duplicate prices?** The file doesn't define the duplicates; median is robust and not optimistic; it's configurable.
**Q: Does starting with a full tank game the result?** It's stated, configurable (`starting_fuel_gallons=0`), and gallons consumed are reported so the reviewer can compute either convention.
**Q: What if OSRM public is down during review?** Cached responses and `docs/sample_responses/`; provider interface lets you switch to ORS via env.
**Q: Is greedy really optimal with equal prices and capacity limits?** Yes for the line version with a tie rule of `<=`; backed by the oracle test.
**Q: Will detours matter?** They are ignored by design; the corridor is narrow; reported as a limitation.
**Q: Is the OSRM call truly the only external call?** For `City, ST` or `lat,lng` inputs, yes. Free-text inputs add up to two Nominatim calls (≤3 total), reported in `meta.external_calls`.

---

## 30. Appendix A — verified numbers
| Fact | Value | Where verified |
|---|---|---|
| Latest Django on PyPI | **6.1.1** | `pip index versions django`, 30 Sept 2026 |
| Latest DRF on PyPI | **3.18.1** | same |
| Python in planning sandbox | 3.12.3 (numpy 2.4.4, scipy 1.17.1) | sandbox |
| CSV rows | 8,151 (7,531 US + 620 Canada) | pandas profile |
| Unique US station IDs | 6,626 | pandas |
| IDs with multiple prices | 568 (max spread $0.90) | pandas |
| Unique (address,city,state) US | 6,325 | pandas |
| Price range | $2.687–$6.399, median ≈ $3.43 | pandas |
| States in file | 48 lower-48 + 9 Canadian | pandas |
| CA / OR / WA stations | 8 / 29 / 52 | pandas |
| Optimizer vs DP oracle | 350 feasible matched, 250 infeasible agreed, 0 failures | sandbox run |
| Corridor code | ran on synthetic Dallas–Chicago route; 201 candidates within 5 mi, all offsets ≤ 5 | sandbox run |

Not verified (verify yourself): OSRM public-server usage terms and rate limits; OpenRouteService current free quota; gazetteer licence text; Django 6.1 `CheckConstraint(condition=...)` signature against installed docs.

## 31. Appendix B — sources
- Recruiter email (Spotter, 29 Sept 2026) — the assignment text in §3.
- Spotter AI careers page: "Remote Backend Django Engineer – AI & Algorithmic Systems" (careers.spotter.ai).
- Public GitHub submissions listed in §5 (read for patterns only).
- PyPI (django, djangorestframework) for versions.
- Local analysis of `fuel-prices-for-be-assessment.csv`.

## 32. Appendix C — cheat-sheet
```
miles = meters / 1609.344
tank_gallons = range_miles / mpg                  # 500/10 = 50
gallons_consumed = total_miles / mpg
conservation: start + purchased - consumed == ending
OSRM URL: {base}/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson&steps=false
GeoJSON/OSRM = [lon, lat];  Leaflet = [lat, lng]
HTTP: 400 bad input | 422 infeasible/no route | 502 upstream bad | 503 data missing | 504 upstream timeout
Rounding: money 2dp; total = sum of rounded stop costs
```

*End of ACTION.md*