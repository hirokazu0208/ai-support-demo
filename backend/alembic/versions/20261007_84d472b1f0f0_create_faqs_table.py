"""create faqs table

Revision ID: 84d472b1f0f0
Revises: d39d3345e879
Create Date: 2026-10-07 11:46:31.260819

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '84d472b1f0f0'
down_revision: Union[str, Sequence[str], None] = 'd39d3345e879'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # FAQ（AI Agent の FAQ 検索 Tool が参照する）。category は inquiries と同じ値を
    # VARCHAR + 名前付き CHECK 制約で保存する。Alembic 1.20.0 の autogenerate は SQLAlchemy 2.1 の
    # Enum 由来の CHECK 制約を重複して出力するため、初期 migration と同様に Enum には制約を作らせず
    # 明示する（docs/demo2/step2-database-layer.md 参照）。
    op.create_table(
        "faqs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("question", sa.String(length=200), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
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
        sa.Column("keywords", sa.String(length=500), nullable=False),
        # 日時は UTC。SQLite では DATETIME、PostgreSQL では TIMESTAMP WITH TIME ZONE になる
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "category IN ('ACCOUNT', 'NETWORK', 'SOFTWARE', 'OTHER')",
            name=op.f("ck_faqs_category"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_faqs")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("faqs")
