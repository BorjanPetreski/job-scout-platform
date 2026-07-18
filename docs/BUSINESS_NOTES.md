# Business Notes — monetization, GTM & valuation (living)

> **Captured early (2026-07-18), used later.** These are directional strategy notes, not a
> formal valuation. They feed the **GTM / marketing & sales-prep phase** that follows the build
> (see PROJECT_PLAN roadmap). Refresh as real numbers (MRR, retention, COGS) arrive — every figure
> here hinges on traction we don't have yet.

## The one governing truth

**Valuation ≈ f(revenue, retention, growth, defensibility) — not code quality.** A buyer pays for
a cash-flowing asset, not for how well-built it is. So "how much can we get" is set by traction,
not by finishing the build. A finished, unused product is an *idea + code sale*, not a business.

## Product SWOT (honest)

**Strengths**
- Positioning: honest, quality-first, non-spammy, **user-owns-their-data** — the opposite of the
  auto-apply spam bots (LazyApply, Sonara, LoopCV, Jobright…). Sells well to privacy-conscious
  users and, more so, to institutions.
- **The one real moat: the compounding voice + knowledge base.** Longer use → more valuable
  personal asset → higher switching cost. Most job tools have zero retention hook; this has one.
- The **companion (not apply-bot) vision extends LTV** past a single job hunt (CV doctor, writing
  coach, always-on career companion) — fighting the #1 killer of job-search economics (users leave
  the moment they're hired).

**Headwinds (these cap every number)**
- It's a **Claude wrapper** — low inherent defensibility; moat must come from brand + the
  data-compounding above + execution.
- **Ongoing COGS** — scanning judgment, voice-building, drafting all burn tokens per user forever;
  squeezes margin → squeezes multiple. **Watch COGS-per-user like a hawk.**
- **Scraping fragility** — boards change/block (why health monitoring exists); to an acquirer
  that's a maintenance treadmill + a ToS/legal diligence flag. Anything LinkedIn-adjacent is a red flag.
- **Job-seekers are the worst SaaS segment** — brutal churn (success = cancellation), low WTP
  ($10–30/mo), high CAC, seasonal.
- Today: **pre-revenue, single-user dogfood** — no retention data, which is what every number needs.

## Go-to-market paths, ranked

1. **White-label / B2B — best risk-adjusted value.** License the engine to career-services firms,
   outplacement providers (RiseSmart/LHH world), bootcamps, universities, recruiting/coaching
   agencies who rebrand it. Higher WTP, annual contracts, far lower churn, fewer customers to
   support; the honest/GDPR/data-ownership story sells better to institutions than consumers. A few
   $1–5k/mo contracts beat thousands of churny consumers — and are more sellable. **Keep
   white-label ownership + run your own brand = fine (just "do both" once the engine is productized).**
2. **Direct consumer SaaS (web-first; mobile/desktop are channels).** Viable but a grind (churn,
   CAC, COGS, crowded). Web-first is right; native apps add build/maintenance + 15–30% store fees.
   Use this as the **wedge to prove retention**, not the end state.
3. **Flip on Acquire.com / Flippa — only *after* traction.** Profit-multiple marketplaces; flipping
   pre-revenue leaves ~everything on the table, and buyers stack discounts for wrapper + scraping +
   founder-dependency + churny market. It's an exit *option* you unlock with numbers.

## Valuation ranges (directional, not a formal valuation)

| Stage | What it looks like | Realistic value |
|---|---|---|
| **Today** (pre-revenue, dogfood) | code + IP + working demo, no users | **~$0–10k** — not worth flipping. |
| **Wedge traction** | ~$2–8k MRR (~$25–100k ARR), moderate churn, COGS in check | **~$50k–300k** (2–4x ARR / 3–4x SDE); **churn drags to the low end** ($50k far likelier than $300k). |
| **Real business** | $50k–150k+ MRR, low churn (usually via B2B/white-label) | **~$1M–5M+**, more likely a *strategic* acquisition than a marketplace flip. Multi-year. |

**The variable that moves you between rows is retention/churn — not features.** Won on the
B2B/white-label side and via the career-long-companion LTV extension, not consumer volume.

## Recommendation

- **Don't optimize for the exit before there are users.** Highest-value near-term move: get a small
  cohort of *real* users (beyond Borjan/Ani) through the companion and measure retention + WTP.
- **Primary thesis to test = the B2B/white-label wedge.** Consumer SaaS is the demo/wedge, not the
  destination.
- **"Flip it" is an option you earn**, not a strategy. The build is the price of entry; retention
  is the valuation.

## Parked monetization ideas (revisit at the GTM phase)

- **In-product ads (web-platform route).** If we go web-platform/free-tier, an ad surface may be a
  revenue lever for free users — **later-phase decision** (weigh against the premium/privacy
  positioning; ads can undercut the "we don't mine you" story, so tread carefully). Belongs in the
  free-vs-paid tier design.
- **Career-long companion as the retention/LTV play** — lean into it deliberately; it's the moat.
- **Watch COGS-per-user** as a first-class metric from the first paying user — it's what turns
  "nice product" into "positive-margin business," the whole ballgame for any sale.
- **BYO-key / AI-provider-agnostic (Borjan, 2026-07-18).** Let users bring their own LLM API key so
  *their* usage is on *their* bill — you charge for the software/orchestration, not tokens. The
  strongest lever against the COGS-caps-valuation problem. Caveats: it does **not** add
  defensibility (a model-agnostic wrapper is *less* defensible); quality is tuned to Claude and the
  companion lives on Claude-native rails, so keep **Claude the tuned default** and treat other
  providers as an option, not parity. Implement via the provider-adapter seam (ARCHITECTURE §7b);
  tier it (hosted-Claude = managed COGS; BYO-key = pro tier). Design the seam early, build later.
