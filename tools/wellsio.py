"""Read and write index.html with the wells array (const D=[...]) stored in data/wells.js.

index.html keeps a one-line marker (//@D) where the array used to be, and loads data/wells.js with a <script> tag
before the main script. The helpers present the "virtual" page text, with the array inlined exactly as before, so
scripts that slice the text between "const D=" and ";\\nconst GRID" keep working unchanged.

    s = wellsio.read_index(path)        # page text with the array inlined (works on either layout)
    wellsio.write_index(path, s)        # splits the array back out to data/wells.js and writes the page
"""
import os

MARK = "//@D\n"
TAG = '<script src="data/wells.js"></script>\n'


def _wells_path(index):
    return os.path.join(os.path.dirname(os.path.abspath(index)), "data", "wells.js")


def read_index(index="index.html"):
    s = open(index).read()
    if MARK not in s:
        return s                      # old layout: array still inline
    return s.replace(TAG, "", 1).replace(MARK, open(_wells_path(index)).read(), 1)


def write_index(index, s):
    """s is the virtual text (array inline). Writes data/wells.js and the page with the marker."""
    i = s.index("const D=")
    j = s.index(";\nconst GRID", i) + 2
    open(_wells_path(index), "w").write(s[i:j])
    page = s[:i] + MARK + s[j:]
    if TAG not in page:
        k = page.rindex("<script>", 0, page.index(MARK))
        page = page[:k] + TAG + page[k:]
    open(index, "w").write(page)
