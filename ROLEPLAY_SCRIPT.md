# Brand Performance Manager — AI Role-play Script

A timed talk track for the **Submission – AI role-play** (Customer Skills domain). You present
once to two personas in the same room:

- **Business stakeholder:** VP Commercial at NovaLife Nutrition, the person who funds the decision. Cares
  about share, revenue, team productivity and risk.
- **Technical stakeholder:** Head of Data / Enterprise Architect, who has to run what you built. Cares
  about governance, identity, reliability, cost and how it grows.

Deck: `brand-performance-manager-reference-architecture.pptx`. Each slide's speaker notes hold the
short version of this script.

---

## 1. How each scoring criterion is covered

| Criterion | Where you earn it | The behavior they're scoring |
|---|---|---|
| **Demo setup** | Slide 1 (0:00–2:00) | Name the customer, the problem in their words, and the three things you'll show, *before* any screen. |
| **Tell-show-tell** | Slide 3 → live app → Slide 4 | Say the 3 moments + KPIs → demo exactly those → land "what you just saw means…" |
| **Value communication** | Slides 2, 3, 8 + every demo landing | Lead with outcomes and their KPIs (share, $, time to insight). Never "and here's another feature". |
| **Reading the room** | Q&A, slides 4–6 | Answer at the altitude of whoever asked, then add a one-line bridge for the other person. |
| **Professionalism** | Throughout | Calm pace, signpost transitions, handle objections with Acknowledge → Clarify → Respond → Confirm. |

---

## 2. Pre-flight checklist (do this 15 min before)

The demo depends on live services. Supervisors and the app have been deleted before; check them first.

- [ ] App loads: https://<app-url>
- [ ] **Warm the path.** Ask one suggested question end to end and confirm it. This wakes the SQL
      warehouse, the supervisor endpoint and Lakebase, which **suspends after 5 idle minutes**.
- [ ] The Advisor tab shows the "Lakebase audit log · HITL confirmation rate" line. It only appears once at
      least one decision has been logged.
- [ ] Open tabs ready: **AI Advisor** (start here), **Insurgent Brands**, **Distribution**.
- [ ] Backup: a screen recording or screenshots of the same three moments, in case a live call fails.
- [ ] If the agent call 404s: the supervisor was deleted. Follow the recovery steps in `DEPLOY_STATUS.md`
      (about 15 min), or present from the backup.

---

## 3. Run of show (~25 min)

| Time | Slide / screen | Mode | Aimed at |
|---|---|---|---|
| 0:00–2:00 | 1 · Outcome | **Setup** | Both: frame customer, problem, agenda |
| 2:00–5:00 | 2 · Value case | Value | Business |
| 5:00–6:00 | 3 · What you'll see | **Tell** | Both |
| 6:00–13:00 | **Live app** | **Show** | Both (narrate business, footnote technical) |
| 13:00–15:00 | 4 · Journey | **Tell** (land) → bridge | Business → Technical |
| 15:00–17:00 | 5 · Architecture | Depth | Technical |
| 17:00–19:00 | 6 · Trade-offs | Judgment | Technical (+1 line for business) |
| 19:00–20:00 | 7 · Built with AI | Force multiplier | Both |
| 20:00–22:00 | 8 · Close + ask | **Tell** + ask | Business |
| 22:00–30:00 | Q&A | Reading the room | Whoever asks |

If you're running long, cut slide 7 to one sentence and skip slide 9 entirely.

---

## 4. Opening: demo setup (slide 1)

> "Thanks both for the time. Before I show anything, let me frame why we're here.
>
> NovaLife's brand teams make share decisions every Monday. But the question *'why did NovaBaby slip at
> Walmart?'* takes an analyst two to three days to answer from the syndicated data. And insurgent brands
> like Happy Roots show up in the weekly deck two to three weeks after they started taking share.
>
> In the next twenty minutes I'll do three things: show you what solving that is worth, show you the app
> answering that exact question live, and then walk [architect's name] through how it's built and
> governed, so you both leave knowing whether it's worth a pilot."

**Check in (business):** "Does that match what you're seeing, or is there a sharper version of the
problem?" *Reuse their words for the rest of the session.*

---

## 5. Live demo: tell → show → tell

**TELL (slide 3):** "Three moments, three KPIs: ask (time to insight), confirm (trust), act (revenue
protected). Keep one number in mind: on this data, one point of NovaBaby share at Walmart is worth about
$80M a year."

### Moment 1 — Ask (≈ 2.5 min) · KPI: time to insight

| Do | Say |
|---|---|
| AI Advisor → click **"Why did NovaBaby share drop in Infant Formula last 4 weeks at Walmart?"** | "This is the Monday question, typed the way a brand manager would ask it. No ticket, no SQL." |
| The **Confirm Routing** card appears | "Before anything runs, the app has worked out the brand, category, retailer and time window, and it proposes *how* to answer: a Topline analysis. Here's why it chose that." |

