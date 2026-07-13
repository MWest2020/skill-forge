---
created: '2026-05-31'
description: A set of resources to help me write all kinds of internal communications,
  using the formats that my company likes to use. Claude should use this skill whenever
  asked to write some sort of internal communications (status reports, leadership
  updates, 3P updates, company newsletters, FAQs, incident reports, project updates,
  etc.).
judge_score: null
name: internal-comms
origin: forge-996cce1c:internal-comms:1
signature: NRwZCljR24Q3Mkui/Or/WB5j2yzYeuoBDqCzxfjiVaJjWL97l860ee5xnvZq0mWLQTzTuoxIOhhNJ8oYaYV4BA==
sources:
- id: src-067b75
  url: https://github.com/anthropics/skills/blob/main/skills/internal-comms/SKILL.md
tags: []
version: 1
visibility: private
---

## When to use this skill
To write internal communications, use this skill for:
- 3P updates (Progress, Plans, Problems)
- Company newsletters
- FAQ responses
- Status reports
- Leadership updates
- Project updates
- Incident reports

## How to use this skill

To write any internal communication:

1. **Identify the communication type** from the request
2. **Load the appropriate guideline file** from the `examples/` directory:
    - `examples/3p-updates.md` - For Progress/Plans/Problems team updates
    - `examples/company-newsletter.md` - For company-wide newsletters
    - `examples/faq-answers.md` - For answering frequently asked questions
    - `examples/general-comms.md` - For anything else that doesn't explicitly match one of the above
3. **Follow the specific instructions** in that file for formatting, tone, and content gathering

If the communication type doesn't match any existing guideline, ask for clarification or more context about the desired format.

## Keywords
3P updates, company newsletter, company comms, weekly update, faqs, common questions, updates, internal comms

## Source

- https://github.com/anthropics/skills/blob/main/skills/internal-comms/SKILL.md
