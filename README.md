# bytronix-leads

Finds Illinois companies with a fresh, public reason to spend on software, for Bytronix Labs'
private-sector outreach. Companion to the bid scanner and the forecaster, whose weekday brief
hands out one YES lead a day.

| Source | Signal | Contact |
|---|---|---|
| SEC Form D | Raised money in the last 60 days. Health, financial, insurance and technology companies; funds, property and holding vehicles are left out. | Named officer and company phone from the filing |
| FDIC and NCUA | Illinois community banks and credit unions with $50M-$3B in assets: regulated, security-heavy, usually without big tech teams | A general address from their own site |
| NIH RePORTER | Holds an NIH small-business (SBIR/STTR) grant | Principal investigator |

Claude checks each lead (YES / MAYBE / NO), picks one of the three starting offers and writes an
opening line. A record gives a reason to write, not proof of need: check the company's site first.
The tool never sends anything and doesn't find email addresses.

SBIR.gov's API answers 403, so it isn't used. LinkedIn and review sites aren't scraped.

## Daily private drafts

`python leads.py --keep-drafts 5` keeps five private emails waiting in Gmail Drafts. It writes only to good-fit leads whose own site
publishes a general address (robots.txt respected, nothing guessed), skips companies already contacted, and never sends. A timer
runs it weekdays at 7:30 Central.

## Draft an email

Once you've found an address: `python leads.py --draft "Renalis" --to name@company.example` saves an email to
Gmail Drafts and adds it to the outreach tracker. It never sends.

## Run

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
python -m tests.test_offline
python leads.py --open
```

Reports land in `reports/`; everything seen is stored in `leads.db`. `deploy/systemd/` has a timer for
Mondays at 7:15 Central. Up to `ai_per_run` leads are checked per run, and results are cached.

Cold email to US businesses falls under CAN-SPAM: include the postal address and a way to opt out.
