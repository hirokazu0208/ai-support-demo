"""create inquiries table

Revision ID: d39d3345e879
Revises: 
Create Date: 2026-10-06 23:21:29.478299

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd39d3345e879'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # category / status は SQLite・PostgreSQL 共通の VARCHAR + CHECK 制約で保存する。
    # CHECK 制約は Enum に自動生成させず（create_constraint=False）、名前付きで明示する。
    # Alembic 1.20.0 の autogenerate は SQLAlchemy 2.1 の Enum 由来の CHECK 制約を判別できず、
    # 同名の制約を重複して出力するため（docs/demo2/step2-database-layer.md 参照）。
    op.create_table(
        "inquiries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "category",
            sa.Enum(
                "ACCOUNT",
                "NETWORK",
                "SOFTWARE",
                "OTHER",
                name="category",
                native_enum=False,
                create_constraint=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "OPEN",
                "IN_PROGRESS",
                "CLOSED",
                name="status",
                native_enum=False,
                create_constraint=False,
                length=20,
            ),
            server_default="OPEN",
            nullable=False,
        ),
        # 日時は UTC。SQLite では DATETIME、PostgreSQL では TIMESTAMP WITH TIME ZONE になる
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "category IN ('ACCOUNT', 'NETWORK', 'SOFTWARE', 'OTHER')",
            name=op.f("ck_inquiries_category"),
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'IN_PROGRESS', 'CLOSED')",
            name=op.f("ck_inquiries_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inquiries")),
    )
    op.create_index(
        op.f("ix_inquiries_created_at"), "inquiries", ["created_at"], unique=False
    )
    op.create_index(op.f("ix_inquiries_status"), "inquiries", ["status"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_inquiries_status"), table_name="inquiries")
    op.drop_index(op.f("ix_inquiries_created_at"), table_name="inquiries")
    op.drop_table("inquiries")
