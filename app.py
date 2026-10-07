"""
Student Grade Management System  (Flask + JSON storage)
PUP-themed UI (maroon and gold)

Run:
    pip install flask
    python app.py
Then open http://127.0.0.1:5000

Grading scale follows PUP: 1.00 (highest) to 5.00 (lowest). 3.00 or better = Passed.
"""

import json
import os

from flask import Flask, flash, redirect, render_template, request, url_for
from jinja2 import DictLoader

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "students.json")
PASSING_GRADE = 3.00
MIN_GRADE, MAX_GRADE = 1.00, 5.00

app = Flask(__name__)
app.secret_key = "pup-grade-system"  # change this for real deployments


# ---------------------------------------------------------------- data layer
def load_students():
    """Return list of students: {"id", "name", "grades": {subject: grade}}"""
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_students(students):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(students, f, indent=2, ensure_ascii=False)


def find_student(students, student_id):
    for s in students:
        if s["id"].lower() == student_id.lower():
            return s
    return None


# ------------------------------------------------------------------ algorithms
def average(grades):
    """Average of a {subject: grade} dict, or None when empty."""
    if not grades:
        return None
    return round(sum(grades.values()) / len(grades), 2)


def remarks(avg):
    if avg is None:
        return "No grades"
    return "Passed" if avg <= PASSING_GRADE else "Failed"


def with_stats(students):
    """Add average, remarks and rank to each student (rank 1 = best average)."""
    rows = [dict(s, average=average(s["grades"])) for s in students]
    ranked = sorted(
        (r for r in rows if r["average"] is not None), key=lambda r: r["average"]
    )
    rank = 0
    prev = None
    for i, r in enumerate(ranked, start=1):
        if r["average"] != prev:  # ties share a rank
            rank = i
            prev = r["average"]
        r["rank"] = rank
    for r in rows:
        r.setdefault("rank", None)
        r["remarks"] = remarks(r["average"])
    return rows


def search(rows, query):
    q = query.strip().lower()
    if not q:
        return rows
    return [r for r in rows if q in r["id"].lower() or q in r["name"].lower()]


def sort_rows(rows, key):
    if key == "name":
        return sorted(rows, key=lambda r: r["name"].lower())
    if key == "id":
        return sorted(rows, key=lambda r: r["id"].lower())
    # default: performance (best average first, no-grade students last)
    return sorted(rows, key=lambda r: (r["average"] is None, r["average"] or 0))


def parse_form(form):
    """Validate the add/edit form. Returns (name, grades, errors)."""
    errors = []
    name = form.get("name", "").strip()
    if not name:
        errors.append("Student name is required.")

    grades = {}
    for subject, grade in zip(form.getlist("subject"), form.getlist("grade")):
        subject, grade = subject.strip(), grade.strip()
        if not subject and not grade:
            continue
        if not subject or not grade:
            errors.append("Each grade row needs both a subject and a grade.")
            continue
        try:
            value = float(grade)
        except ValueError:
            errors.append(f"Grade for {subject} must be a number.")
            continue
        if not (MIN_GRADE <= value <= MAX_GRADE):
            errors.append(f"Grade for {subject} must be between 1.00 and 5.00.")
            continue
        if subject.lower() in (k.lower() for k in grades):
            errors.append(f"{subject} is listed more than once.")
            continue
        grades[subject] = round(value, 2)
    return name, grades, errors


# ----------------------------------------------------------------------- routes
@app.route("/")
def index():
    q = request.args.get("q", "")
    sort = request.args.get("sort", "performance")
    rows = with_stats(load_students())

    graded = [r["average"] for r in rows if r["average"] is not None]
    stats = {
        "total": len(rows),
        "class_avg": round(sum(graded) / len(graded), 2) if graded else None,
        "passed": sum(1 for r in rows if r["remarks"] == "Passed"),
        "failed": sum(1 for r in rows if r["remarks"] == "Failed"),
    }
    rows = sort_rows(search(rows, q), sort)
    return render_template("index.html", rows=rows, q=q, sort=sort, stats=stats)


