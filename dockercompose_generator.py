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

# Get db_config section
db_config = input_config["db_config"]

name_of_db = ""

# Loop through all DB entries (e.g. postgres-db, mysql-db, etc.)
for db_name, db_values in db_config.items():
    name_of_db = db_name
    # Adding custom ones
    services[db_name] = {
        "image": "postgres:15",
        "container_name": "postgres-db",
        "environment": [
            "POSTGRES_USER=" + db_values["postgres_user"],
            "POSTGRES_PASSWORD=" + db_values["postgres_password"],
            "POSTGRES_DB=" + db_values["postgres_db"],
        ],
        "healthcheck": {
            "test": ["CMD", "pg_isready", "-U", "postgres"],
            "interval": "5s",
            "timeout": "5s",
            "retries": 10,
            "start_period": "20s",
        },
        "mem_limit": "300M",
        "cpus": "1.0",
        "volumes": ["postgres_data:/var/lib/postgresql/data"],
        "restart": "always",
        "networks": ["task-job_card-orchestrator"],
    }


def handleCommonConfig():
    if input_config["config_fe_be"]["image_name_fe_job_card"] != "":
        services["job_card_manager"] = {
            "image": input_config["config_fe_be"]["image_name_fe_job_card"],
            "container_name": "job_card_manager",
            "healthcheck": {
                "test": ["CMD", "curl", "-f", "https://localhost:5000/"],
                "interval": "30s",
                "timeout": "5s",
                "retries": 3,
                "start_period": "20s",
            },
            "mem_limit": "200M",
            "cpus": "0.5",
            "volumes": ["shared_token:/app/job_card_token"],
            "ports": ["5000:5000"],
            "restart": "always",
            "networks": ["task-job_card-orchestrator"],
        }

    if input_config["config_fe_be"]["image_name_fe_task"] != "":
        services["tasker"] = {
            "image": input_config["config_fe_be"]["image_name_fe_task"],
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
                "./logs/orchestrator:/backend-logs",
                "./config_fe_be/config.json:/app/src/config/config.js",
            ],
            "mem_limit": "200M",
            "cpus": "0.5",
            "ports": ["4000:4000"],
            "restart": "always",
            "networks": ["task-job_card-orchestrator"],
        }

    if input_config["config_fe_be"]["image_name_be"] != "":
        os.makedirs("../converted_attachments", exist_ok=True)
        os.makedirs("../logs/orchestrator", exist_ok=True)
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
            "environment": [
                f'DATABASE_URL=postgresql://{db_config[name_of_db]["postgres_user"]}:{db_config[name_of_db]["postgres_password"]}@{name_of_db}:5432/{db_config[name_of_db]["postgres_db"]}?schema=public'
            ],
            "depends_on": {"postgres-db": {"condition": "service_healthy"}},
            "volumes": [
                "shared_token:/app/job_card_token",
                "./logs/orchestrator:/logs",
                "./converted_attachments:/app/converted-output",
                "./prisma_schema:/app/prisma",
                "./config_fe_be/config.json:/app/src/config/config.js",
            ],
            "mem_limit": "200M",
            "cpus": "2",
            "ports": ["3000:3000"],
            "command": 'sh -c "npm run db:push && npm start"',
            "restart": "always",
            "networks": ["task-job_card-orchestrator"],
        }


handleCommonConfig()

print("---rw configs----")
print(input_config["rw_configs"])
print("---rw configs----")

for rw_name, rw_values in input_config["rw_configs"].items():
    print("inside loop: "+rw_name)
    print("inside loop: "+str(rw_values))
    folder_path = os.path.join(parent_folder, rw_name)
    file_path = os.path.join(folder_path, "config.json")
    print("inside loop: "+folder_path)
    
    if os.path.isfile(file_path):
        services[rw_name] = {
            "image": rw_values["image_name"],
            "container_name": rw_name,
            "volumes": ["./rw_configs/" + rw_name + "/config.json:/app/config.json"],
            "mem_limit": "200M",
            "cpus": "0.5",
            "restart": "always",
            "volumes":["./logs/"+rw_name+":/logs"],
            "networks": ["task-job_card-orchestrator"],
        }


# log viewer services
if input_config["config_log_viewer"]["logs_viewer_be"] != "":
    services["logs_viewer_be"] = {
        "container_name": "logs_viewer_be",
        "image": input_config["config_log_viewer"]["logs_viewer_be"],
        "restart": "always",
        "user": "0:0",
        "networks": ["task-job_card-orchestrator"],
        "ports": ["3001:8000"],
        "volumes": ["/var/run/docker.sock:/var/run/docker.sock"],
        "environment": ["DOCKER_HOST=unix:///var/run/docker.sock"]
    }

if input_config["config_log_viewer"]["logs_viewer_fe"] != "":
    services["logs_viewer_fe"] = {
        "container_name": "logs_viewer_fe",
        "image": input_config["config_log_viewer"]["logs_viewer_fe"],
        "restart": "always",
        "user": "0:0",
        "networks": ["task-job_card-orchestrator"],
        "ports": ["3002:4600"],
        "volumes": ["./logs/:/app/dist/logs"],
        "environment": ["DOCKER_HOST=unix:///var/run/docker.sock"]
    }

# Create the Docker Compose file content
docker_compose = {
    "services": services,
    "volumes": {
        "postgres_data": {"driver": "local"},
        "converted_output": {"driver": "local"},
        "shared_token": {"driver": "local"},
    },
    "networks": {"task-job_card-orchestrator": {"name": "task-job_card-orchestrator"}},
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
