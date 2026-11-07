import re,pypdfium2 as pdfium
def read(f):
    d=pdfium.PdfDocument(f)
    for i in range(min(len(d),8)):
        t=d[i].get_textpage().get_text_range()
        if "Latitude (SHL)" in t and "Latitude (BHL)" in t:
            la=re.search(r"Latitude \(SHL\)\s*(-?\d+\.\d+)",t); lb=re.search(r"Latitude \(BHL\)\s*(-?\d+\.\d+)",t)
            lo=re.findall(r"-\s?1\d\d\.\d{3,}",t)
            if la and lb and len(lo)>=2:
                return (float(la.group(1)),float(lo[0].replace(" ",""))),(float(lb.group(1)),float(lo[1].replace(" ","")))
    return None
