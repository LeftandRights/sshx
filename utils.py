import requests, os, json
from secrets import token_urlsafe

INSTANCE_DIR: str = os.path.join(os.getcwd(), "instances")


def fetch_docker_image(name: str) -> dict:
    res = requests.get(f"https://hub.docker.com/v2/search/repositories/?query={name}&page_size=10")

    if res.status_code == 200:
        results = [repo for repo in res.json()["results"] if repo["repo_name"] == name]
        return results


def load_instances() -> list[dict]:
    collections = []

    os.makedirs(INSTANCE_DIR, exist_ok=True)

    for instance_id in os.listdir(INSTANCE_DIR):
        instance_path = os.path.join(INSTANCE_DIR, instance_id)

        if not os.path.isdir(instance_path):
            continue

        with open(os.path.join(instance_path, "config.json"), "r") as file:
            collections.append(json.loads(file.read()))

    return collections


def create_instances(instance_name: str, ram: int, core: int) -> None:
    instance_id = token_urlsafe(22)
    instance_dir = os.path.join(INSTANCE_DIR, instance_id)

    os.mkdir(instance_dir)
    os.mkdir(os.path.join(instance_dir, "workspace"))

    with open(os.path.join(instance_dir, "config.json"), "w") as file:
        json.dump(
            {
                "instance_id": instance_id,
                "instance_name": instance_name,
                "status": "stopped",
                "ram": ram,
                "core": core,
                "uptime": "0",
                "instance_config": {
                    "docker_image": "",
                    "install_command": "",
                    "run_command": "",
                },
            },
            file,
            indent=2,
        )


def get_data_by_id(instance_id: str) -> dict:
    instance_dir = os.path.join(INSTANCE_DIR, instance_id)

    if not os.path.exists(instance_dir) or not os.path.isdir(instance_dir):
        return

    with open(os.path.join(instance_dir, "config.json")) as file:
        return json.load(file)


def write(instance_id: str, data: dict) -> None:
    instance_dir = os.path.join(INSTANCE_DIR, instance_id)

    if not os.path.exists(instance_dir) or not os.path.isdir(instance_dir):
        return

    with open(os.path.join(instance_dir, "config.json"), "w") as file:
        json.dump(data, file, indent=2)


def create_docker_file(instance_id: str) -> None:
    instance_dir = os.path.join(INSTANCE_DIR, instance_id)
    data = json.load(open(os.path.join(instance_dir, "config.json")))

    data["is_installing"] = True
    write(instance_id, data)

    docker_image = data["instance_config"]["docker_image"]
    install_command = data["instance_config"]["install_command"]
    run_command = data["instance_config"]["run_command"]
    # workspace_dir = os.path.join(instance_dir, "workspace")

    with open(os.path.join(instance_dir, "entrypoint.sh"), "w") as file:
        file.write(
            f"""#!/bin/bash
echo "===== 🔧 Installing dependencies... {" (Skipping)" if not install_command else ""} =====\n\n"
{install_command if install_command else ""}

echo "\n\n===== 🚀 Starting application... =====\n\n"
{run_command}
tail -f /dev/null"""
        )

    with open(os.path.join(instance_dir, "Dockerfile"), "w") as file:
        file.write(
            f"""
FROM {docker_image}
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace
COPY workspace/ .
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]""".strip()
        )


# RUN {install_command}
# CMD {json.dumps(run_command.split())}
