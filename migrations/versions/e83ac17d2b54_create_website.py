"""Create public website content and form tables."""

import sqlalchemy as sa
from alembic import op

revision = "e83ac17d2b54"
down_revision = "71b27dc9e804"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "website_media",
        sa.Column(
            "kind",
            sa.Enum("VIDEO", "PDF", name="kind", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_website_media")),
    )
    op.create_table(
        "website_galleries",
        sa.Column(
            "category",
            sa.Enum(
                "INICIO",
                "HOTEL",
                "HABITACIONES",
                "RESTAURANTE",
                "BAR",
                "SERVICIOS",
                name="category",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_website_galleries")),
    )
    op.create_table(
        "website_gallery_images",
        sa.Column("gallery_id", sa.Uuid(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["gallery_id"],
            ["website_galleries.id"],
            name=op.f("fk_website_gallery_images_gallery_id_website_galleries"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_website_gallery_images")),
    )
    op.create_index(
        op.f("ix_website_gallery_images_gallery_id"),
        "website_gallery_images",
        ["gallery_id"],
        unique=False,
    )
    op.create_table(
        "website_descriptions",
        sa.Column(
            "category",
            sa.Enum(
                "INICIO",
                "HOTEL",
                "HABITACIONES",
                "RESTAURANTE",
                "BAR",
                "SERVICIOS",
                name="category",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_website_descriptions")),
        sa.UniqueConstraint("category", name=op.f("uq_website_descriptions_category")),
    )
    op.create_table(
        "website_complaints",
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column(
            "document_type",
            sa.Enum(
                "SIN DOCUMENTO",
                "DNI",
                "RUC",
                "CARNET DE EXTRANJERIA",
                "PASAPORTE",
                name="document_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("document_number", sa.String(length=32), nullable=False),
        sa.Column(
            "request_type",
            sa.Enum(
                "QUEJA", "RECLAMO", name="request_type", native_enum=False, create_constraint=True
            ),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("expected_solution", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount >= 0", name=op.f("ck_website_complaints_nonnegative_amount")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_website_complaints")),
    )
    op.create_table(
        "website_contacts",
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_website_contacts")),
    )


def downgrade() -> None:
    op.drop_table("website_contacts")
    op.drop_table("website_complaints")
    op.drop_table("website_descriptions")
    op.drop_table("website_gallery_images")
    op.drop_table("website_galleries")
    op.drop_table("website_media")
