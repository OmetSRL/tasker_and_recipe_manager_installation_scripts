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


def make_job_card_model(model_name: str, fields: dict) -> str | None:
    """Generate Prisma job_card_* model with back-reference to job_card_metadata."""
    if not fields:
        return None

    prisma_fields = ["  id BigInt @id @unique"]
    for key, field in fields.items():
        t = field.get("type") or field.get("dataType")
        prisma_type = TYPE_MAP.get(t, "String")
        prisma_fields.append(f"  {key} {prisma_type}?")

    # back-reference to job_card_metadata
    rel_name = f"{model_name}_rel"
    prisma_fields.append(
        f'  job_card_metadata job_card_metadata @relation("{rel_name}", fields: [id], references: [id], onDelete: Cascade)'
    )

    return f"model {model_name} {{\n" + "\n".join(prisma_fields) + "\n}\n"


def make_task_models(sources: dict) -> tuple[str, list[str]]:
    """Generate main task model and task_* models with relationships."""
    task_model = None
    other_tasks = []

    for src_name, fields in sources.items():
        if "generic_" in src_name:
            # Main task model
            prisma_fields = ["  id Int @id @default(autoincrement())"]
            has_job_card = False
            for key, field in fields.items():
                if key == "job_card_id":
                    has_job_card = True
                t = field.get("type") or field.get("dataType")
                prisma_type = TYPE_MAP.get(t, "String")
                if key == 'odp':
                    prisma_fields.append(f"  {key} {prisma_type} @unique")
                else:
                    prisma_fields.append(f"  {key} {prisma_type}?")

            # adding some special relationships
            if has_job_card:
                prisma_fields.append(
                    f'  job_card_metadata job_card_metadata?  @relation("job_card_rel", fields: [job_card_id], references: [id], onDelete: SetNull)'
                )
            prisma_fields.append(f"  createdAt DateTime @default(now())")
            prisma_fields.append(f'  status_timestamp status_timestamp[] @relation("status_timestamp_rel")')

            task_model = (
                "model "
                + src_name.replace("generic_", "")
                + " {\n"
                + "\n".join(prisma_fields)
                + "\n}\n"
            )
        else:
            if not fields == {}:
                # Child task model
                model_name = f"task_{src_name}"
                prisma_fields = ["  id Int @id @unique"]
                for key, field in fields.items():
                    t = field.get("type") or field.get("dataType")
                    prisma_type = TYPE_MAP.get(t, "String")
                    prisma_fields.append(f"  {key} {prisma_type}?")

                rel_name = f"{model_name}_rel"
                prisma_fields.append(
                    f'  task task @relation("{rel_name}", fields: [id], references: [id], onDelete: Cascade)'
                )
                other_tasks.append((model_name, prisma_fields, rel_name))

    # Add back-relations into main task model
    if task_model and other_tasks:
        task_lines = task_model.splitlines()
        for model_name, _, rel_name in other_tasks:
            task_lines.insert(
                -1, f'  {model_name} {model_name}[] @relation("{rel_name}")'
            )
        task_model = "\n".join(task_lines)

    # Render other task models
    task_models = []
    for model_name, prisma_fields, _ in other_tasks:
        task_models.append(
            "model " + model_name + " {\n" + "\n".join(prisma_fields) + "\n}\n"
        )

    return task_model, task_models


def make_job_card_metadata_model(job_card_models: list[str]) -> str:
    prisma_fields = [
        '  id        BigInt  @id @default(dbgenerated("floor(EXTRACT(epoch FROM now()))"))',
        "  name      String",
        "  new       Boolean @default(false)",
        "  colorNum  Int",
        "  notes     String?",
        "  status    Int     @default(0) // status 0 ready 1 loaded in the machine",
        '  updatedAt BigInt  @default(dbgenerated("floor(EXTRACT(epoch FROM now()))"))',
        '  task       task[]   @relation("job_card_rel")',
    ]

    for rm in job_card_models:
        rel_name = f"{rm}_rel"
        prisma_fields.append(f'  {rm} {rm}? @relation("{rel_name}")')

    return "model job_card_metadata {\n" + "\n".join(prisma_fields) + "\n}\n"


def parse_sources_config(source_file: Path) -> dict:
    """Return {source_name: {field_name: field_def,...}}"""
    with open(source_file) as f:
        data = json.load(f)
    sources = {}
    for src in data.get("sources", []):
        # i add generic_ in front of the generic sources aka the basic task model and maybe something else in the future
        name = (
            src["source"]
            if src["generic_fields"] != True
            else f'generic_{src["source"]}'
        )
        sources[name] = src["fields"]
    return sources


def generate_job_card_models(
    folder_base: Path, sources: dict
) -> tuple[list[str], list[str]]:
    job_card_models = []
    job_card_model_names = []

    for folder in folder_base.iterdir():
        if folder.is_dir():
            config_file = folder / "config.json"
            if config_file.exists():
                with open(config_file) as f:
                    data = json.load(f)
                folder_name = folder.name
                model_name = f"job_card_{folder_name}"

                fields = data.get("data", {})

                # Filter if folder name matches a source
                for src_name, src_fields in sources.items():
                    if src_name in folder_name:
                        fields = {
                            k: v for k, v in fields.items() if k not in src_fields
                        }

                prisma_fields = {k: {"type": v["type"]} for k, v in fields.items()}
                model_str = make_job_card_model(model_name, prisma_fields)
                if model_str:
                    job_card_models.append(model_str)
                    job_card_model_names.append(model_name)
                else:
                    print(f"Skipped {model_name}, no fields left after filtering")

    return job_card_models, job_card_model_names


def static_models() -> str:
    """Return the always-present models."""
    return """
model status_timestamp {
  id        Int      @id @default(autoincrement())
  timestamp DateTime @default(now())
  status    Int      @default(0)
  task_id    Int
  task_data  task      @relation("status_timestamp_rel", fields: [task_id], references: [id], onDelete: Cascade)
}

model app_heartbeat {
  name           String   @id
  task_id         Int?
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

    job_card_models, job_card_model_names = generate_job_card_models(base_path, sources)
    job_card_metadata_model = make_job_card_metadata_model(job_card_model_names)

    task_model, task_models = make_task_models(sources)

    schema = (
        "generator client {\n"
        '  provider = "prisma-client-js"\n'
        '  output = "../generated/prisma"\n'
        "}\n\n"
        "generator jsonSchema {\n"
        '  provider = "prisma-json-schema-generator"\n'
        '  output = "../json-schema"\n'
        '  includeRequiredFields = "true"\n'
        '  keepRelationFields = "false"\n'
        "}\n\n"
        "datasource db {\n"
        '  provider = "postgresql"\n'
        '  url      = env("DATABASE_URL")\n'
        "}\n\n"
        + job_card_metadata_model
        + "\n"
        + "\n".join(job_card_models)
        + "\n"
        + task_model
        + "\n"
        + "\n".join(task_models)
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
