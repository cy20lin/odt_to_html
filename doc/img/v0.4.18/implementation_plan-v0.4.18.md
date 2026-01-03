# Implementation Plan - Paragraph Anchoring Refactor

Refactor odt_to_html.py to correctly handle paragraph-anchored draw objects by placing them in a relative container, separate from the paragraph text.

## User Review Required
> [!IMPORTANT]
> This change strictly affects elements with `anchor-type="paragraph"`. Other anchor types (e.g., `char`, `as-char`, `page`) will remain inside the `<p>` or processed as before. This assumes `svg:x` and `svg:y` for paragraph-anchored objects are relative to the paragraph's top-left corner (or compatible with `position: relative` on the wrapper).

## Proposed Changes

### odt_to_html.py

#### [MODIFY] odt_to_html.py
-   Refactor [_process_inline_content](odt_to_html.py#522-635) (or create a new split method) to return two collections:
    1.  `inline_parts`: HTML strings for text and inline elements.
    2.  `anchored_parts`: HTML strings for paragraph-anchored objects (specifically `anchor-type="paragraph"`).
-   Update [_process_paragraph](odt_to_html.py#496-508) to use these collections:
    -   If `anchored_parts` is empty, return `<p>{inline_parts}</p>` (standard behavior).
    -   If `anchored_parts` exists, return:
        ```html
        <div class="paragraph-anchor" style="position: relative">
          <p>{inline_parts}</p>
          {anchored_parts}
        </div>
        ```
-   Ensure that `tail` text of anchored elements is always added to `inline_parts` to preserve text flow.

## Verification Plan

### Automated Tests
-   Run [odt_to_html.py](sample_annotated_image.odt).
-   Inspect the generated HTML to verify the structure:
    -   Check for `<div class="paragraph-anchor">`.
    -   Check that the arrow (or relevant shape) is a direct child of this div and sibling to `<p>`.
    -   Check that the array has `position: absolute` and `left`/`top` set.
-   Generate a screenshot using [html_to_png.py](html_to_png.py) and visually verify the arrow position (arrow 3 pointing to the image).

### Manual Verification
-   Review [sample_annotated_image.html](sample_annotated_image.html) source code.
