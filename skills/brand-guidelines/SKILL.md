---
created: '2026-05-31'
description: Applies Anthropic's official brand colors and typography to any sort
  of artifact that may benefit from having Anthropic's look-and-feel. Use it when
  brand colors or style guidelines, visual formatting, or company design standards
  apply.
judge_score: null
name: brand-guidelines
origin: forge-996cce1c:brand-guidelines:1
signature: 2KSe4Nbg7XjlApslH8iLTi0qPQ22002PVJHaOlnBB/Xtp9wCmNPqdILlmO+NdU+WlW/Q9PJZMbP4mFsd0Fo2Cg==
sources:
- id: src-1120b3
  url: https://github.com/anthropics/skills/blob/main/skills/brand-guidelines/SKILL.md
tags:
- design
version: 1
visibility: private
---

# Anthropic Brand Styling

## Overview

Applies Anthropic's official brand colors and typography to visual artifacts. The rules below cover the two common targets explicitly — PowerPoint decks (via python-pptx) and HTML/CSS — and the palette/typography facts transfer to any other medium. There is no bundled script: you write the styling code yourself with the Write tool using the rules in Procedure, then run it with Bash.

**Keywords**: branding, corporate identity, visual identity, post-processing, styling, brand colors, typography, Anthropic brand, visual formatting, visual design

## Brand Guidelines

### Colors

**Main Colors:**

- Dark: `#141413` - Primary text and dark backgrounds
- Light: `#faf9f5` - Light backgrounds and text on dark
- Mid Gray: `#b0aea5` - Secondary elements
- Light Gray: `#e8e6dc` - Subtle backgrounds

**Accent Colors:**

- Orange: `#d97757` - Primary accent
- Blue: `#6a9bcc` - Secondary accent
- Green: `#788c5d` - Tertiary accent

### Typography

- **Headings**: Poppins (fallback: Arial)
- **Body Text**: Lora (fallback: Georgia)

## Procedure

Each step names the tool that performs it.

1. **Check font availability (Bash).** Run `fc-list | grep -iE "poppins|lora"`. If either font is missing, use the fallback (Arial for headings, Georgia for body) — set the fallback name explicitly rather than relying on renderer substitution. Do not attempt to install fonts.
2. **Write the styling code (Write tool).** For a .pptx, write a Python script using python-pptx's `RGBColor` and run it with Bash (`python style_deck.py deck.pptx`). For HTML, write CSS custom properties into the stylesheet (see Example).
3. **Apply these rules in the code you write:**
   - **Text color by background** (the full selection rule): on light backgrounds (`#faf9f5`, `#e8e6dc`) use dark text `#141413`; on the dark background `#141413` use light text `#faf9f5`.
   - **Fonts**: headings — 24pt and larger in pptx, `h1`–`h3` in HTML — get Poppins; all other text gets Lora.
   - **Non-text shapes**: assign accent fills in fixed order orange → blue → green, repeating (accent index = shape index mod 3).
4. **Verify (Bash + Read).** Re-open or render the artifact and confirm the fonts and hex values were applied.

## Example

python-pptx — brand an existing deck:

```python
from pptx.util import Pt
from pptx.dml.color import RGBColor

ACCENTS = [RGBColor(0xD9, 0x77, 0x57), RGBColor(0x6A, 0x9B, 0xCC), RGBColor(0x78, 0x8C, 0x5D)]

for slide in prs.slides:
    accent_i = 0
    for shape in slide.shapes:
        if shape.has_text_frame:
            for para in shape.text_frame.paragraphs:
                for run in para.runs:
                    is_heading = run.font.size is not None and run.font.size >= Pt(24)
                    run.font.name = "Poppins" if is_heading else "Lora"
                    run.font.color.rgb = RGBColor(0x14, 0x14, 0x13)  # dark on light slide
        elif shape.shape_type is not None and hasattr(shape, "fill"):
            shape.fill.solid()
            shape.fill.fore_color.rgb = ACCENTS[accent_i % 3]
            accent_i += 1
```

Equivalent CSS custom properties for an HTML artifact:

```css
:root {
  --brand-dark: #141413; --brand-light: #faf9f5;
  --accent-orange: #d97757; --accent-blue: #6a9bcc; --accent-green: #788c5d;
}
h1, h2, h3 { font-family: "Poppins", Arial, sans-serif; }
body { font-family: "Lora", Georgia, serif; color: var(--brand-dark); background: var(--brand-light); }
```

## Failure modes

- **Brand fonts unavailable**: python-pptx writes the font name whether or not the font exists, and the viewer silently substitutes. If step 1's `fc-list` check shows Poppins/Lora missing, write `Arial`/`Georgia` explicitly so the fallback is deliberate and consistent across systems.
- **Low-contrast gray-on-gray**: `#b0aea5` on `#e8e6dc` fails contrast; use the grays for secondary shapes and backgrounds only, never for body text.

## Source

- https://github.com/anthropics/skills/blob/main/skills/brand-guidelines/SKILL.md
