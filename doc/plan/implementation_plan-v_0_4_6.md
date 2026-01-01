# Implementation Plan - Fix Round Rectangle Corners (v0.4.5-v0.4.6)

The goal is to fix the "Round Rectangle" shape rendering. Currently, it renders with straight chamfered corners because the ODT `X` and `Y` path commands are mapped to simple `LineTo` (`L`) commands in SVG. We will change this to map them to `Arc` (`A`) commands.

## User Review Required
> [!NOTE]
> This interpretation assumes `X` and `Y` in ODT enhanced paths `round-rectangle` shape represent quarter-ellipse arcs (corners). This is inferred from the shape name and typical vector geometry construction, as explicit documentation for these specific commands is scarce.

## Proposed Changes

### `odt_to_html.py`

#### [MODIFY] [odt_to_html.py](file:///c:/Users/cylin/Repo/_playground/any_to_html/odt_to_html.py)

1.  **Update `_convert_path`**:
    -   Add state tracking for `current_x` and `current_y` as the path is parsed.
    -   Update `M`, `L`, `C` handlers to update `current_x` and `current_y`.
        -   `M x y` -> `current_x=x`, `current_y=y`
        -   `L x y` -> `current_x=x`, `current_y=y`
        -   `C x1 y1 x2 y2 x y` -> `current_x=x`, `current_y=y`
        -   `Z` -> need to track start point of subpath? (Usually not strictly needed for just `current` tracking if `M` follows, but good for correctness. Subpath start tracking logic already exists partially.)
    -   **Change `X` and `Y` handling**:
        -   Parse target `x, y`.
        -   Calculate radii: `rx = abs(x - current_x)`, `ry = abs(y - current_y)`.
        -   Generate SVG Arc command: `A rx ry 0 0 0 x y` (Sweep flag 0 for CCW cornering).
        -   Update `current_x`, `current_y`.

2.  **Verify Sweep Flag**:
    -   The path goes `M top-right -> ... -> Left-Down corner`.
    -   (3600, 0) -> (0, 3600).
    -   If standard coordinate system, this is a convex turn if we are traversing the perimeter.
    -   Standard rounded rect paths in ODT usually go counter-clockwise (or clockwise?).
    -   If we use `0` and it looks "concave" (bites into shape), we flip to `1`.
    -   Round rectangle corners should bulge *out* (convex).
    -   Will use `0` initially based on vector direction logic (Turning Left relative to straight line).

## Verification Plan

### Automated Tests
-   Run `odt_to_html.py` on `sample_test_drawing.odt`.
-   Generate PNG and visually inspect.

### Manual Verification
-   Check `sample_test_drawing.html` to see if `rect` path now contains `A` commands for corners.
-   Verify visually that corners are rounded.
