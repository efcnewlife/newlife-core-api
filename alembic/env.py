import logging
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config
from sqlalchemy import pool

from portal.config import settings
from portal.libs.database.orm import Base
from portal.models import *  # noqa

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for "autogenerate" support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata
table_schema = settings.DATABASE_SCHEMA
# Allowed schemas for migrations
# NOTE: If you add a new schema, you need to add it to the ALLOWED_SCHEMAS list
ALLOWED_SCHEMAS = {"public", "auth", "audit", "org", "member", "facility", "content"}

# Get logger
log = logging.getLogger("alembic.env")


def _metadata_schemas() -> set[str]:
    """Collect distinct schema names from SQLAlchemy metadata (None -> public)."""
    schemas: set[str] = set()
    for table in target_metadata.tables.values():
        schemas.add(table.schema or "public")
    return schemas


def _check_allowed_schemas() -> bool:
    """Exit when ORM metadata contains schemas not listed in ALLOWED_SCHEMAS."""
    missing_from_allowed = _metadata_schemas() - ALLOWED_SCHEMAS
    if not missing_from_allowed:
        return True
    log.error(
        f"Schema mismatch: metadata contains schemas {missing_from_allowed} not in ALLOWED_SCHEMAS {ALLOWED_SCHEMAS}"
    )
    return False


def _emit_env_startup_logs() -> None:
    print("-" * 150)
    log.info("Checking allowed schemas...")
    try:
        is_allowed_schemas_ok = _check_allowed_schemas()
        if not is_allowed_schemas_ok:
            sys.exit(1)
    except Exception as exc:
        log.error("Error checking allowed schemas: %s", exc)
        sys.exit(1)
    finally:
        print("-" * 150)


_emit_env_startup_logs()

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.
config.set_main_option("sqlalchemy.url", settings.SQLALCHEMY_DATABASE_URI)


def include_name(name, type_, parent_names):
    if type_ == "schema":
        return name is None or name in ALLOWED_SCHEMAS
    if type_ == "table":
        schema_name = parent_names.get("schema_name")
        effective_schema = schema_name or "public"
        return effective_schema in ALLOWED_SCHEMAS and name != "alembic_version"
    return True


def include_object(obj, name, type_, reflected, compare_to) -> bool:
    """
    Control which objects will be included in the migration file
    :param obj: the object itself
    :param name: the object name
    :param type_: the object type (table, column, foreign_key_constraint, index, unique_constraint, check_constraint)
    :param reflected: whether the object is reflected from the database
    :param compare_to: the object to compare to
    :return:
    """
    # Exclude alembic_version table and system tables
    if type_ == "table":
        schema = getattr(obj, "schema", None) or settings.DATABASE_SCHEMA
        if schema not in ALLOWED_SCHEMAS:
            return False
        if name == "alembic_version" or name.startswith("pg_"):
            return False

    # Check constraint name length for PostgreSQL (max 63 characters)
    if type_ == "foreign_key_constraint" and len(name) > 63:
        log.warning(f"Foreign key constraint name '{name}' exceeds PostgreSQL limit of 63 characters (length: {len(name)})")

    # Process foreign key constraints: compare fields and referenced tables
    if type_ == "foreign_key_constraint" and compare_to is not None:
        if hasattr(obj, 'elements') and hasattr(compare_to, 'elements'):
            # Compare field names
            obj_columns = [elem.parent.name for elem in obj.elements]
            compare_columns = [elem.parent.name for elem in compare_to.elements]

            # Compare referenced table names (simple string comparison)
            obj_table = str(obj.referred_table).replace('public.', '')
            compare_table = str(compare_to.referred_table).replace('public.', '')

            # If fields and tables are the same, skip this constraint
            if obj_columns == compare_columns and obj_table == compare_table:
                return False

    return True


def run_migrations_offline() -> None:
    """Run migrations in "offline" mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don"t even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def process_revision_directives(context, revision, directives):
    """
    Process migration directives, reorder table columns to put 'id' first
    """
    if not config.cmd_opts or not getattr(config.cmd_opts, "autogenerate", False):
        return

    script = directives[0]
    if not script.upgrade_ops or not script.upgrade_ops.ops:
        log.warning("autogenerate empty; check ALLOWED_SCHEMAS in alembic/env.py.")
        return

    for op in script.upgrade_ops.ops:
        if not hasattr(op, 'columns') or not op.columns:
            continue

        # Separate id column from other columns
        columns = list(op.columns)
        id_columns = [col for col in columns if col.name == 'id']
        other_columns = [col for col in columns if col.name != 'id']

        # Reorder if id column exists
        if id_columns:
            op.columns = id_columns + other_columns


def run_migrations_online() -> None:
    """Run migrations in "online" mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_server_default=True,
            include_name=include_name,
            include_object=include_object,
            include_schemas=True,
            process_revision_directives=process_revision_directives,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