*Technical footnote, one line:* "That understanding step is a governed Unity Catalog function using
`ai_extract` and `ai_classify`. It's deterministic and auditable."

### Moment 2 — Confirm (≈ 2 min) · KPI: trust and adoption

| Do | Say |
|---|---|
| Point at the route dropdown, then click **✅ Confirm & Run** | "The human stays in control. If the route looked wrong I'd change it here. That approval and whether I overrode it are written to Lakebase. That's how we measure trust: the target is over 80% confirmed first time." |
| The answer and chart appear | "**34.0% to 33.0% in four weeks**, and the biggest driver is **distribution**, about a third of the decline. Not price, not promotion." |

**LAND:** "That's a three-day analyst turnaround in under ninety seconds, and it tells the team *what to
fix*: shelf presence at Walmart, not a price cut."

*Note:* the agent's exact wording varies between runs. Quote the numbers it shows on screen; the figures
above are what the underlying data says.

### Moment 3 — Act (≈ 2.5 min) · KPI: revenue protected

| Do | Say |
|---|---|
| **Insurgent Brands** tab | "Now the threat radar. **Happy Roots is up about 2.4 points in 52 weeks.** In today's process you'd see that in a deck weeks later." |
| **Distribution** tab (or ask "Which SKUs have below 80% ACV in the Northeast?") | "And where we're exposed: one SKU is at roughly **26% ACV in the Northeast at Walmart**. That's the gap an insurgent walks into." |
| Back to Advisor: point at the **confirmation-rate** line | "Every decision today is in that number. It comes live from Lakebase." |

**TELL (land, slide 4):** "So what you just saw: the Monday question answered in under ninety seconds, a
human approving every route, and the threat spotted while there's still time to act. That's the outcome.
[Architect], let me show you why it's trustworthy."

---

## 6. Reading the room: answer at the asker's altitude

**Rule:** answer the person who asked at *their* altitude, then give the other person a one-line bridge.

- Business question → outcome, number, risk. Bridge: "[Architect], the mechanism is X; happy to go deeper."
- Technical question → real detail (service, identity, failure mode). Bridge: "In business terms, that
  means Y."
- Signal you've gone too deep: the business stakeholder goes quiet or asks about cost. Summarize in one
  line and hand back.

### Business stakeholder: likely questions

| Question | Answer (executive altitude) |
|---|---|
| "What's this worth to us?" | "Two buckets: about $0.5M a year of analyst capacity, and about $2M a year for every tenth of a point of share defended in a $2B category. The pilot is designed to measure both on your data." |
| "How fast can we have it?" | "Six-week pilot on one category. Week one it's running in your workspace against the real feed; weeks two to six we measure the four success criteria." |
| "Will my brand managers actually use it?" | "That's exactly what the confirmation-rate metric tells us. We track it from day one, alongside sessions per week. Target is over 20." |
| "What if it gives a wrong answer to a VP?" | "Two safeguards. A human approves the route before it runs, and every answer comes from SQL on your governed tables, not from the model's memory. Overrides are logged, so we see and fix routing errors quickly." |
| "Does this replace our BI or our analysts?" | "Neither. It removes the queue for routine share questions so analysts spend time on the decisions. Tableau stays for standard reporting." |
| "What does it cost to run?" | "It's serverless and scales to zero: the warehouse, agents and Lakebase only bill when used. We'll baseline the run cost in the pilot against the capacity it frees up." *(Don't quote a number you haven't measured.)* |

### Technical stakeholder: likely questions

| Question | Answer (real detail) | Bridge to business |
|---|---|---|
| "How is identity handled?" | "The app runs as its own service principal with least-privilege UC grants: USE on the catalog and schemas, SELECT on the data, EXECUTE on the function, CAN_USE on the warehouse, CAN_QUERY on both supervisors. Lakebase uses a short-lived OAuth credential minted per connection, so no stored passwords." | "Nobody gets data they couldn't already see." |
| "How do you stop the LLM hallucinating numbers?" | "The model never invents figures. Genie generates SQL that runs on governed Delta tables, and charts are built deterministically from SQL, not LLM-generated JSON. Intake is a SQL function with `ai_extract`/`ai_classify`, so it's testable." | "Every number traces back to a table." |
| "Why not have the agent pause for human approval?" | "We tried it: an agent writing PENDING to Lakebase while the app polled. A deployed supervisor endpoint is synchronous and can't suspend mid-request, so it dead-ended. The app owns the gate in two phases: enrich, confirm, then one supervisor call carrying ROUTE=." | "Simpler means faster and fewer failures." |
| "How does real data get in?" | "Syndicated files land in a UC volume. A serverless Lakeflow pipeline uses Auto Loader to ingest only new files into five streaming tables, with data-quality expectations recorded in the event log. For the real feed we point the same pipeline at the Circana drop location." | "Weekly data refreshes automatically, with quality checks." |
| "Why Lakebase? Why not just a Delta table?" | "The decision log is small, frequent, transactional writes from the app, which is an OLTP pattern. Lakebase is Postgres, written after the response is returned so it adds no latency. It's registered in UC as `bpm_lakebase`, so the confirmation rate is plain SQL alongside the Delta data." | "We can prove adoption with data." |
| "What happens if Lakebase or an agent is down?" | "Lakebase is off the critical path: writes are best-effort and the analysis still runs. If the supervisor is down, the dashboard tabs still work, since they query Delta directly, and the Advisor reports the error." | "A partial outage doesn't stop the team." |
| "How do you monitor it?" | "OpenTelemetry metrics (request latency, enrich latency, agent-call latency per route) export to Unity Catalog tables, plus the pipeline event log for data quality." | "We'll report the pilot KPIs from real telemetry." |
| "How does this scale to more categories or BUs?" | "Add a Genie space per domain and register it as a sub-agent on the supervisor. The data pipeline and app don't change. Unity Catalog grants scope each BU." | "The next category is weeks, not a new project." |
| "Is it tested?" | "Unit tests cover the HITL flow, routing, UC functions, visualization and the Lakebase audit contract. Deploys are verified end to end against the live workspace." | |
| "Lock-in?" | "Data is open Delta and Postgres. The app is plain React and FastAPI. The Databricks-specific pieces are the governance and agent layers, which is where the value is." | |

