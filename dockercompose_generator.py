import os
import yaml
import json

parent_folder = "../rw_configs"

# reading the config file
with open("../input_config/config.json", "r") as f:
    input_config = json.load(f)


# --- Custom scalar string for folded formatting ---
class FoldedScalarString(str):
    pass


# --- Custom dumper ---
class CustomDumper(yaml.SafeDumper):
    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


# --- Represent FoldedScalarString with style='>' ---
def folded_scalar_representer(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data), style=">")


# --- Represent lists using block style ---
def block_list_representer(dumper, data):
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=False)


# --- Register the representers ---
CustomDumper.add_representer(FoldedScalarString, folded_scalar_representer)
CustomDumper.add_representer(list, block_list_representer)


# Custom function to clean and format the string correctly for folded scalar style
def clean_folded_string(input_str):
    input_str = input_str.strip()

    folded_lines = "\n".join(
        line.strip() for line in input_str.splitlines() if line.strip()
    )
    # Return as FoldedScalarString for proper YAML representation
    return FoldedScalarString(folded_lines + "\n")


# Directory containing config files
input_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "configs")

services = {}

# Adding custom ones
services["postgres-db"] = {
    "image": "postgres:15",
    "container_name": "postgres-db",
    "environment": [
        "POSTGRES_USER=postgres",
        "POSTGRES_PASSWORD=ADM",
        "POSTGRES_DB=omet",
    ],
    "healthcheck": {
        "test": ["CMD", "pg_isready", "-U", "postgres"],
        "interval": "5s",
        "timeout": "5s",
        "retries": 10,
        "start_period": "20s",
    },
    "volumes": ["postgres_data:/var/lib/postgresql/data"],
    "restart": "always",
    "networks": ["job-recipe-orchestrator"],
}


def handleCommonConfig():
    if input_config["config_fe_be"]["image_name_fe_recipe"] != "":
        services["recipe_manager"] = {
            "image": input_config["config_fe_be"]["image_name_fe_recipe"],
            "container_name": "recipe_manager",
            "healthcheck": {
                "test": ["CMD", "curl", "-f", "https://localhost:5000/"],
                "interval": "30s",
                "timeout": "5s",
                "retries": 3,
                "start_period": "20s",
            },
            "volumes": ["shared_token:/app/recipe_token"],
            "ports": ["5000:5000"],
            "restart": "always",
            "networks": ["job-recipe-orchestrator"],
        }

    if input_config["config_fe_be"]["image_name_fe_job"] != "":
        services["tasker"] = {
            "image": input_config["config_fe_be"]["image_name_fe_job"],
            "container_name": "tasker",
            "healthcheck": {
                "test": ["CMD", "curl", "-f", "https://localhost:4000/"],
                "interval": "30s",
                "timeout": "5s",
                "retries": 3,
                "start_period": "20s",
            },
            "volumes": [
                "./tasker-logs:/app/dist/logs",
                "./backend-logs:/backend-logs",
                "./config_fe_be/config.json:/app/src/config/config.js",
            ],
            "ports": ["4000:4000"],
            "restart": "always",
            "networks": ["job-recipe-orchestrator"],
        }

    if input_config["config_fe_be"]["image_name_be"] != "":
        services["orchestrator"] = {
            "image": input_config["config_fe_be"]["image_name_be"],
            "container_name": "orchestrator",
            "healthcheck": {
                "test": ["CMD", "curl", "-fsSL", "http://localhost:3000/api/health"],
                "interval": "30s",
                "timeout": "5s",
                "retries": 3,
                "start_period": "20s",
            },
            "depends_on": {"postgres-db": {"condition": "service_healthy"}},
            "volumes": [
                "./backend-logs:/logs",
                "shared_token:/app/recipe_token",
                "converted_output:/app/converted-output",
                "prisma_schema:/app/prisma",
                "./config_fe_be/config.json:/app/src/config/config.js",
            ],
            "ports": ["3000:3000"],
            "command": ['sh -c "npm run db:push && npm start"'],
            "restart": "always",
            "networks": ["job-recipe-orchestrator"],
        }


handleCommonConfig()

for rw_name, rw_values in input_config["rw_configs"].items():

    folder_path = os.path.join(parent_folder, rw_name)
    file_path = os.path.join(folder_path, "config.json")

    if os.path.isfile(file_path):
        services[rw_name] = {
            "image": rw_values["image_name"],
            "container_name": rw_values["image_name"],
            "volumes": ["./rw_configs/" + rw_name + "/config.json:/app/config.json"],
            "restart": "always",
            "networks": ["job-recipe-orchestrator"],
        }


# Create the Docker Compose file content
docker_compose = {
    "services": services,
    "volumes": {
        "postgres_data": {"driver": "local"},
        "converted_output": {"driver": "local"},
        "shared_token": {"driver": "local"},
    },
    "networks": {"job-recipe-orchestrator": {"name": "job-recipe-orchestrator"}},
}

# Step 6: Dump using the custom dumper
yaml_output = yaml.dump(
    docker_compose,
    Dumper=CustomDumper,
    default_flow_style=False,
    sort_keys=False,
    indent=2,
    width=120,
    allow_unicode=True,
)

# Post-process the YAML output to strip extra newlines
yaml_output = yaml_output.replace("\n\n", "\n")
yaml_output = yaml_output.replace("'''", "'")

output_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "docker-compose.yml"
)

# Now write the cleaned YAML output to the file
with open(output_path, "w") as f:
    f.write(yaml_output)

print("docker-compose.yml generated.")
