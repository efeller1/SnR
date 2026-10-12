# Perception Capital: operational due diligence readiness

This is the document pack and the processes Perception Capital should have ready before an allocator's operational due diligence (ODD). It is built from *Emerging Manager ODD: What a Pension Fund Actually Asked For* (The Emerging Manager, on Alfonso Peccatiello's ~20 DD processes and Palinuro's pension-fund IMA), plus the standard items every institutional DDQ asks for.

Each item is tagged with where it comes from:

- **[Article]**: raised explicitly in the article.
- **[Standard]**: not in the article, but on every institutional DDQ (AIMA / ILPA style). You will be asked for it.

Items assume a US adviser. If Perception launches under a regulatory host or platform (as Palinuro did) or outside the US, swap in the host's or local equivalents. The article says allocators still judge a hosted manager against a firm with its own licence.

**The benchmark from the article:** an allocator sends 20 questions at once, and you answer within an hour with documents attached, sent by someone other than the CIO.

---

## 1. Tier 1: must exist before any allocation

The article says allocators send a formal list after ODD. Tier 1 (about 10–12 items) must be fixed before money moves. These are the items most likely to be on it.

| # | Item | Source | Status |
|---|---|---|---|
| 1 | **Written key-person succession plan.** One named successor who knows the strategy and can already trade the book. Single-manager shops with no credible backup "are unlikely to pass ODD." | Article | ☐ |
| 2 | **Live trade reconciliation.** Real-time check that each fill is in the right account, the right instrument, the right direction and the right size. Next-day Excel reconciliation against the broker report is a red flag. | Article | ☐ |
| 3 | **Fat-finger controls on two independent lines.** Line 1: hard limits in your OMS. Line 2: limits at the broker that stop an order even if the OMS let it through. Sanctioned countries and restricted names blocked at the broker. | Article | ☐ |
| 4 | **Errors and omissions (E&O) insurance**, sized to the largest error the strategy can make. The article cites allocator minimums of $5m, $7.5m or $10m per year. | Article | ☐ |
| 5 | **Cyber insurance** (usually a separate policy from E&O). | Article | ☐ |
| 6 | **Cybersecurity baseline:** 2FA on everything used to trade, a partitioned (work-only) phone and computer, an annual penetration test and regular phishing tests. | Article | ☐ |
| 7 | **Background checks on every employee**, covering criminal records and outside business interests, with the reports ready to share. | Article | ☐ |
| 8 | **Pre-cleared references.** Nominated in advance, permission obtained, contact details on file. | Article | ☐ |
| 9 | **Independent service providers** (administrator, auditor, legal counsel, prime broker / custodian). See §3. | Standard | ☐ |
| 10 | **Compliance manual and code of ethics** with a named CCO. See §2. | Standard | ☐ |
| 11 | **Valuation policy** with independent pricing by the administrator. | Standard | ☐ |
| 12 | **Policies that agree with each other.** The article stresses this: the DDQ, compliance manual, BCP and offering documents must describe the same process. | Article | ☐ |

---

## 2. The document pack

Keep these in one data room folder, current, dated and versioned, so any request can be answered by attaching a file.

### Firm and people

| Document | Source | Notes |
|---|---|---|
| Firm overview / org chart | Standard | Ownership, roles, who does what, reporting lines. |
| Bios of principals and staff | Standard | Include the named successor. |
| **Key-person succession plan** | Article | Who takes over, what they can do today, how investors are told. |
| **Background check reports** (all staff) | Article | Criminal records and outside business interests. |
| **Reference list** (pre-cleared) | Article | Former employers or colleagues, a service provider, an early investor or research client. |
| Outside business activities disclosure | Standard | Required anyway by the code of ethics. |

### Strategy and investment process

