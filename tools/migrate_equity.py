"""
One-off migration: convert the OLD Equity quiz_app data (file1.json with 8
readings, file2.json with 7 blocks) into the new per-exam layout:

    content/equity/_subject.json
    content/equity/reading-39.json ... reading-46.json
    content/equity/equity-valuation-1.json ... -7.json

Re-running is safe (it overwrites). After this, the old quiz_app/ is no longer
needed by the app.

Usage:
    python tools/migrate_equity.py [--src "<path to old data folder>"]
"""
import argparse
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")  # Windows console is cp1252 by default

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "content", "equity")
DEFAULT_SRC = r"e:\phongnt\CFA\Equity\quiz_app\data"

KEEP = ("id", "question", "options", "answer", "explanation", "answer_source")

SUBJECT_META = {
    "name": "Equity Investments",
    "icon": "📈",
    "order": 6,
    "weight": "11–14%",
    "description": "Tổ chức thị trường, chỉ số, hiệu quả thị trường và định giá "
                   "cổ phiếu.",
}


def clean_question(q, exam_id, i):
    out = {k: q[k] for k in KEEP if k in q}
    out.setdefault("id", f"{exam_id}-{i + 1}")
    return out


def write_exam(exam_id, name, group, questions):
    data = {
        "schema_version": 1,
        "id": exam_id,
        "name": name,
        "group": group,
        "questions": [clean_question(q, exam_id, i) for i, q in enumerate(questions)],
    }
    path = os.path.join(OUT, f"{exam_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return len(data["questions"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC,
                    help="Folder containing old file1.json / file2.json")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "_subject.json"), "w", encoding="utf-8") as f:
        json.dump(SUBJECT_META, f, ensure_ascii=False, indent=2)

    total = 0
    # --- file1: one exam per Reading -------------------------------------- #
    with open(os.path.join(args.src, "file1.json"), encoding="utf-8") as f:
        f1 = json.load(f)
    for s in f1["sets"]:
        m = re.match(r"R(\d+)", s["id"])
        num = m.group(1) if m else s["id"]
        n = write_exam(f"reading-{num}", s["name"],
                       "Câu hỏi ôn tập (Reading 39–46)", s["questions"])
        total += n
        print(f"  reading-{num}.json — {n} câu")

    # --- file2: one exam per 20-question block ---------------------------- #
    with open(os.path.join(args.src, "file2.json"), encoding="utf-8") as f:
        f2 = json.load(f)
    for i, s in enumerate(f2["sets"], 1):
        n = write_exam(f"equity-valuation-{i}", s["name"],
                       "Reading Equity Valuation (Reading 48)", s["questions"])
        total += n
        print(f"  equity-valuation-{i}.json — {n} câu")

    print(f"OK — {total} câu vào {OUT}")


if __name__ == "__main__":
    main()
