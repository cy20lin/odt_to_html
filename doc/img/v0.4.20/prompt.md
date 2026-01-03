# 🔧 Fix `as-char` Anchor Positioning Bug in `odt_to_html`

**Context**

- Test file: `sample.odt`
- Extracted content: `content.xml` → `sample.odt.xml`
- Conversion tool: `odt_to_html.py`
- Output HTML with bug: `sample.html`
- Issue: **“Figure 3: Options Settings Window” is rendered at the wrong vertical position** (shifted upward).

---

## Root Cause

In ODT, the problematic frame is defined as:

```xml
<draw:frame text:anchor-type="as-char" svg:y="-3.0583in" ...>
```

Semantic meaning in ODT:

- `text:anchor-type="as-char"` = **inline object anchored to text baseline**
- `svg:y` = **baseline-relative vertical offset**, NOT an absolute page offset

Current (incorrect) HTML output treats this as:

```html
<div style="position: absolute; top: -3.0583in">
```

This incorrectly converts an **inline (character-anchored)** object into an **absolutely positioned block**, causing the figure to drift.

---

## Correct Mapping Rule

**`anchor-type="as-char"` must be rendered as an inline element, not absolutely positioned.**

- Do NOT use `position: absolute`
- Do NOT map `svg:y` to `top`
- Treat the object as inline content aligned to text flow

---

## Required Fix

When `text:anchor-type == "as-char"`:

- Render the frame as an inline element (`<span>`)
- Use `display: inline-block`
- Apply vertical offset relative to baseline using `transform` (or equivalent)

---

## Expected HTML Output Pattern

```html
<span class="anchor-char drawing-frame"
      style="
        display: inline-block;
        transform: translateY(-3.0583in);
      ">
  ...
</span>
```

---

## Scope & Constraints

- Only modify the `as-char` handling logic
- Do NOT change behavior for:
  - `paragraph` anchors
  - `page` anchors
- Goal: match LibreOffice semantics so inline figures render at the correct position
