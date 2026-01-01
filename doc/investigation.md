# Investigation

## v1 first version (by claude opus 4.5 thinking)


- Basic conversion work

### Issues

- Fonts differ from the those in original document
- Page split is not visible
- Image caption missing
- footnote not handle properly, show only the part at referencer with footnote number but not referenced footnote
- Drawing Object is not shown

Let me know if there is any difficulty in fixing these issues, 
e.g. recommended using exiting packages or library could help, or other limitation.

# v2  (by claude opus 4.5 thinking)

use of external resource is not preferred, the html should be offline viewable

# v3 (by google gemini 3 pro)

- `--page-breaks` should enable by default
- See a.odt, the figure number and caption is not shown properly
- See a.odt, drawing in frames doesn't work `figure 3: 選項設定視窗`
- strikethrough doesn't work at text `Obsidian WikiLink limitations motivated this approach`
- Tweak the tests accordingly for regression and reflects changes of features  
