from flask import Blueprint, render_template, request, redirect, url_for
from app import db
from app.models import Assignment, Module

bp = Blueprint("assignments", __name__, url_prefix="/assignments")

@bp.route("/")
def index():
    assignments = Assignment.query.all()
    return render_template("assignments/index.html", assignments=assignments)

@bp.route("/add", methods=["GET", "POST"])
def add_assignment():
    modules = Module.query.all()
    if request.method == "POST":
        module_id = request.form["module_id"]
        title = request.form["title"]
        brief = request.form["brief"]
        criteria = request.form["criteria"]
        new_assignment = Assignment(module_id=module_id, title=title, brief=brief, criteria=criteria)
        db.session.add(new_assignment)
        db.session.commit()
        return redirect(url_for("assignments.index"))
    return render_template("assignments/add.html", modules=modules)