from flask import Blueprint, render_template, request, redirect, url_for
from app import db
from app.models import Module

bp = Blueprint("modules", __name__, url_prefix="/modules")

@bp.route("/")
def index():
    modules = Module.query.all()
    return render_template("modules/index.html", modules=modules)

@bp.route("/add", methods=["GET", "POST"])
def add_module():
    if request.method == "POST":
        name = request.form["name"]
        description = request.form["description"]
        new_module = Module(name=name, description=description)
        db.session.add(new_module)
        db.session.commit()
        return redirect(url_for("modules.index"))
    return render_template("modules/add.html")