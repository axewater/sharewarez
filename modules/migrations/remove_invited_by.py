from alembic import op
import sqlalchemy as sa

def upgrade():
    # Remove the foreign key constraint first
    op.drop_constraint('users_invited_by_fkey', 'users', type_='foreignkey')
    # Then remove the column
    op.drop_column('users', 'invited_by')

def downgrade():
    # Add the column back
    op.add_column('users', sa.Column('invited_by', sa.Integer(), nullable=True))
    # Recreate the foreign key constraint
    op.create_foreign_key('users_invited_by_fkey', 'users', 'users', ['invited_by'], ['id'])
