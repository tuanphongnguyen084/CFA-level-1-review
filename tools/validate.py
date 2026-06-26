"""
Validate every exam JSON under content/ against schema/exam.schema.json plus
semantic checks (answer must be a real option, ids unique within an exam).

Run before committing/pushing — exits non-zero if anything is wrong, so it can
also gate a CI workflow.

Usage:
    python tools/validate.py
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

from jsonschema import Draft7Validator  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(REPO, "content")
SCHEMA = os.path.join(REPO, "schema", "exam.schema.json")


def check_exam(path, validator):
    errs = []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:  # noqa: BLE001
        return [f"JSON lỗi: {e}"]

    for e in validator.iter_errors(data):
        loc = "/".join(str(p) for p in e.path)
        errs.append(f"{loc or '(root)'}: {e.message}")

    seen = set()
    for i, q in enumerate(data.get("questions", [])):
        if not isinstance(q, dict):
            continue
        opts = q.get("options", {})
        if isinstance(opts, dict) and q.get("answer") not in opts:
            errs.append(f"q[{i}]: answer '{q.get('answer')}' không nằm trong "
                        f"{sorted(opts)}")
        qid = q.get("id")
        if qid in seen:
            errs.append(f"q[{i}]: id trùng '{qid}'")
        seen.add(qid)
    return errs


def main():
    with open(SCHEMA, encoding="utf-8") as f:
        validator = Draft7Validator(json.load(f))

    n_files = n_q = n_bad = 0
    for subject_id in sorted(os.listdir(CONTENT)):
        sdir = os.path.join(CONTENT, subject_id)
        if not os.path.isdir(sdir):
            continue
        for fn in sorted(os.listdir(sdir)):
            if not fn.endswith(".json") or fn == "_subject.json":
                continue
            path = os.path.join(sdir, fn)
            n_files += 1
            errs = check_exam(path, validator)
            if errs:
                n_bad += 1
                print(f"❌ {subject_id}/{fn}")
                for e in errs[:10]:
                    print(f"     - {e}")
            else:
                with open(path, encoding="utf-8") as f:
                    n_q += len(json.load(f).get("questions", []))

    print(f"\n{n_files} đề · {n_q} câu hợp lệ · {n_bad} file lỗi")
    sys.exit(1 if n_bad else 0)


if __name__ == "__main__":
    main()