---

## 7. Objections: Acknowledge → Clarify → Respond → Confirm

Stay calm, don't rush, and never argue. Agree with what's true, then reframe.

| Objection | Response |
|---|---|
| **"Your numbers are made up."** | *Acknowledge:* "Fair. They're estimates, and the inputs are on the slide." *Clarify:* "What's your analyst headcount on this category?" *Respond:* "Even at half, it pays back, and the pilot measures the real figure." *Confirm:* "Would measured time-to-insight be the number you'd hold us to?" |
| **"This is a demo on synthetic data."** | "Yes. The data is synthetic by design so we could build without licensing delays. The pipeline, governance and agents are exactly what runs on your feed. That's what the pilot proves in week one." |
| **"We already have Tableau dashboards."** | "And they stay. Dashboards answer the questions you knew to ask. This answers the *why* question on Monday morning that today goes into the analyst queue." |
| **"Gen AI is too risky for numbers that go to the board."** | "Agreed, which is why the model doesn't produce the numbers. SQL on governed tables does, a human approves the route, and every decision is audited." |
| **"Our data team can't take on another platform."** | "It runs on the Databricks workspace you already govern: same Unity Catalog, same identities. No new infrastructure." |
| **"Six weeks is too long" / "too fast"** | "We can scope it to one brand team and one category. The four success criteria stay fixed either way." |
| **"What if the routing is wrong?"** | "The user sees and can change the route before anything runs, and overrides are logged. The override rate *is* our routing-accuracy signal, with a target of over 90% correct." |

**If you don't know:** "I don't want to guess on that. I'll confirm and come back to you by [day]." Then
move on confidently.

---

## 8. Close and ask (slide 8)

> "Let me bring it back to NovaLife. **Outcome:** brand managers get answers in under ninety seconds.
> **Value:** about half a million a year in capacity, and about two million for every tenth of a point you
> defend. **Risk:** governed end to end, with a human approving every route.
>
> I'd propose a six-week pilot on one category, with these four success criteria agreed today. **Which
> category would you pick, and who owns the Circana feed on your side?**"

Then **stop talking**. Silence after the ask is fine.

---

## 9. Delivery reminders

- Signpost every transition: "That's the value. Now let me *show* you…" / "So what that means is…"
- After every demo moment, say the business consequence out loud. Never let a screen speak for itself.
- Use their names, and use their KPIs: share, ACV, velocity, time to insight.
- Avoid feature-tour language ("and it also has…", "let me show you another tab"). Tie every click to a moment.
- Be honest about limitations: synthetic data, estimated value, the Knowledge Assistant is still roadmap.
  Candor reads as confidence.
- If the demo breaks: "Live systems, let me switch to the recording of the same flow." Keep narrating the
  value story; don't debug on stage.

### Demo numbers cheat-sheet (from the live tables)

| Fact | Value |
|---|---|
| NovaBaby Infant Formula value share, Walmart, Total US | **34.0% → 33.0%** (prior 4 wks → last 4 wks) |
| Biggest driver of the decline | **Distribution**, about 36% of the 4-week change |
| One point of NovaBaby IF share at Walmart (synthetic) | **≈ $80M / yr** |
| Top insurgent | **Happy Roots, +2.4 ppt** value share over 52 weeks |
| Weakest SKU distribution | Little Sprouts Organic 4oz, **25.6% ACV**, Walmart Northeast |
| Data volume | 5 tables · 172,640 rows · 104 weeks |
| Platform footprint | 4 Genie spaces · 2 supervisors · 1 UC function · 1 Lakeflow pipeline · 1 Lakebase project |
