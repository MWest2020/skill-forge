---
created: '2026-05-31'
description: Use this skill when creating, choosing, or contributing `.gitignore`
  files for a repository, especially when working with GitHub's collection of `.gitignore`
  templates or deciding where a new template belongs (root, `Global`, or `community`).
  It explains the folder conventions, what makes a curated template, how versioned
  and specialized templates are handled, and the contribution workflow.
judge_score: null
name: gitignore-templates
origin: forge-996cce1c:gitignore-templates:1
signature: q46d339+/+n6n/SEbuHxDAf+EeP4RCfRWubsOJ3NlAjaRbDypmRI7Ma2Pys8VIXZHwttZ9mHlWpZqVaN1z8vCw==
sources:
- id: src-5fb675
  url: https://raw.githubusercontent.com/github/gitignore/main/README.md
tags: []
version: 1
visibility: private
---

## When to use

Reach for this skill when you need to:

- Pick or assemble a `.gitignore` for a project in a given language, framework, or tool.
- Decide whether editor/OS/tool ignore rules belong in the project file or in a personal global ignore.
- Contribute a new template to GitHub's `gitignore` collection, or judge whether a proposed template is a good fit.
- Understand why a template lives at the root vs. under `Global` or `community`.

## Procedure

1. **Understand what `.gitignore` does first.** It tells Git which untracked files to ignore so they are never committed. See the canonical references: the Pro Git "Ignoring Files" chapter, GitHub Help's ignoring-files article, and the `gitignore(5)` manual page.

2. **Locate the right template by folder convention.** The collection is organized into three tiers:
   - **Root folder** — templates in common use for popular languages/technologies. The root file is always the *current, "evergreen" version* with no version number in the filename.
   - **`Global/`** — templates for editors, tools, and operating systems (e.g. editor swap files, OS metadata). Don't paste these into a project file; instead add them to your *global* ignore via Git's `core.excludesFile`, or merge them into the project file only if the project permanently needs them.
   - **`community/`** — specialized templates for less mainstream languages/tools, and *previous versions* of root templates. Add these to your project-specific file when you adopt that framework or tool.

3. **Compose your project file.** Start from the relevant root template, then merge in `community/` rules for specific frameworks you use. Keep OS/editor noise in your personal global ignore rather than the committed file.

4. **When contributing a new template:**
   - Read and follow the repo's `CONTRIBUTING.md` (Contributing Guidelines) — this is the first requirement.
   - Keep it a *small, curated set of rules* specific to one language/framework/tool/environment. If you can't curate a meaningful small set, it's not a good fit.
   - If the template is mostly a list of files installed by a particular software version, it belongs under `community/` as a versioned template, not the root.
   - For specialized/niche templates, place them under `community/<sensible-folder>/`. Add a header comment naming the framework, its website, and any companion templates to combine (e.g. `# Recommended: VisualStudio.gitignore`).
   - Use a header comment line like `# gitignore template for <Name>` and group rules with comments (ignore rules, plus `!`-prefixed force-include rules where needed).

5. **Versioning rule.** The supported current version lives at the root with no version in the filename; older versions move to `community/` *with the version embedded in the filename* so maintainers can support repos still in the wild.

6. **Submit via the standard flow:** fork the project, create a branch, make changes, and send a pull request from your branch to the upstream `main` branch. The web-based editor works too and auto-forks/prompts a PR. Include details in the PR when the template is important and visible — promotion to root may happen later based on interest.

## Failure modes

- **Dumping `Global` editor/OS rules into the committed project file.** Prefer the personal global ignore (`core.excludesFile`) so teammates aren't forced to adopt your editor's noise.
- **Putting a versioned, install-manifest-style template at the root.** Those belong in `community/` with the version in the filename; the root must stay evergreen.
- **Submitting a sprawling, unfocused template.** The collection curates *the most common and helpful* rules, not every possible tool. A template that can't be reduced to a small useful rule set will be rejected.
- **Expecting every language/tool to be accepted.** Non-inclusion is a curation choice, not a quality judgment — niche items go to `community/`.
- **Omitting the header comment / companion-template note on a specialized template**, leaving users unsure what framework it targets or what to combine it with.
- **Skipping `CONTRIBUTING.md`.** Adherence to the Contributing Guidelines is mandatory; a PR that ignores them won't be merged.

## Source

- [A collection of `.gitignore` templates (github/gitignore README)](https://raw.githubusercontent.com/github/gitignore/main/README.md)
- [gitignore(5) manual page](https://git-scm.com/docs/gitignore)
- [Pro Git — Ignoring Files](https://git-scm.com/book/en/v2/Git-Basics-Recording-Changes-to-the-Repository#_ignoring)
- [GitHub Docs — Ignoring files](https://docs.github.com/en/get-started/getting-started-with-git/ignoring-files)
