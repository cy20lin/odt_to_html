# ODT to HTML Document Layout & Anchor Design

## Decision: Use name anchor-xxx over layout-xxx for semantic clearer and perciser meaning

The name for css class name for the helper container for the internal elements to utilize for layout and positioning is chosen to start with name `anchor-` as name preifx, this naming clearly states that such element is used as the anchor for the internal element for positioning, which conveys the original intent.

While such class in future could also and may be use for layout the document. The current focus is the make the drawing & text objects and elements get their positioning fit to the right place. Hence, the decision.

Considering future compatibilty and extensibility, we reserved the name `layout-`, and such class may be defined as an alias of the corresponding `anchor-` class, and is intentently left for future decision.

## Regarding the anchor hierarchy

```
anchor-page
├── anchor-page-header
├── anchor-page-content
│   └── anchor-paragraph
│       └── anchor-char
└── anchor-page-footer

```

```html
<div class="anchor-page">
  <div class="anchor-page-content">
    <!-- paragraphs & shapes -->
  </div>
</div>
```

- anchor-page: