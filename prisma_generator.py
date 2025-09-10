import json
from pathlib import Path

# Mapping JSON types to Prisma types
TYPE_MAP = {
    "Float": "Float",
    "float32": "Float",
    "Double": "Float",
    "String": "String",
    "string": "String",
    "Boolean": "Boolean",
    "Int16": "Int",
    "int16": "Int",
    "Int32": "Int",
    "int32": "Int",
    "Int64": "BigInt",
    "int64": "BigInt",
    "BOOL": "Boolean",
    "BYTE": "Int",
    "WORD": "Int",
    "DWORD": "Int",
    "SINT": "Int",
    "USINT": "Int",
    "INT": "Int",
    "UINT": "Int",
    "DINT": "Int",
    "UDINT": "Int",
    "REAL": "Float",
    "STRING": "String",
}


def make_recipe_model(model_name: str, fields: dict) -> str | None:
    """Generate Prisma recipe_* model with back-reference to recipe_data."""
    if not fields:
        return None

    prisma_fields = ["  id BigInt @id @unique"]
    for key, field in fields.items():
        t = field.get("type") or field.get("dataType")
        prisma_type = TYPE_MAP.get(t, "String")
        prisma_fields.append(f"  {key} {prisma_type}?")

    # back-reference to recipe_data
    rel_name = f"{model_name}_rel"
    prisma_fields.append(
        f'  recipe_data recipe_data @relation("{rel_name}", fields: [id], references: [id], onDelete: Cascade)'
    )

    return f"model {model_name} {{\n" + "\n".join(prisma_fields) + "\n}\n"


def make_job_models(sources: dict) -> tuple[str, list[str]]:
    """Generate main job model and job_* models with relationships."""
    job_model = None
    other_jobs = []

    for src_name, fields in sources.items():
        if src_name == "job":
            # Main job model
            prisma_fields = ["  id Int @id @default(autoincrement())"]
            has_recipe = False
            for key, field in fields.items():
                if key == "recipe_id":
                    has_recipe = True
                t = field.get("type") or field.get("dataType")
                prisma_type = TYPE_MAP.get(t, "String")
                prisma_fields.append(f"  {key} {prisma_type}?")

            # adding some special relationships
            if has_recipe:
                prisma_fields.append(
                    f'  recipe_data recipe_data?  @relation("recipe_rel", fields: [recipe_id], references: [id], onDelete: Cascade)'
                )
            prisma_fields.append(
                f'  status_timestamp status_timestamp[] @relation("status_timestamp_rel")'
            )

            job_model = "model job {\n" + "\n".join(prisma_fields) + "\n}\n"
        else:
            if not fields == {}:
                # Child job model
                model_name = f"job_{src_name}"
                prisma_fields = ["  id Int @id @unique"]
                for key, field in fields.items():
                    t = field.get("type") or field.get("dataType")
                    prisma_type = TYPE_MAP.get(t, "String")
                    prisma_fields.append(f"  {key} {prisma_type}?")

                rel_name = f"{model_name}_rel"
                prisma_fields.append(
                    f'  job job @relation("{rel_name}", fields: [id], references: [id], onDelete: Cascade)'
                )
                other_jobs.append((model_name, prisma_fields, rel_name))

    # Add back-relations into main job model
    if job_model and other_jobs:
        job_lines = job_model.splitlines()
        for model_name, _, rel_name in other_jobs:
            job_lines.insert(
                -1, f'  {model_name} {model_name}[] @relation("{rel_name}")'
            )
        job_model = "\n".join(job_lines)

    # Render other job models
    job_models = []
    for model_name, prisma_fields, _ in other_jobs:
        job_models.append(
            "model " + model_name + " {\n" + "\n".join(prisma_fields) + "\n}\n"
        )

    return job_model, job_models


def make_recipe_data_model(recipe_models: list[str]) -> str:
    prisma_fields = [
        '  id        BigInt  @id @default(dbgenerated("floor(EXTRACT(epoch FROM now()))"))',
        "  name      String",
        "  new       Boolean @default(false)",
        "  colorNum  Int",
        "  notes     String?",
        "  status    Int     @default(0) // status 0 ready 1 loaded in the machine",
        '  updatedAt BigInt  @default(dbgenerated("floor(EXTRACT(epoch FROM now()))"))',
        '  job       job[]   @relation("recipe_rel")',
    ]

    for rm in recipe_models:
        rel_name = f"{rm}_rel"
        prisma_fields.append(f'  {rm} {rm}? @relation("{rel_name}")')

    return "model recipe_data {\n" + "\n".join(prisma_fields) + "\n}\n"


def parse_sources_config(source_file: Path) -> dict:
    """Return {source_name: {field_name: field_def,...}}"""
    with open(source_file) as f:
        data = json.load(f)
    sources = {}
    for src in data.get("sources", []):
        name = src["source"]
        sources[name] = src["fields"]
    return sources


def generate_recipe_models(
    folder_base: Path, sources: dict
) -> tuple[list[str], list[str]]:
    recipe_models = []
    recipe_model_names = []

    for folder in folder_base.iterdir():
        if folder.is_dir():
            config_file = folder / "config.json"
            if config_file.exists():
                with open(config_file) as f:
                    data = json.load(f)
                folder_name = folder.name
                model_name = f"recipe_{folder_name}"

                fields = data.get("data", {})

                # Filter if folder name matches a source
                for src_name, src_fields in sources.items():
                    if src_name in folder_name:
                        fields = {
                            k: v for k, v in fields.items() if k not in src_fields
                        }

                prisma_fields = {k: {"type": v["type"]} for k, v in fields.items()}
                model_str = make_recipe_model(model_name, prisma_fields)
                if model_str:
                    recipe_models.append(model_str)
                    recipe_model_names.append(model_name)
                else:
                    print(f"Skipped {model_name}, no fields left after filtering")

    return recipe_models, recipe_model_names


def static_models() -> str:
    """Return the always-present models."""
    return """
model status_timestamp {
  id        Int      @id @default(autoincrement())
  timestamp DateTime @default(now())
  status    Int      @default(0)
  job_id    Int
  job_data  job      @relation("status_timestamp_rel", fields: [job_id], references: [id], onDelete: Cascade)
}

model app_heartbeat {
  name           String   @id
  job_id         Int?
  last_heartbeat DateTime @updatedAt
}

model User {
  id        String   @id @default(uuid())
  username  String   @unique
  password  String
  role      String   @default("USER") // Can be "USER", "ADMIN", etc.
  createdAt DateTime @default(now())
  updatedAt DateTime @default(now()) @updatedAt
}
"""


if __name__ == "__main__":
    base_path = Path(
        "../rw_configs"
    )  # where your folders (folder1, dummy_1, etc.) live
    sources_file = Path("../config_fe_be/config.json")

    sources = parse_sources_config(sources_file)

    recipe_models, recipe_model_names = generate_recipe_models(base_path, sources)
    recipe_data_model = make_recipe_data_model(recipe_model_names)

    job_model, job_models = make_job_models(sources)

    schema = (
        "generator client {\n"
        '  provider = "prisma-client-js"\n'
        "}\n\n"
        "datasource db {\n"
        '  provider = "postgresql"\n'
        '  url      = env("DATABASE_URL")\n'
        "}\n\n"
        + recipe_data_model
        + "\n"
        + "\n".join(recipe_models)
        + "\n"
        + job_model
        + "\n"
        + "\n".join(job_models)
        + "\n"
        + static_models()
    )

    # Path to schema file
    schema_file = Path("../prisma_schema/schema.prisma")

    # Create parent directories if they don't exist
    schema_file.parent.mkdir(parents=True, exist_ok=True)

    # Write the schema
    schema_file.write_text(schema)

    print("schema.prisma generated")
