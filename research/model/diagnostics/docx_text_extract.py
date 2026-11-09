"""Checker's requirement: a text extraction of the rendered .docx, and a check that every number in
that text appears somewhere in s1_profit1_docx_data.json (the renderer's only data source).

    python -u research/model/diagnostics/docx_text_extract.py
"""
import html
import json
import os
import re
import subprocess
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DOCX_PATH = os.path.expanduser("~/Downloads/HL-PROFIT1_backtest_24_runs.docx")
DATA_PATH = os.path.join(ROOT, "research", "model", "logs", "s1", "s1_profit1_docx_data.json")
TEXT_OUT = os.path.join(ROOT, "research", "model", "diagnostics", "docx_extracted_text.txt")

T_RE = re.compile(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", re.DOTALL)
NUM_RE = re.compile(r"-?\d[\d,]*\.?\d*")


def extract_text():
    with zipfile.ZipFile(DOCX_PATH) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    texts = T_RE.findall(xml)
    full = html.unescape("\n".join(texts))
    open(TEXT_OUT, "w").write(full)
    return full


def flatten_json_numbers(obj, out):
    if isinstance(obj, dict):
        for v in obj.values():
            flatten_json_numbers(v, out)
    elif isinstance(obj, list):
        for v in obj:
            flatten_json_numbers(v, out)
    elif isinstance(obj, (int, float)):
        out.add(obj)
    elif isinstance(obj, str):
        for m in NUM_RE.findall(obj):
            try:
                out.add(float(m.replace(",", "")))
            except ValueError:
                pass


DECIMAL_NDS = (0, 1, 2, 3, 4, 6)


def decimal_variants(x):
    """Same-magnitude formatting differences only (2dp vs 4dp, thousands separator, trailing zeros)."""
    return {round(x, nd) for nd in DECIMAL_NDS}


def pct_variants(x):
    """Checker's condition 2: the doc sometimes prints a JSON fraction as a percentage, or vice
    versa -- kept SEPARATE from decimal_variants so provenance (did a number match on its own
    magnitude, or only via a x100/x100 conversion) can be reported, not just folded into one set."""
    return {round(x * 100, 2), round(x / 100, 6)}


def n_sig_figs(x):
    s = f"{abs(x):.10g}".replace(".", "").lstrip("0")
    return len(s)


def main():
    text = extract_text()
    print(f"[DOCXCHECK] extracted {len(text)} chars to {TEXT_OUT}")

    data = json.load(open(DATA_PATH))
    json_numbers = set()
    flatten_json_numbers(data, json_numbers)

    decimal_norm, pct_norm = set(), set()
    for x in json_numbers:
        decimal_norm |= decimal_variants(x)
        pct_norm |= pct_variants(x)
    print(f"[DOCXCHECK] {len(json_numbers)} distinct numbers found in docx_data.json "
          f"({len(decimal_norm)} decimal-rounding variants, {len(pct_norm)} %-conversion variants)")

    doc_numbers = set()
    for m in NUM_RE.findall(text):
        try:
            doc_numbers.add(float(m.replace(",", "")))
        except ValueError:
            pass
    print(f"[DOCXCHECK] {len(doc_numbers)} distinct numbers found in the extracted docx text")

    not_found, decimal_matches, pct_only_matches = [], [], []
    for x in sorted(doc_numbers):
        if x in decimal_norm:
            decimal_matches.append(x)
        elif x in pct_norm:
            pct_only_matches.append(x)
        else:
            not_found.append(x)

    print(f"[DOCXCHECK] matched via decimal rounding only: {len(decimal_matches)}")
    print(f"[DOCXCHECK] matched via %-conversion only (checker's condition 2): {len(pct_only_matches)}")
    sig3_pct_only = [x for x in pct_only_matches if n_sig_figs(x) >= 3]
    print(f"[DOCXCHECK]   of those, with 3+ significant digits: {len(sig3_pct_only)}")
    for x in sig3_pct_only:
        print(f"  {x}")

    print(f"[DOCXCHECK] numbers in the docx NOT found (after normalization) in docx_data.json: "
          f"{len(not_found)}")
    for x in not_found:
        print(f"  {x}")


if __name__ == "__main__":
    main()
