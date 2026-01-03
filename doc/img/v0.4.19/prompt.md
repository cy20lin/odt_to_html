Phase 2: Introduce explicit page anchoring for ODT-to-HTML conversion.

Context:
Paragraph anchoring (Phase 1) is complete.
Paragraph-anchored draw objects now render correctly on the first page,
but drift on subsequent pages due to missing page-level coordinate context.

Current problem:
The HTML output relies on <body> and natural flow for pagination,
but ODT draw coordinates (svg:x / svg:y) are defined relative to the page content box,
not the document body or scroll position.

Do NOT:
- Do not remove or redesign the paragraph-anchor implementation
- Do not fix this by adjusting top offsets heuristically
- Do not rely on browser pagination or scroll position
- Do not introduce CSS columns or JS-based layout

Phase 2 goals:
- Explicitly model ODT pages as containers
- Introduce a <div class="odt-page"> as the page coordinate system
- Each odt-page must have position: relative and fixed dimensions
  matching the ODT page size (e.g. A4: 8.27in x 11.69in minus margins)

Required behavior:
- All paragraph-anchor containers must be placed inside an odt-page
- Paragraph-anchored draw objects remain relative to their paragraph-anchor
- Page-relative positioning (svg:x/svg:y) must be resolved against the odt-page,
  not against <body> or viewport

Implementation guidance:
- Derive page size and margins from ODT styles (or start with defaults)
- Accumulate paragraph vertical offsets to determine when content
  overflows to a new page
- When overflow occurs, start a new odt-page container
- Maintain a running "page origin offset" for each page

Outcome:
Draw objects and annotations render correctly on all pages,
with stable positions regardless of scroll or document length.


# Phase 2: Introduce anchor-page for correct page-anchored positioning

## Context

We are working on writing a script ./odt_to_html.py converting ODT (content.xml) to HTML .
Phase 1 (paragraph-anchor) is complete: shapes anchored to paragraphs render correctly on the first page.

Remaining issue:
Shapes that are logically anchored to a page (i.e. their svg:x / svg:y are page-relative) drift when the document spans multiple pages.

## Goal of Phase 2

Introduce a minimal and explicit page-level anchor so that page-anchored drawing and text objects render at correct positions regardless of document length or scrolling.

This phase focuses only on positioning correctness, not full layout fidelity.

## Goal of Phase 2

Introduce a minimal and explicit page-level anchor so that page-anchored drawing and text objects render at correct positions regardless of document length or scrolling.

This phase focuses only on positioning correctness, not full layout fidelity.

## Anchor Hierarchy (Target)


```
anchor-page 
└── anchor-page-content 
    └── anchor-paragraph 
        └── anchor-char
```

- `anchor-page-content` is the **coordinate origin** for page-anchored shapes.
- All `svg:x / svg:y` page-anchored positioning must be resolved relative to `anchor-page-content`.

## Scope of Work (Phase 2 ONLY)

✅ In scope

Wrap page-level content in:

```html
<div class="anchor-page">
  <div class="anchor-page-content">
    <!-- paragraphs, shapes -->
  </div>
</div>
```

- Ensure anchor-page-content has position: relative
- Ensure page-anchored shapes use position: absolute relative to anchor-page-content
- Maintain existing paragraph-anchor behavior unchanged
- Preserve visual correctness of shapes across multiple pages

## Implementation Guidance

- Treat anchor-page-content as the canonical reference frame for:
  - draw:frame
  - draw:custom-shape
  - other page-anchored drawing objects
- Do not bind page-anchored objects to:
  - <body>
  - viewport
  - document root
- Avoid introducing new CSS abstractions unless strictly required for anchoring

## Output Expectation

- Minimal, focused code changes
- Clear separation between paragraph-anchor and page-anchor logic
- No speculative features beyond Phase 2 scope

## Reminder

This is a viewer-oriented renderer, not a layout engine.
Correct anchoring > perfect layout.