from flask import Blueprint, render_template, request, redirect, url_for
from app import db
from app.models import Document, Module

bp = Blueprint("documents", __name__, url_prefix="/documents")

@bp.route("/")
def index():
    documents = Document.query.all()
    return render_template("documents/index.html", documents=documents)

@bp.route("/add", methods=["GET", "POST"])
def add_document():
    modules = Module.query.all()
    if request.method == "POST":
        module_id = request.form["module_id"]
        title = request.form["title"]
        type = request.form["type"]
        source = request.form["source"]
        file_path = request.form["file_path"]
        new_doc = Document(module_id=module_id, title=title, type=type, source=source, file_path=file_path)
        db.session.add(new_doc)
        db.session.commit()
        return redirect(url_for("documents.index"))
    return render_template("documents/add.html", modules=modules)