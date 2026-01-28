from flask import Blueprint, render_template, request, redirect, url_for
from app import db
from app.models import Template

bp = Blueprint("templates", __name__, url_prefix="/templates")

@bp.route("/")
def index():
    templates = Template.query.all()
    return render_template("templates/index.html", templates=templates)

@bp.route("/add", methods=["GET", "POST"])
def add_template():
    if request.method == "POST":
        name = request.form["name"]
        category = request.form["category"]
        file_path = request.form["file_path"]
        format = request.form["format"]
        pearson_link = request.form["pearson_link"]
        new_template = Template(name=name, category=category, file_path=file_path, format=format, pearson_link=pearson_link)
        db.session.add(new_template)
        db.session.commit()
        return redirect(url_for("templates.index"))
    return render_template("templates/add.html")