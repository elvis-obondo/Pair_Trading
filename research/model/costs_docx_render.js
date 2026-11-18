// COSTS1 Word report renderer. Reads ONLY research/model/logs/costs1/costs_report.md (written by
// research/model/diagnostics/costs_report_md.py) and formats it as Word. It holds no numbers and no findings.
//   cd research/model && node costs_docx_render.js
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType, HeadingLevel,
  PageOrientation,
} = require("docx");

const ROOT = path.resolve(__dirname, "..", "..");
const SRC = path.join(ROOT, "research/model/logs/costs1/costs_report.md");
const OUT = process.env.COSTS_DOCX_OUT || path.join(process.env.HOME, "Downloads/HL-COSTS1_costs_report.docx");
const lines = fs.readFileSync(SRC, "utf8").split("\n");

const PAGE_W = 12240, PAGE_H = 15840, MARGIN = 720, TABLE_W = PAGE_H - 2 * MARGIN;

function runs(text, size, bold) {
  const out = [];
  text.split(/(\*\*[^*]+\*\*)/).forEach((part) => {
    if (!part) return;
    const b = part.startsWith("**") && part.endsWith("**");
    out.push(new TextRun({ text: b ? part.slice(2, -2) : part, bold: bold || b, font: "Arial", size }));
  });
  return out;
}
const para = (t) => new Paragraph({ children: runs(t, 20), spacing: { after: 100 } });
const bullet = (t, lvl) => new Paragraph({ children: runs(t, 20), numbering: { reference: "bul", level: lvl }, spacing: { after: 60 } });
const heading = (t, n) => new Paragraph({ children: [new TextRun({ text: t })], heading: [HeadingLevel.TITLE, HeadingLevel.HEADING_1, HeadingLevel.HEADING_2, HeadingLevel.HEADING_3, HeadingLevel.HEADING_4][n - 1] });

function cell(text, width, header, fs) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: header ? { type: ShadingType.CLEAR, fill: "D9D9D9", color: "auto" } : undefined,
    margins: { top: 30, bottom: 30, left: 60, right: 60 },
    children: [new Paragraph({ children: runs(String(text), fs, header) })],
  });
}
function table(rows) {
  const cells = rows.map((r) => r.split("|").slice(1, -1).map((c) => c.trim()));
  const head = cells[0], body = cells.slice(2);
  const n = head.length;
  const fs = n > 10 ? 13 : n > 7 ? 15 : 17;
  const wt = head.map((h, i) => Math.min(30, Math.max(6, Math.min(h.length, 14), ...body.map((r) => String(r[i] || "").length))));
  const sum = wt.reduce((a, b) => a + b, 0);
  const w = wt.map((x) => Math.floor((x / sum) * TABLE_W));
  w[0] += TABLE_W - w.reduce((a, b) => a + b, 0);
  const hr = new TableRow({ tableHeader: true, children: head.map((h, i) => cell(h, w[i], true, fs)) });
  const br = body.map((r) => new TableRow({ children: head.map((_, i) => cell(r[i] === undefined ? "" : r[i], w[i], false, fs)) }));
  return new Table({ width: { size: TABLE_W, type: WidthType.DXA }, columnWidths: w, rows: [hr, ...br] });
}

const body = [];
let i = 0;
let first = true;
while (i < lines.length) {
  const ln = lines[i];
  if (ln.startsWith("|")) {
    const blk = [];
    while (i < lines.length && lines[i].startsWith("|")) blk.push(lines[i++]);
    body.push(table(blk));
    body.push(new Paragraph({ children: [], spacing: { after: 80 } }));
    continue;
  }
  const m = /^(#{1,5}) (.*)$/.exec(ln);
  if (m) {
    const lvl = m[1].length;
    body.push(heading(m[2], first ? 0 + 1 : lvl + 0));
    if (first) { body[body.length - 1] = new Paragraph({ children: [new TextRun({ text: m[2] })], heading: HeadingLevel.TITLE }); first = false; }
  } else if (/^ {4}- /.test(ln)) body.push(bullet(ln.replace(/^ {4}- /, ""), 1));
  else if (/^- /.test(ln)) body.push(bullet(ln.slice(2), 0));
  else if (ln.trim() !== "") body.push(para(ln));
  i++;
}

const doc = new Document({
  numbering: { config: [{ reference: "bul", levels: [
    { level: 0, format: "bullet", text: "•", alignment: "left", style: { paragraph: { indent: { left: 540, hanging: 270 } } } },
    { level: 1, format: "bullet", text: "–", alignment: "left", style: { paragraph: { indent: { left: 1080, hanging: 270 } } } }] }] },
  styles: {
    default: {
      document: { run: { font: "Arial", size: 20 } },
      heading1: { run: { font: "Arial", size: 32, bold: true }, paragraph: { spacing: { before: 240, after: 120 }, keepNext: true } },
      heading2: { run: { font: "Arial", size: 26, bold: true }, paragraph: { spacing: { before: 200, after: 100 }, keepNext: true } },
      heading3: { run: { font: "Arial", size: 22, bold: true }, paragraph: { spacing: { before: 160, after: 80 }, keepNext: true } },
      heading4: { run: { font: "Arial", size: 20, bold: true }, paragraph: { spacing: { before: 120, after: 60 }, keepNext: true } },
      title: { run: { font: "Arial", size: 40, bold: true }, paragraph: { spacing: { before: 0, after: 200 }, keepNext: true } },
    },
  },
  sections: [{
    properties: { page: { size: { width: PAGE_W, height: PAGE_H, orientation: PageOrientation.LANDSCAPE }, margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN } } },
    children: body,
  }],
});
Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT, buf);
  console.log(`[DOCX] wrote ${OUT} (${buf.length} bytes) from ${SRC} (${lines.length} lines)`);
});
