"""
Convert an Excel/CSV question bank into exam JSON files — the MAIN way admins
add content.

Spreadsheet columns (header row, case-insensitive; extra columns ignored):

    exam_id      required  short id -> filename, e.g. "reading-1" (one per exam)
    exam_name    optional  display title; defaults to exam_id
    group        optional  sub-heading shown in the subject view
    question     required  the question stem
    A, B         required  options (C and D optional)
    C, D         optional
    answer       required  one of A/B/C/D
    explanation  optional
    tags         optional  separated by ; or ,

Rows are grouped by exam_id, so one spreadsheet can hold many exams. Each .xlsx
sheet is read; for .csv the single sheet is read. Generated files land in
content/<subject>/<exam_id>.json.

Usage:
    python tools/xlsx_to_json.py path/to/bank.xlsx --subject economics
    python tools/xlsx_to_json.py path/to/bank.csv  --subject quant --dry-run
"""
import argparse
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OPTION_COLS = ["A", "B", "C", "D"]


def _norm(s):
    # drop spaces, underscores and hyphens so "exam_id"/"Exam Id" -> "examid"
    return re.sub(r"[\s_-]+", "", str(s)).lower()


def _frames(path):
    if path.lower().endswith(".csv"):
        return [pd.read_csv(path, dtype=str, keep_default_na=False,
                            encoding="utf-8-sig")]
    xls = pd.ExcelFile(path)
    return [xls.parse(sh, dtype=str, keep_default_na=False)
            for sh in xls.sheet_names]


def _colmap(df):
    """lowercased-name -> actual column name."""
    return {_norm(c): c for c in df.columns}


def parse(path):
    exams = {}      # exam_id -> {"name", "group", "questions": [...]}
    errors = []
    skipped = []
    for si, df in enumerate(_frames(path)):
        if df.empty:
            continue
        cols = _colmap(df)
        missing = [n for n in ("examid", "question", "answer") if n not in cols]
        if missing:
            # Not a question sheet (e.g. the HƯỚNG DẪN guide) — skip quietly.
            skipped.append(f"sheet #{si + 1}: thiếu cột {missing} "
                           f"(có: {list(df.columns)})")
            continue

        for ri, row in df.iterrows():
            exam_id = str(row[cols["examid"]]).strip()
            qtext = str(row[cols["question"]]).strip()
            if not exam_id or not qtext:
                continue  # skip blank rows

            options = {}
            for L in OPTION_COLS:
                key = _norm(L)
                if key in cols:
                    val = str(row[cols[key]]).strip()
                    if val:
                        options[L] = val
            answer = str(row[cols["answer"]]).strip().upper()
            if len(options) < 2:
                errors.append(f"[{exam_id}] dòng {ri + 2}: cần ≥2 đáp án")
                continue
            if answer not in options:
                errors.append(f"[{exam_id}] dòng {ri + 2}: answer '{answer}' "
                              f"không nằm trong {sorted(options)}")
                continue

            ex = exams.setdefault(exam_id, {
                "name": str(row[cols["examname"]]).strip()
                if "examname" in cols and str(row[cols["examname"]]).strip()
                else exam_id,
                "group": str(row[cols["group"]]).strip() if "group" in cols else "",
                "questions": [],
            })
            q = {
                "id": f"{exam_id}-{len(ex['questions']) + 1}",
                "question": qtext,
                "options": options,
                "answer": answer,
                "explanation": (str(row[cols["explanation"]]).strip()
                                if "explanation" in cols else ""),
            }
            if "tags" in cols:
                raw = str(row[cols["tags"]]).strip()
                tags = [t.strip() for t in re.split(r"[;,]", raw) if t.strip()]
                if tags:
                    q["tags"] = tags
            ex["questions"].append(q)
    if not exams and skipped:
        errors.extend(skipped)   # surface why nothing was found
    return exams, errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="Path to .xlsx or .csv")
    ap.add_argument("--subject", required=True,
                    help="Subject folder under content/ (e.g. economics)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Parse and report, but don't write files")
    args = ap.parse_args()

    exams, errors = parse(args.input)
    for e in errors:
        print(f"⚠️  {e}")
    if not exams:
        print("Không tạo được đề nào. Kiểm tra lại file/cột.")
        sys.exit(1)

    outdir = os.path.join(REPO, "content", args.subject)
    total = 0
    for exam_id, ex in exams.items():
        data = {
            "schema_version": 1,
            "id": exam_id,
            "name": ex["name"],
            "group": ex["group"],
            "questions": ex["questions"],
        }
        n = len(ex["questions"])
        total += n
        dest = os.path.join(outdir, f"{exam_id}.json")
        if args.dry_run:
            print(f"[dry-run] {args.subject}/{exam_id}.json — {n} câu")
        else:
            os.makedirs(outdir, exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"✅ {args.subject}/{exam_id}.json — {n} câu")

    print(f"\nXong: {len(exams)} đề, {total} câu"
          + (" (dry-run, chưa ghi)" if args.dry_run else "")
          + f"{'' if args.dry_run else f' -> content/{args.subject}/'}")
    if errors:
        print(f"({len(errors)} dòng bị bỏ qua — xem cảnh báo ở trên)")


if __name__ == "__main__":
    main()
