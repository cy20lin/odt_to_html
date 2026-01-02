# Fix ODT Text Box Conversion

## Goal Description
Fix the issue where text boxes in ODT files are converted to HTML without their borders and positioning styles. Specifically, `draw:frame` elements (which can be text boxes) are not extracting their associated graphic properties (border, fill, stroke style).

## User Review Required
None. This is a bug fix.

## Proposed Changes

### [odt_to_html.py](file:///c:/Users/cylin/Repo/_playground/any_to_html/odt_to_html.py)

#### [MODIFY] [odt_to_html.py](file:///c:/Users/cylin/Repo/_playground/any_to_html/odt_to_html.py)
*   **Update [_extract_graphic_properties](file:///c:/Users/cylin/Repo/_playground/any_to_html/odt_to_html.py#356-384)**:
    *   Map `draw:stroke="dash"` to `border-style: dashed;` and `stroke-dasharray` (for SVG).
    *   Map `draw:stroke="solid"` (or imply it) to `border-style: solid;`.
    *   Ensure `border-width` is treated correctly.
*   **Update [_process_frame](file:///c:/Users/cylin/Repo/_playground/any_to_html/odt_to_html.py#550-657)**:
    *   Extract `draw:style-name`.
    *   Retrieve the style properties using `self.styles.get()`.
    *   Apply these properties (specifically `border`, `border-color`, `border-width`, `border-style`, `background-color`, `padding`) to the frame's `style_parts`.
    *   Add `box-sizing: border-box` to ensure padding/borders don't mess up dimensions if needed, or handle explicitly.

## Verification Plan

### Automated Tests
1.  **Run conversion**: `python .\odt_to_html.py .\sample_test_drawing.odt sample_test_drawing.html`
2.  **Verify Output**:
    *   Check [sample_test_drawing.html](file:///c:/Users/cylin/Repo/_playground/any_to_html/sample_test_drawing.html) content.
    *   Look for the `div` corresponding to "Text box with Bold Text".
    *   Assert it has `border-style: dashed`, `border-color` (should be blueish), and `position: absolute` (or handled via frame positioning).
3.  **Visual Check**:
    *   Generate PNG: `python .\html_to_png.py .\sample_test_drawing.html sample_test_drawing.html.png`
    *   Compare [sample_test_drawing.html.png](file:///c:/Users/cylin/Repo/_playground/any_to_html/sample_test_drawing.html.png) with specific requirements (blue dashed box).

### Manual Verification
*   Inspect the generated HTML code for the presence of `border` styles on the `div` wrapping the text box.
