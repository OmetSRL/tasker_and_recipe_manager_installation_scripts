# Task Executor deployment script

This script is used to prepare the enviroment for the installation of the Tasker and/or the Job Card Manger application.\
It installs all the required packages, logs in Docker Hub and launches some setup Python scripts.\
You need to pass the Docker Hub username, the password and the ssh jey for the github like:\
./setup_script.sh <username_dockerhub> <password_dockerhub> <ssh_key_for_github>
\
The Python scripts execute these operations:

 1. clones the correct configs for the RW modules from this repo <https://github.com/OmetSRL/tasker_and_recipe_manager_installation_scripts> and prepares the backend/Tasker configs
 2. generates the prisma file (the DB schema essentially) from the configs prepared in the step before
 3. generate the docker compose file and all the required volumes

Once executed this repo can be deleted since each required file is generated outside this folder, to start the application after the execution you only need to do docker compose up
