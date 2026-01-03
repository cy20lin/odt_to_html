Phase 2: Introduce anchor-page for correct page-anchored positioning

**Context**

We are converting ODT (`content.xml`) to HTML for a document viewer (not print-perfect layout, not FTS).  
Phase 1 (paragraph-anchor) is complete: shapes anchored to paragraphs render correctly on the first page.

Remaining issue:  
Shapes that are logically anchored to a page (i.e. their `svg:x / svg:y` are page-relative) drift when the document spans multiple pages.

**Goal of Phase 2**

Introduce a minimal and explicit *page-level anchor* so that page-anchored drawing and text objects render at correct positions regardless of document length or scrolling.

This phase focuses **only on positioning correctness**, not full layout fidelity.

---

### Core Design Decisions (Do NOT change)

1.  Use the prefix **`anchor-`**
2.  Introduce **`anchor-page`** and **`anchor-page-content`**.
3.  Do NOT implement pagination, headers, footers, or page breaking.
4.  Do NOT attempt print-accurate layout.
5.  Do NOT reflow tables or text to fit pages.

### Anchor Hierarchy (Target)

```scss
anchor-page
└── anchor-page-content
    └── anchor-paragraph
        └── anchor-char
```

-   `anchor-page-content` is the **coordinate origin** for page-anchored shapes.
    
-   All `svg:x / svg:y` page-anchored positioning must be resolved relative to `anchor-page-content`.
    

---

### Scope of Work (Phase 2 ONLY)

✅ **In scope**

-   Wrap page-level content in:
    
    ```html
    <div class="anchor-page">
      <div class="anchor-page-content">
        <!-- paragraphs, shapes -->
      </div>
    </div>
    ```
    
-   Ensure `anchor-page-content` has `position: relative`
    
-   Ensure page-anchored shapes use `position: absolute` relative to `anchor-page-content`
    
-   Maintain existing paragraph-anchor behavior unchanged
    
-   Preserve visual correctness of shapes across multiple pages
    

❌ **Out of scope**

-   Pagination logic
    
-   Page size calculation (A4, Letter, etc.)
    
-   Header / footer rendering
    
-   Overflow clipping
    
-   Layout roles or grid systems
    
-   `layout-*` classes (reserved for future)
    

---

### Important Constraints

-   Page anchor size is **not required** in this phase
    
-   Only the **origin (top-left)** must be correct
    
-   Overflow across page boundaries is acceptable
    
-   Visual semantics of shapes take priority over text flow accuracy
    

---

### Implementation Guidance

-   Treat `anchor-page-content` as the canonical reference frame for:
    
    -   `draw:frame`
        
    -   `draw:custom-shape`
        
    -   other page-anchored drawing objects
        
-   Do not bind page-anchored objects to:
    
    -   `<body>`
        
    -   viewport
        
    -   document root
        
-   Avoid introducing new CSS abstractions unless strictly required for anchoring
    

---

### Validation Criteria

The implementation is correct if:

1.  A page-anchored shape appears in the same relative position:
    
    -   on page 1
        
    -   on page 2
        
    -   after inserting large blocks of content before it
        
2.  Scrolling the document does **not** cause shape drift
    
3.  Paragraph-anchored shapes remain unaffected
    

---

### Output Expectation

-   Minimal, focused code changes
    
-   Clear separation between paragraph-anchor and page-anchor logic
    
-   No speculative features beyond Phase 2 scope
    

---

**Reminder**

This is a viewer-oriented renderer, not a layout engine.  
Correct anchoring > perfect layout.

