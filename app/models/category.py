import enum
from app import db
from app.models.base import TimestampMixin


class CategoryGroup(enum.Enum):
    """The reference-data groups a Super Admin can manage independently of
    the fixed Activity workflow fields. These give operational control over
    labels/subcategories used for classification and reporting, without
    touching the core Activity schema (activity_type/maintenance_type
    remain fixed enums for data integrity)."""

    ACTIVITY_TYPE = "activity_type"
    MAINTENANCE_TYPE = "maintenance_type"
    TSR_CATEGORY = "tsr_category"
    MIC_CATEGORY = "mic_category"
    RI_CATEGORY = "ri_category"

    @property
    def label(self):
        return {
            CategoryGroup.ACTIVITY_TYPE: "Activity Types",
            CategoryGroup.MAINTENANCE_TYPE: "Maintenance Types",
            CategoryGroup.TSR_CATEGORY: "TSR Categories",
            CategoryGroup.MIC_CATEGORY: "MIC Categories",
            CategoryGroup.RI_CATEGORY: "RI Categories",
        }[self]


class Category(TimestampMixin, db.Model):
    """A Super-Admin-managed reference item used to sub-classify Engineer
    activities for reporting and filtering (e.g. specific TSR/MIC/RI
    categories, or descriptive maintenance sub-types). Disabling an item
    removes it from selection going forward without affecting any
    historical activity that already references it."""

    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    group = db.Column(db.Enum(CategoryGroup, name="category_group"), nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.String(300), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("group", "name", name="uq_category_group_name"),
        db.Index("ix_categories_group_active", "group", "is_active"),
    )

    def __repr__(self):
        return f"<Category {self.group.value}:{self.name}>"