| Document | Source | Notes |
|---|---|---|
| **Investment process write-up: idea generation and replicability** | Article | Allocators probe where ideas come from and whether the process repeats. Perception's systematic screen (point-in-time fundamentals, attention residuals, factor-residual momentum, documented in this repo's `README.md` and `snr/config.py`) is the evidence. Show the rule-based steps that produce candidates and the discretionary review that follows. |
| Track record and its limits | Article | Present returns with the number of independent bets behind them. The article's point: ~150 trades over three years is statistically thin. The process is the evidence, not the record. |
| Backtest methodology and known biases | Standard | The README's survivorship, attention-history and sector-mapping caveats. Disclosing these up front reads as honesty, which the article lists as a controllable. |
| Risk management framework | Article / Standard | Position limits, gross and net exposure, stop-losses, liquidity (% of ADV), correlation and stress tests, and how often they run. The article says allocators did not grill this, but be ready to demo it at any time. |
| Sample investor letter and reporting pack | Article | Regular letters, transparent reporting, bad news not hidden. |

### Regulatory and compliance

| Document | Source | Notes |
|---|---|---|
| Form ADV Parts 1, 2A and 2B (or exempt reporting adviser filing) | Standard | Depends on AUM and structure. Under a host, provide the host's registration and your appointment. |
| Compliance manual | Standard | Including the annual compliance review. |
| Code of ethics | Standard | Personal trading pre-clearance, holdings reports, gifts and entertainment, outside activities. |
| Insider trading / MNPI policy | Standard | Especially relevant for small-cap, under-followed names: cover expert networks, management meetings and channel checks. |
| Trade allocation and aggregation policy | Standard | Needed once there is more than one account (fund plus SMA). |
| Best execution policy and broker review | Standard | |
| Trade error policy | Standard | Who pays, how errors are logged and reported. Pairs with the E&O cover. |
| AML / KYC policy | Standard | Usually delegated to the administrator; document the delegation. |
| Marketing / advertising rule compliance | Standard | Performance presentation, hypothetical (backtest) performance disclosures. |
| Regulatory exam and litigation history | Standard | "None" is still an answer to have in writing. |

### Operations and technology

| Document | Source | Notes |
|---|---|---|
| **Trade lifecycle and reconciliation process** | Article | Order → OMS checks → broker checks → fill → live recon → admin recon. Include break escalation. |
| **Pre-trade control limits** | Article | The OMS limits and the broker limits, as two separate lists. |
| **Cybersecurity policy** | Article | 2FA, device partitioning, access control, patching, vendor review. |
| **Penetration test report** (latest) | Article | |
| **Phishing test results** | Article | |
| Business continuity / disaster recovery plan, with a test record | Standard | Should name the same successor as the succession plan. |
| Systems inventory | Standard | OMS, data vendors, storage, backups. |
| Valuation policy | Standard | |
| Liquidity management policy | Standard | |

### Insurance

| Policy | Source | Notes |
|---|---|---|
| **E&O / professional liability** | Article | $5m–$10m per year per the article. Ask each allocator for its minimum. |
| **Cyber** | Article | |
| D&O / management liability | Standard | Often bundled with E&O for funds. |
| Fidelity / crime bond | Standard | |

### Fund and legal documents

| Document | Source | Notes |
|---|---|---|
| PPM / offering memorandum, LPA, subscription documents | Standard | |
| **Founder share class terms** | Article | Follow-on allocators asked for these as soon as the first ticket landed. |
| Template IMA for a managed account (SMA) | Article | The article says large allocations typically come through an SMA, not the fund. |
| Service provider agreements | Standard | Administrator, prime broker or custodian, auditor. |
| Clearing agreement / ISDAs | Article | Part of the article's $40–50m "properly structured" launch floor. ISDAs only if you trade OTC derivatives. |
| Audited financial statements (fund and management company) | Standard | First audit once the fund has a full year. |

### Due diligence questionnaire

| Document | Source | Notes |
|---|---|---|
| Completed AIMA-style DDQ | Standard | Fill it in once. Most allocator questionnaires map onto it. Keep it consistent with every policy above. |

---

## 3. Service providers to line up

