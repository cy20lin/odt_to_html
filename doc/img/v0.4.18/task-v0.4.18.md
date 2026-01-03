# Task: Refactor Paragraph Anchoring for Draw Objects

- [x] Analyze [inspect_arrow.py](inspect_arrow.py) and existing resources
- [x] Create a minimal reproduction test case (if possible, or use existing)
- [x] Create [implementation_plan.md](.gemini/antigravity/brain/3919c318-9557-49b5-bcae-030f5132f7fa/implementation_plan.md)
- [x] Refactor [odt_to_html.py](odt_to_html.py)
    - [x] Modify [_process_paragraph](odt_to_html.py#496-519) to separate inline content and anchored objects
    - [x] update [_process_inline_content](odt_to_html.py#564-580) or create new helpers to extract anchored objects while preserving text flow (tails)
    - [x] Implement `div.paragraph-anchor` wrapper
- [x] Verify the fix
    - [x] Run conversion on sample ODT
    - [x] specific check for [sample_annotated_image.odt](sample_annotated_image.odt) (arrow 3)
