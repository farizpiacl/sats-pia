from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required

from app import db
from app.models.category import Category, CategoryGroup
from app.forms.admin_forms import CategoryForm
from app.utils.decorators import super_admin_required
from app.utils.audit import log_action

admin_categories_bp = Blueprint("admin_categories", __name__, url_prefix="/admin/categories")

VALID_GROUPS = {g.value: g for g in CategoryGroup}


def _get_group(group_key):
    group = VALID_GROUPS.get(group_key)
    if group is None:
        abort(404)
    return group


@admin_categories_bp.route("/<group_key>/")
@login_required
@super_admin_required
def list_categories(group_key):
    group = _get_group(group_key)
    status_filter = request.args.get("status", "").strip()

    query = Category.query.filter_by(group=group)
    if status_filter == "active":
        query = query.filter(Category.is_active.is_(True))
    elif status_filter == "disabled":
        query = query.filter(Category.is_active.is_(False))

    items = query.order_by(Category.name).all()
    return render_template(
        "admin/categories_list.html",
        items=items,
        group=group,
        group_key=group_key,
        status_filter=status_filter,
        all_groups=CategoryGroup,
    )


@admin_categories_bp.route("/<group_key>/new", methods=["GET", "POST"])
@login_required
@super_admin_required
def create_category(group_key):
    group = _get_group(group_key)
    form = CategoryForm()

    if form.validate_on_submit():
        name = form.name.data.strip()
        if Category.query.filter_by(group=group, name=name).first():
            flash(f"A {group.label[:-1] if group.label.endswith('s') else group.label} named '{name}' already exists.", "danger")
            return render_template("admin/category_form.html", form=form, mode="create", group=group, group_key=group_key)

        item = Category(
            group=group,
            name=name,
            description=(form.description.data or "").strip() or None,
            is_active=form.is_active.data,
        )
        db.session.add(item)
        db.session.commit()
        log_action("CREATE", entity_type="Category", entity_id=item.id, description=f"Created {group.label} item '{item.name}'")
        flash(f"'{item.name}' added to {group.label}.", "success")
        return redirect(url_for("admin_categories.list_categories", group_key=group_key))

    return render_template("admin/category_form.html", form=form, mode="create", group=group, group_key=group_key)


@admin_categories_bp.route("/<group_key>/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
@super_admin_required
def edit_category(group_key, item_id):
    group = _get_group(group_key)
    item = Category.query.filter_by(group=group, id=item_id).first_or_404()
    form = CategoryForm(obj=item)

    if form.validate_on_submit():
        name = form.name.data.strip()
        existing = Category.query.filter(Category.group == group, Category.name == name, Category.id != item.id).first()
        if existing:
            flash(f"Another item in {group.label} already uses this name.", "danger")
            return render_template("admin/category_form.html", form=form, mode="edit", group=group, group_key=group_key, item=item)

        item.name = name
        item.description = (form.description.data or "").strip() or None
        item.is_active = form.is_active.data
        db.session.commit()
        log_action("UPDATE", entity_type="Category", entity_id=item.id, description=f"Updated {group.label} item '{item.name}'")
        flash(f"'{item.name}' updated.", "success")
        return redirect(url_for("admin_categories.list_categories", group_key=group_key))

    return render_template("admin/category_form.html", form=form, mode="edit", group=group, group_key=group_key, item=item)


@admin_categories_bp.route("/<group_key>/<int:item_id>/toggle-status", methods=["POST"])
@login_required
@super_admin_required
def toggle_status(group_key, item_id):
    group = _get_group(group_key)
    item = Category.query.filter_by(group=group, id=item_id).first_or_404()
    item.is_active = not item.is_active
    db.session.commit()
    action = "ENABLE" if item.is_active else "DISABLE"
    log_action(action, entity_type="Category", entity_id=item.id, description=f"{action.title()}d {group.label} item '{item.name}'")
    flash(f"'{item.name}' has been {'enabled' if item.is_active else 'disabled'}.", "success")
    return redirect(url_for("admin_categories.list_categories", group_key=group_key))
