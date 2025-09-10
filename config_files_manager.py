import os
import json
import subprocess

# Replace this with your actual repo URL
REPO_URL = "git@github.com:OmetSRL/recipe_deployment_config.git"

def process_config(config_data):
    # 1. Create folder config_fe_be and save config.json
    fe_be_config = config_data.get("config_fe_be", {})
    config_content = fe_be_config.get("config_content", {})

    os.makedirs("../config_fe_be", exist_ok=True)
    with open(os.path.join("../config_fe_be", "config.json"), "w", encoding="utf-8") as f:
        json.dump(config_content, f, indent=2, ensure_ascii=False)

    print("Created config_fe_be/config.json")

    # 2. Loop over rw_configs and clone repos
    rw_configs = config_data.get("rw_configs", {})
    for rw_name, rw_info in rw_configs.items():
        branch_name = rw_info.get("branch_name")
        if not branch_name:
            print(f"Skipping {rw_name}, no branch_name provided")
            continue

        parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../rw_configs"))
        target_dir = os.path.join(parent_dir, rw_name)
        if os.path.exists(target_dir):
            print(f"Directory {target_dir} already exists, skipping clone")
            continue

        print(f"Cloning branch '{branch_name}' into '{target_dir}'...")
        try:
            subprocess.run(
                ["git", "clone", "--branch", branch_name, "--single-branch", REPO_URL, target_dir],
                check=True
            )
            print(f"Cloned {rw_name}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to clone {rw_name} ({branch_name}): {e}")

if __name__ == "__main__":
    # Example usage: reading from a file
    with open("../input_config/config.json", "r", encoding="utf-8") as f:
        config_data = json.load(f)

    process_config(config_data)