@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        students = load_students()
        student_id = request.form.get("id", "").strip()
        name, grades, errors = parse_form(request.form)
        if not student_id:
            errors.append("Student ID is required.")
        elif find_student(students, student_id):
            errors.append(f"Student ID {student_id} already exists.")
        if errors:
            for e in errors:
                flash(e, "error")
            draft = {"id": student_id, "name": name, "grades": grades}
            return render_template("form.html", student=draft, editing=False)
        students.append({"id": student_id, "name": name, "grades": grades})
        save_students(students)
        flash(f"Added {name}.", "ok")
        return redirect(url_for("index"))
    return render_template(
        "form.html", student={"id": "", "name": "", "grades": {}}, editing=False
    )


@app.route("/edit/<student_id>", methods=["GET", "POST"])
def edit(student_id):
    students = load_students()
    student = find_student(students, student_id)
    if not student:
        flash("Student not found.", "error")
        return redirect(url_for("index"))
    if request.method == "POST":
        name, grades, errors = parse_form(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
            draft = {"id": student["id"], "name": name, "grades": grades}
            return render_template("form.html", student=draft, editing=True)
        student["name"], student["grades"] = name, grades
        save_students(students)
        flash(f"Saved changes for {name}.", "ok")
        return redirect(url_for("index"))
    return render_template("form.html", student=student, editing=True)


@app.route("/delete/<student_id>", methods=["POST"])
def delete(student_id):
    students = load_students()
    student = find_student(students, student_id)
    if student:
        students.remove(student)
        save_students(students)
        flash(f"Deleted {student['name']}.", "ok")
    else:
        flash("Student not found.", "error")
    return redirect(url_for("index"))


# ------------------------------------------------------------------- templates
BASE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{% block title %}Grade Management{% endblock %} | PUP</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Libre+Baskerville:wght@700&family=Source+Sans+3:wght@400;600&display=swap" rel="stylesheet">
<style>
:root{
  --maroon:#800000; --maroon-dark:#5c0000; --gold:#e8b923; --gold-soft:#fbf1cf;
  --paper:#fbf8f3; --ink:#2a1a1a; --muted:#7a6a6a; --line:#e6dcd0; --ok:#2e6b3a; --bad:#a3231f;
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 "Source Sans 3",system-ui,sans-serif}
h1,h2{font-family:"Libre Baskerville",Georgia,serif;margin:0}
header{background:var(--maroon);border-bottom:5px solid var(--gold);color:#fff}
.bar{max-width:1050px;margin:auto;padding:14px 20px;display:flex;align-items:center;gap:20px;flex-wrap:wrap}
.brand{font-family:"Libre Baskerville",Georgia,serif;font-size:1.15rem;line-height:1.2}
.brand small{display:block;font:400 .8rem "Source Sans 3",sans-serif;color:var(--gold-soft);opacity:.9}
nav{margin-left:auto;display:flex;gap:6px}
nav a{color:#fff;text-decoration:none;padding:8px 14px;border-radius:6px;font-weight:600}
nav a:hover,nav a.on{background:var(--maroon-dark);box-shadow:inset 0 -3px 0 var(--gold)}
main{max-width:1050px;margin:26px auto;padding:0 20px}
.flash{padding:10px 14px;border-radius:6px;margin-bottom:10px;border-left:5px solid}
.flash.ok{background:#e9f4ec;border-color:var(--ok)}
.flash.error{background:#fbeaea;border-color:var(--bad)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:18px 0}
.stat{background:#fff;border:1px solid var(--line);border-top:4px solid var(--gold);border-radius:6px;padding:12px 16px}
.stat b{display:block;font:700 1.7rem "Libre Baskerville",Georgia,serif;color:var(--maroon)}
.stat span{color:var(--muted);font-size:.9rem}
.tools{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}
input,select{font:inherit;padding:9px 11px;border:1px solid #cdbfb0;border-radius:6px;background:#fff;color:var(--ink)}
input:focus,select:focus,.btn:focus-visible{outline:3px solid var(--gold);outline-offset:1px}
.tools input[type=search]{flex:1;min-width:200px}
.btn{display:inline-block;font:600 1rem "Source Sans 3",sans-serif;padding:9px 16px;border:0;border-radius:6px;background:var(--maroon);color:#fff;cursor:pointer;text-decoration:none}
.btn:hover{background:var(--maroon-dark)}
.btn.gold{background:var(--gold);color:var(--maroon-dark)}
.btn.gold:hover{background:#d4a617}
.btn.ghost{background:transparent;color:var(--maroon);border:1px solid var(--maroon)}
.btn.sm{padding:5px 11px;font-size:.9rem}
.btn.danger{background:transparent;color:var(--bad);border:1px solid var(--bad)}
.btn.danger:hover{background:var(--bad);color:#fff}
.wrap{overflow-x:auto;background:#fff;border:1px solid var(--line);border-radius:6px}
table{width:100%;border-collapse:collapse}
th{background:var(--maroon);color:#fff;text-align:left;padding:11px 14px;font-weight:600;white-space:nowrap}
td{padding:11px 14px;border-top:1px solid var(--line);vertical-align:top}
tr:nth-child(even) td{background:#fdfaf5}
.num{text-align:right;font-variant-numeric:tabular-nums}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{background:var(--gold-soft);border:1px solid #ecd98c;border-radius:20px;padding:1px 10px;font-size:.85rem;white-space:nowrap}
.tag{font-weight:600}.tag.p{color:var(--ok)}.tag.f{color:var(--bad)}.tag.n{color:var(--muted)}
.rank{font:700 1.05rem "Libre Baskerville",Georgia,serif;color:var(--maroon)}
.actions{display:flex;gap:6px;white-space:nowrap}
.empty{padding:36px;text-align:center;color:var(--muted)}
.card{background:#fff;border:1px solid var(--line);border-top:4px solid var(--gold);border-radius:6px;padding:24px;max-width:640px}
label{display:block;font-weight:600;margin:14px 0 4px}
.card input{width:100%}
.row{display:grid;grid-template-columns:1fr 130px auto;gap:8px;margin-bottom:8px}
.hint{color:var(--muted);font-size:.9rem;margin:2px 0 8px}
footer{text-align:center;color:var(--muted);font-size:.85rem;padding:30px 0}
</style>
</head>
<body>
<header><div class="bar">
  <div class="brand">Polytechnic University of the Philippines<small>Student Grade Management System</small></div>
  <nav>
    <a href="{{ url_for('index') }}" class="{{ 'on' if request.endpoint == 'index' }}">Students</a>
    <a href="{{ url_for('add') }}" class="{{ 'on' if request.endpoint == 'add' }}">Add student</a>
  </nav>
</div></header>
<main>
  {% for cat, msg in get_flashed_messages(with_categories=true) %}
    <div class="flash {{ cat }}">{{ msg }}</div>
  {% endfor %}
  {% block body %}{% endblock %}
</main>
<footer>Grades use the PUP scale: 1.00 is highest, 3.00 is the passing mark, 5.00 is failed.</footer>
</body>
</html>"""

INDEX = """{% extends "base.html" %}
{% block body %}
<h1>Students</h1>
<div class="stats">
  <div class="stat"><b>{{ stats.total }}</b><span>Students</span></div>
  <div class="stat"><b>{{ '%.2f'|format(stats.class_avg) if stats.class_avg else '-' }}</b><span>Class average</span></div>
  <div class="stat"><b>{{ stats.passed }}</b><span>Passed</span></div>
  <div class="stat"><b>{{ stats.failed }}</b><span>Failed</span></div>
</div>

<form class="tools" method="get">
  <input type="search" name="q" value="{{ q }}" placeholder="Search by name or student ID" aria-label="Search">
  <select name="sort" aria-label="Sort by" onchange="this.form.submit()">
    <option value="performance" {{ 'selected' if sort == 'performance' }}>Sort: Best performance</option>
    <option value="name" {{ 'selected' if sort == 'name' }}>Sort: Name (A-Z)</option>
    <option value="id" {{ 'selected' if sort == 'id' }}>Sort: Student ID</option>
  </select>
  <button class="btn" type="submit">Search</button>
  {% if q %}<a class="btn ghost" href="{{ url_for('index') }}">Clear</a>{% endif %}
  <a class="btn gold" href="{{ url_for('add') }}">Add student</a>
</form>

<div class="wrap">
{% if rows %}
<table>
  <thead><tr><th>Rank</th><th>Student ID</th><th>Name</th><th>Grades</th><th class="num">Average</th><th>Remarks</th><th></th></tr></thead>
  <tbody>
  {% for r in rows %}
    <tr>
      <td class="rank">{{ r.rank or '-' }}</td>
      <td>{{ r.id }}</td>
      <td>{{ r.name }}</td>
      <td><div class="chips">
        {% for subj, g in r.grades.items() %}<span class="chip">{{ subj }}: {{ '%.2f'|format(g) }}</span>{% else %}<span class="tag n">None yet</span>{% endfor %}
      </div></td>
      <td class="num">{{ '%.2f'|format(r.average) if r.average else '-' }}</td>
      <td><span class="tag {{ 'p' if r.remarks == 'Passed' else 'f' if r.remarks == 'Failed' else 'n' }}">{{ r.remarks }}</span></td>
      <td><div class="actions">
        <a class="btn ghost sm" href="{{ url_for('edit', student_id=r.id) }}">Edit</a>
        <form method="post" action="{{ url_for('delete', student_id=r.id) }}" onsubmit="return confirm('Delete {{ r.name|e }}?')">
          <button class="btn danger sm" type="submit">Delete</button>
        </form>
      </div></td>
    </tr>
  {% endfor %}
  </tbody>
</table>
{% else %}
  <div class="empty">
    {% if q %}No student matches "{{ q }}". Try a different name or ID.{% else %}No students yet. <a href="{{ url_for('add') }}">Add the first student</a>.{% endif %}
  </div>
{% endif %}
</div>
{% endblock %}"""

FORM = """{% extends "base.html" %}
{% block title %}{{ 'Edit student' if editing else 'Add student' }}{% endblock %}
{% block body %}
<h1>{{ 'Edit student' if editing else 'Add student' }}</h1>
<form class="card" method="post" style="margin-top:18px">
  <label for="id">Student ID</label>
  <input id="id" name="id" value="{{ student.id }}" {{ 'readonly' if editing else 'required' }} placeholder="e.g. 2023-00123-CL-0">

  <label for="name">Full name</label>
  <input id="name" name="name" value="{{ student.name }}" required placeholder="Last name, First name">

  <label>Grades</label>
  <p class="hint">Use the PUP scale, 1.00 to 5.00. Leave a row empty to skip it.</p>
  <div id="rows">
    {% for subj, g in student.grades.items() %}
    <div class="row">
      <input name="subject" value="{{ subj }}" placeholder="Subject" aria-label="Subject">
      <input name="grade" type="number" step="0.01" min="1" max="5" value="{{ '%.2f'|format(g) }}" placeholder="Grade" aria-label="Grade">
      <button class="btn danger sm" type="button" onclick="this.parentNode.remove()">Remove</button>
    </div>
    {% endfor %}
  </div>
  <button class="btn ghost sm" type="button" onclick="addRow()">Add subject</button>

  <div style="margin-top:22px;display:flex;gap:10px">
    <button class="btn" type="submit">{{ 'Save changes' if editing else 'Add student' }}</button>
    <a class="btn ghost" href="{{ url_for('index') }}">Cancel</a>
  </div>
</form>

<script>
function addRow(){
  const d = document.createElement('div');
  d.className = 'row';
  d.innerHTML = '<input name="subject" placeholder="Subject" aria-label="Subject">' +
    '<input name="grade" type="number" step="0.01" min="1" max="5" placeholder="Grade" aria-label="Grade">' +
    '<button class="btn danger sm" type="button" onclick="this.parentNode.remove()">Remove</button>';
  document.getElementById('rows').appendChild(d);
  d.firstChild.focus();
}
if (!document.querySelector('#rows .row')) addRow();
</script>
{% endblock %}"""

app.jinja_loader = DictLoader(
    {"base.html": BASE, "index.html": INDEX, "form.html": FORM}
)

if __name__ == "__main__":
    app.run(debug=True)