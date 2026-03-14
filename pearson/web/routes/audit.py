from flask import Blueprint, render_template, request, redirect, url_for
from app import db
from app.models import AuditStatus, Module, Template

bp = Blueprint("audit", __name__, url_prefix="/audit")

@bp.route("/")
def index():
    audits = AuditStatus.query.all()
    return render_template("audit/index.html", audits=audits)

@bp.route("/update", methods=["GET", "POST"])
def update_audit():
    modules = Module.query.all()
    templates = Template.query.all()
    if request.method == "POST":
        module_id = request.form["module_id"]
        template_id = request.form["template_id"]
        status = request.form["status"]
        last_updated = request.form["last_updated"]
        audit = AuditStatus(module_id=module_id, template_id=template_id, status=status, last_updated=last_updated)
        db.session.add(audit)
        db.session.commit()
        return redirect(url_for("audit.index"))
    return render_template("audit/update.html", modules=modules, templates=templates)