| Provider | Source | Why |
|---|---|---|
| Fund administrator | Standard | Independent NAV, investor services, AML. Also the independent half of reconciliation. |
| Auditor | Standard | Allocators look for a recognised fund auditor. |
| Prime broker / custodian | Article / Standard | Must support broker-side pre-trade limits and sanctioned-name blocks (Line 2). |
| Fund and regulatory counsel | Standard | Offering documents, IMA templates, side letters. |
| Outsourced compliance / CCO support | Standard | Common for small managers. |
| Insurance broker | Article | E&O, cyber, D&O and crime, placed together. |
| Background check firm | Article | |
| Penetration test / cybersecurity vendor | Article | Also runs the phishing tests. |
| OMS / reconciliation tooling | Article | Must support hard limits and live fill checks. |

---

## 4. Processes to put in place

### Trade operations (article action item 1)

The test from the article: **how quickly would you know a trade went into the wrong account, in the wrong direction?** The target is minutes (live), not "by close of business the following day."

- Reconcile each fill against the intended order automatically during the day (account, ticker, side, quantity, price), with an alert on any break.
- Run the end-of-day three-way reconciliation: internal book vs. broker vs. administrator.
- Log every break with its cause and resolution. Allocators will ask to see the log.

### Fat-finger controls (two independent lines)

The article's example uses futures lot limits. For an equity book the equivalents are:

- **Line 1 (OMS):** maximum shares and notional per order, maximum % of average daily volume per order and per day, maximum position size as a % of NAV, a price collar against the last trade, and a restricted list.
- **Line 2 (broker):** the same order-size and notional caps agreed with the broker and coded on their side, plus hard blocks on sanctioned countries and names so orders can't be placed or cleared.
- Write both lists down and confirm them with the broker in writing.

### Key person (article action item 2)

- Name one successor. They must understand the screen and the discretionary overlay, and be able to trade the book today.
- Give them working access (OMS, broker, data) now, not only on paper.
- Write down when the plan triggers, who tells investors and within what time, and what happens to positions in the meantime.

### Diligence response (article action item 3)

- Keep the data room current and review it quarterly. Re-date documents when they change.
- Make one person other than the CIO responsible for answering requests. The article says a dedicated ops person "makes a strong impression."
- Run a mock test: take a 20-question DDQ section and time how long it takes to answer with attachments. Target: under an hour.
- After every ODD, keep the allocator's findings list and track Tier 1 and Tier 2 items to closure.

### Ongoing

- Annual: penetration test, compliance review, BCP test, insurance renewal and limit check, background checks for new hires.
- Regular: phishing tests, staff compliance attestations, personal trading reports.
- Investor communication: a regular letter, transparent reporting and early explanation of drawdowns. The article lists these among the few things a manager controls.

---

## 5. Tier 2: build toward these over time

From the article: allocators will fund before these are done, provided there is a plan and they are consulted.

- Moving from a regulatory host to your own registration, with everything it requires.
- Dedicated operations hire (the article's Palinuro hired ops and BD/CRM people at six staff).
- Formal independent risk function.
- Upgrading tooling as AUM grows (OMS, recon, CRM).

---

## 6. What the article says not to spend on

- **Prestige office:** not required. Nobody cared about a Mayfair address.
- **On-site visit prep:** optional. Many allocators never visit.
- Put the money into reconciliation, controls, insurance and an ops person instead.

---

## 7. Context to keep in mind

- **Launch economics:** the article puts the floor for a properly structured fund at $40–50m AUM, with at least two years to profitability. Allocators expect the infrastructure spend *before* ODD, with no guarantee of a ticket.
- **First ticket is a signal:** once one credible allocator completes ODD, others treat it as done and move faster. Have founder share class terms ready.
- **ODD is half the decision:** investment due diligence (about 10–12 interviews) and ODD carry roughly equal weight.
- **Terms:** early large investors typically get favourable fees and fixed capacity for two to three years. They underwrite the business, not just the strategy.
