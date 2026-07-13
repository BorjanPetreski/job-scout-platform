# Gemini Cross-Check Prompt — Reference

Load ONLY after Borjan says yes to the post-scan offer (the offer itself is mandatory every scan, per SKILL.md).

**Why structured this way:** addressed to Gemini 3.1 Pro Extended for extended reasoning and a broad crawl (compensates for the category-tagging miss pattern, e.g. Holepunch); carries the full profile, hard filters, and scoring bands so Gemini scores on the same rubric; explicitly checks Engineering/Product/Development categories; output columns mirror the skill's shortlist table so results paste back and log to Notion without reformatting.

**Delivery:** fill in [TODAY'S DATE], deliver in one plain markdown code block (no language tag), no commentary inside the block.

```
You are cross-checking a remote job search for Borjan Petreski. Use extended reasoning and as broad a crawl as you can — don't stop at the first few results in any category, and don't limit yourself to listings explicitly tagged "Project Manager." Take your time; this is a deep, thorough pass, not a quick lookup.

CANDIDATE PROFILE
- 7+ years IT Project Manager / Delivery Manager / Scrum Master / Technical Program Manager
- Location: Skopje, North Macedonia — CET/EEST timezone (UTC+1/UTC+2)
- Employment model: B2B contractor / sole proprietor — invoices directly, no visa or local payroll needed; also open to full-time
- Core tools: Jira, Confluence, Azure DevOps, Agile/Scrum, Kanban
- Certs: PSM, PSPO, ECBA
- Domains: Travel & Leisure, Educational AI, Social Prospecting, Industrial IoT, Media/Streaming

SEARCH SCOPE
Search broadly across remote job boards and company career pages (We Work Remotely, Jobgether, Dynamite Jobs, Arc.dev, Remote Rocketship, Working Nomads, Himalayas, EuropeRemotely, Remotive, Welcome to the Jungle, Landing.jobs, JustRemote, NoDesk, Remote OK, Otta, JustJoin.it, Greenhouse, Lever, Workable, and any others you find relevant). Search for: "Project Manager," "Scrum Master," "Delivery Manager," "Agile Delivery Lead," "Technical Program Manager," "Technical Project Manager," "Technical Delivery Manager," "Digital Project Manager," "Product Delivery Manager," "IT Program Manager," "Client Delivery Manager," "Solutions Delivery Manager," "Agile Project Manager."

IMPORTANT: many companies file technical/delivery PM roles under Engineering, Product, or Development categories rather than Management categories — check those categories too, not just the ones explicitly labelled "Project Management."

HARD FILTERS — auto-disqualify any role matching:
- US-only, EU-citizenship-required, or E-Verify employer
- Any travel requirement, however minor
- Core working hours requiring availability after 17:00 CET/EEST
- Published salary below ~€3,000/month gross or ~$35,000/year
- Requires Dynamics 365, SAP, Salesforce, Workday, ServiceNow, or Oracle as a primary skill
- Any security clearance or background investigation requirement
- Pure Business Analyst roles with no PM/delivery component
- Long hours / nights / weekends stated as a baseline expectation in the JD
- Closed, expired, or 404/410 listings

SCORING: Score each surviving role 1.0–10.0 (one decimal, e.g. 8.6). Only include roles scoring 7.0 or above. Bands:
- 9.0–10.0: full delivery lifecycle, Agile/Scrum/Kanban, Jira+Confluence, worldwide/EMEA open, no travel, salary confirmed above threshold
- 8.0–8.9: senior PM/SM/delivery role, globally open, agile required, salary likely above threshold, one minor gap acceptable
- 7.0–7.9: PM/SM/Delivery role, globally open but salary unconfirmed, or a minor flag (e.g. staffing/pool model)

OUTPUT FORMAT: a markdown table with these exact columns, then 2–3 sentences per role underneath explaining the fit score and any flags:

| # | Role | Company | Platform | Fit | Salary | URL |

VERIFICATION — do this before including any role, not just a title/summary read: open the actual posting and explicitly check for (a) any work-authorization, visa-sponsorship, or "must be located in X" requirement, (b) the exact stated working hours or core-overlap hours, even if buried in a bullet list rather than the headline, and (c) any travel requirement, however minor. These are frequently NOT in the job title or first paragraph — they show up in application-form questions, benefits sections, or a single buried bullet. If you find any of these, drop the role entirely rather than including it with a caveat. Do not rely on the listing's "Remote" or "Worldwide" label alone — that label describes where the *team* sits, not always who's eligible to apply.

Verify each URL is live before including it. Today's date is [TODAY'S DATE].
```
