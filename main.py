import streamlit, secrets, time
import os, requests, subprocess
import threading, shutil

from streamlit_autorefresh import st_autorefresh
import streamlit.components.v1 as components

from functools import partial
from utils import fetch_docker_image, load_instances, create_instances
import utils

streamlit.set_page_config(layout="wide")
streamlit.markdown('<style> [data-testid="stSidebar"] { display: none } </style>', unsafe_allow_html=True)

INITIAL_HEIGHT = 670

hide_streamlit_style = """
<style>
div[data-testid="stToolbar"] {
visibility: hidden;
height: 0%;
position: fixed;
}
div[data-testid="stDecoration"] {
visibility: hidden;
height: 0%;
position: fixed;
}
div[data-testid="stStatusWidget"] {
visibility: hidden;
height: 0%;
position: fixed;
}
#MainMenu {
visibility: hidden;
height: 0%;
}
header {
visibility: hidden;
height: 0%;
}
footer {
visibility: hidden;
height: 0%;
}
</style>
"""
streamlit.markdown(hide_streamlit_style, unsafe_allow_html=True)


def modifySessionState(key, value) -> None:
    streamlit.session_state[key] = value


def run_container(instance_id) -> None:
    def execute(instance_id):
        data = utils.get_data_by_id(instance_id)
        os.system("docker image prune -f")

        if data["status"] == "starting":
            utils.create_docker_file(instance_id)
            process = subprocess.run(["docker", "build", "-t", instance_id.lower(), f"instances/{instance_id}"])
            run_command = [
                "docker",
                "run",
                "-d",
                f"--memory={data["ram"].replace(" ", "").replace("GB", "g").replace("MB", "m")}",
                f"--cpus={data["core"]}",
                "--name",
                f"container_{instance_id}",
                instance_id.lower(),
            ]

            if process.returncode == 0:

                run_proc = subprocess.run(run_command)

                data = utils.get_data_by_id(instance_id)
                data["status"] = "running" if run_proc.returncode == 0 else "stopped"
                data["uptime"] = repr(time.time())
                utils.write(instance_id, data)

            else:
                data = utils.get_data_by_id(instance_id)
                data["status"] = "stopped"
                utils.write(instance_id, data)

        elif data["status"] == "stopping":
            subprocess.run(["docker", "rm", "-f", "container_" + instance_id])
            data = utils.get_data_by_id(instance_id)
            data["status"] = "stopped"
            utils.write(instance_id, data)

    data = utils.get_data_by_id(instance_id)

    if data["status"] == "stopped":
        data["status"] = "starting"
        utils.write(instance_id, data)

    if data["status"] == "running":
        data = utils.get_data_by_id(instance_id)
        data["status"] = "stopping"
        utils.write(instance_id, data)

    threading.Thread(target=execute, args=(instance_id,)).start()


def execute_the_first_time() -> None:
    client_data = utils.load_instances()
    print("Executing the first time startup")

    for data in client_data:
        if data["status"] != "running":
            continue

        data["status"] = "stopped"
        utils.write(data["instance_id"], data)
        run_container(data["instance_id"])


def instance_stats(instance_id) -> dict:
    result = subprocess.run(
        [
            "docker",
            "stats",
            "container_" + instance_id,
            "--no-stream",
            "--format",
            "{{.Container}},{{.CPUPerc}},{{.MemUsage}},{{.NetIO}},{{.BlockIO}},{{.PIDs}}",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    if result.returncode == 0:
        result = result.stdout.split(",")
        result = {
            "container": result[0],
            "cpu_percent": result[1],
            "memory_usage": result[2],
            "net_io": result[3],
            "block_io": result[4],
            "pids": result[5],
        }

    else:
        result = None

    return result


instances = load_instances()
current_page = streamlit.query_params.get("page", "dashboard")
current_instance_id = streamlit.query_params.get("instance_id")
current_view = streamlit.query_params.get("view", "usage")
current_filename = streamlit.query_params.get("filename")
current_directory = streamlit.query_params.get("dir", "/")

status = {"stopped": "🔴 Stopped", "starting": "🟡 Starting", "running": "🟢 Running", "stopping": "🟡 Stopping"}

if os.path.exists("./first_time"):
    os.remove("first_time")
    execute_the_first_time()

if current_page == "login":
    l, m, r = streamlit.columns([2, 4, 2])

    with m.form(border=True, key="Login Page"):
        streamlit.write(
            f"""
            <div style="text-align: center; font-size: 22px; font-weight: bold; color: #FFFFFF; margin-top: 5px;">
                Please Login before heading to the Dashboard
            </div>
            """,
            unsafe_allow_html=True,
        )
        streamlit.divider()

        user_input = streamlit.text_input("Username")
        password_input = streamlit.text_input("Password", type="password")
        submit_button = streamlit.form_submit_button("Submit", use_container_width=True)

        if submit_button:
            username, password = os.getenv("USERNAME"), os.getenv("PASSWORD")

            if (username, password) == (user_input, password_input):
                streamlit.session_state["isLogged"] = True
                streamlit.query_params["page"] = "dashboard"
                streamlit.rerun()

            else:
                streamlit.error("Credintials error")

if current_page == "dashboard":
    if not streamlit.session_state.get("isLogged", False):
        streamlit.query_params["page"] = "login"
        streamlit.rerun()

    st_autorefresh(1000)
    # streamlit.warning(
    #     "**Notice**: This dashboard runs on GitHub Actions. "
    #     "Every ~5 hours, the system undergoes a brief maintenance where all instances may temporarily shut down. "
    #     "They'll automatically recover a few minutes later.",
    #     icon="⚠️",
    # )
    left, right = streamlit.columns([5, 2])

    with right, streamlit.container(border=True, height=INITIAL_HEIGHT):
        streamlit.subheader("🚀 Create New Instance")

        name = streamlit.text_input("Instance Name", max_chars=22)
        ram = streamlit.selectbox("RAM", ["512 MB", "1 GB", "2 GB", "4 GB", "8 GB"])
        cores = streamlit.selectbox("CPU Cores", [1, 2, 4])

        streamlit.divider()
        streamlit.write("Credintials below will be used to access the instance dashboard")

        username_input = streamlit.text_input("Username")
        password_input = streamlit.text_input("Password", type="password")

        create = streamlit.button(
            "Create",
            key="create_instance_btn",
            use_container_width=True,
            on_click=partial(create_instances, name, ram, cores, username_input, password_input),
            disabled=(not name) or name in [instance["instance_name"] for instance in instances],
        )

    if instances:
        with left, streamlit.container(border=True, height=INITIAL_HEIGHT):
            for _ in range(0, len(instances), 2):
                columns = streamlit.columns(2)

                for column, instance in zip(columns, instances[_ : _ + 2]):

                    with column, streamlit.container(border=True):

                        streamlit.write(
                            f"""
                            <div style="text-align: center; font-size: 22px; font-weight: bold; color: #2C8EFF; margin-top: 5px;">
                                🚀 {instance["instance_name"]}
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        streamlit.divider()
                        info_block = f"""
                        🆔 Instance ID : {instance['instance_id']}
                        🟡 Status      : {status[instance["status"]]}
                        🧠 RAM         : {instance['ram']}
                        ⚙️ Core        : {instance['core']}
                        ⏱️ Uptime      : {utils.format_time(int(time.time() - float(instance['uptime']))) if status == '🟢 Running' else 'N/A'}
                        """

                        streamlit.code(info_block, language="json")

                        viewButton = streamlit.button(
                            "View",
                            key=secrets.token_urlsafe(12),
                            use_container_width=True,
                            on_click=partial(
                                streamlit.query_params.update,
                                {
                                    "page": "instance",
                                    "instance_id": instance["instance_id"],
                                    "view": "file",
                                },
                            ),
                        )

                        runButton = streamlit.button(
                            "Run" if instance["status"] == "stopped" else "Stop",
                            key=secrets.token_urlsafe(12),
                            use_container_width=True,
                            disabled=(instance["status"] in ["starting", "stopping"])
                            or (not instance["instance_config"]["docker_image"] or not instance["instance_config"]["run_command"]),
                            on_click=partial(run_container, instance["instance_id"]),
                        )

    else:
        with left, streamlit.container(border=True, height=INITIAL_HEIGHT):
            streamlit.markdown("## 👋 Welcome to the Dashboard!")
            streamlit.markdown(
                "This app helps you manage isolated Python environments (we call them **Instances**) that can run independently with real-time log viewing and file browsing."
            )

            streamlit.divider()

            streamlit.subheader("🆕 How to Create Your First Instance")
            streamlit.markdown(
                """
            1. **Head over to the right panel** labeled “🚀 Create New Instance”.
            2. Fill out:
            - 🏷️ *Instance Name* – like `my-test-bot`
            - 🧠 *RAM* – how much memory to give
            - 🖥️ *CPU Cores* – how much processing power
            - 📦 *Upload Files* (Optional)
            3. Hit **Create** – it will appear on the left listreamlit.
            4. Click **View** to open it and see logs, files, and actions.
            """
            )

            streamlit.divider()

            streamlit.subheader("⚠️ Note on System Behavior")
            streamlit.markdown(
                """
            > This app runs inside **GitHub Actions**.
            >
            > That means:
            - 🕒 Every ~5 hours it restarts.
            - 🔁 Your instances may briefly go offline.
            - ✅ They’ll recover automatically within a few minutes.
            """
            )

if current_page == "instance" and current_instance_id:
    instance_data = utils.get_data_by_id(current_instance_id)

    if not instance_data:
        streamlit.error("Instance ID not found")

    if (not streamlit.session_state.get("logged_" + current_instance_id, False)) and (
        instance_data["instance_user"] and instance_data["instance_password"]
    ):
        l, m, r = streamlit.columns([2, 4, 2])
        user, passwd = instance_data["instance_user"], instance_data["instance_password"]

        with m.form("Instance Login"):
            streamlit.write("Please login with the credintials you have entered during the creation of this instance")
            streamlit.divider()

            user_input = streamlit.text_input("Username")
            password_input = streamlit.text_input("Password", type="password")

            if streamlit.form_submit_button(use_container_width=True):
                if (user, passwd) == (user_input, password_input):
                    streamlit.session_state["logged_" + current_instance_id] = True
                    streamlit.rerun()

                else:
                    streamlit.error("Wrong credintials")

    else:

        left, right = streamlit.columns([2, 5])

        with left:

            def set_instance_view(view_name):
                streamlit.query_params["view"] = view_name

                for data in streamlit.session_state.keys():
                    if not data.startswith("logged_"):
                        del streamlit.session_state[data]

                if view_name != "view_file" and "filename" in streamlit.query_params:
                    del streamlit.query_params["filename"]

                if "dir" in streamlit.query_params:
                    if view_name != "file":
                        del streamlit.query_params["dir"]

                    elif "dir" != "/" and view_name == "file":
                        streamlit.query_params["dir"] = "/" + "/".join(streamlit.query_params["dir"][:-1][1:].split("/")[:-1])

            with streamlit.container(border=True):
                usageButton = streamlit.button(
                    "📊 Usage",
                    use_container_width=True,
                    on_click=partial(set_instance_view, "usage"),
                    disabled=utils.get_data_by_id(current_instance_id)["status"] == "stopped",
                )
                terminalButton = streamlit.button(
                    "📟 Terminal and Logs",
                    use_container_width=True,
                    on_click=partial(set_instance_view, "terminal"),
                    # disabled=utils.get_data_by_id(current_instance_id)["status"] == "stopped",
                )
                fileStorageButton = streamlit.button(
                    "📁 File Manager",
                    use_container_width=True,
                    on_click=partial(set_instance_view, "file"),
                )
                settingsButton = streamlit.button(
                    "⚙️ Settings",
                    use_container_width=True,
                    on_click=partial(set_instance_view, "settings"),
                )

            def go_to_dashboard():
                streamlit.query_params.clear()
                streamlit.query_params["page"] = "dashboard"

            backButton = streamlit.button(
                "Back to Dashboard",
                use_container_width=True,
                on_click=go_to_dashboard,
            )

        if current_view == "usage":
            st_autorefresh(3500)

        elif current_view == "terminal":
            st_autorefresh(interval=500, key=f"log_refresher_{current_instance_id}")

        with right, streamlit.container(border=True, height=INITIAL_HEIGHT):
            if current_view == "usage":

                left, mid, right = streamlit.columns([2, 2, 2])
                result = instance_stats(current_instance_id)

                if result is not None:
                    left.metric("CPU Usage", result["cpu_percent"], border=True)
                    mid.metric("Memory Usage", result["memory_usage"], border=True)
                    right.metric("Net I/O", result["net_io"], border=True)

            elif current_view == "terminal":
                container_name = f"container_{current_instance_id}"
                log_command = ["docker", "logs", "--tail", "100", container_name]
                vmStatus = utils.get_data_by_id(current_instance_id)["status"]

                result = subprocess.run(
                    log_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    check=False,
                    timeout=10,
                )

                status_color = "d41e1e" if vmStatus == "stopped" else ("fbff00" if vmStatus in ["starting", "stopping"] else "00ff1a")
                vmStatus = "Not Running" if vmStatus == "stopped" else ("Starting" if vmStatus == "starting" else vmStatus.title())

                streamlit.write(
                    f"""
                <div style="text-align: center; font-size: 22px; font-weight: bold; color: #{status_color}; margin-top: 5px;">
                    {vmStatus.title()}
                </div>
                """,
                    unsafe_allow_html=True,
                )
                streamlit.divider()

                with streamlit.container(height=450, border=False):
                    terminal_l = 22
                    spacing_count = terminal_l - (std_len := len(result.stdout.splitlines()) - 2)

                    if vmStatus == "Running" and result.returncode == 0:
                        # streamlit.code(result.stdout + ("\n \u200b" * spacing_count if std_len < 20 else ""), language="bash", line_numbers=False)

                        html_code = f"""
                        <style>
                        /* Hide scrollbar for Chrome/Safari */
                        #terminal::-webkit-scrollbar {{
                            display: none;
                        }}
                        /* Hide scrollbar for Firefox/Edge */
                        #terminal {{
                            scrollbar-width: none;
                            -ms-overflow-style: none;
                        }}
                        </style>

                        <div id="terminal" style="
                            max-height: 490px;
                            overflow-y: auto;
                            background-color: var(--secondary-background-color, #0e1117);
                            color: var(--text-color, #dcdcdc);
                            padding: 1rem;
                            font-family: 'Source Code Pro', Menlo, Monaco, Consolas, monospace;
                            font-size: 0.875rem;
                            line-height: 1.4;
                            border-radius: 0.5rem;
                            white-space: pre-wrap;
                            word-wrap: break-word;
                        ">
                            <pre>{result.stdout + ("\n \u200b" * spacing_count if std_len < terminal_l else "")}</pre>
                        </div>

                        <script>
                            var term = document.getElementById("terminal");
                            term.scrollTop = term.scrollHeight;
                        </script>
                        """

                        components.html(html_code, height=470, scrolling=False)

                runButton = streamlit.button(
                    "Run Instance" if vmStatus in ["Not Running", "Starting"] else "Stop Instance",
                    use_container_width=True,
                    disabled=(vmStatus == "Starting"),
                    on_click=partial(run_container, current_instance_id),
                )

            elif current_view == "settings":
                left, right = streamlit.columns([2, 2])

                with left:
                    with streamlit.container(border=True):
                        streamlit.subheader("🧩 Install Command")

                        streamlit.markdown(
                            """This command runs *once* when the instance is first created.
                            It's usually used to install dependencies or setup tools.
                            **Example:**"""
                        )

                        streamlit.code("python3 -m pip install -r requirements.txt")
                        streamlit.divider()

                        install_command_input = streamlit.text_input(
                            "Install Command (Optional)", instance_data["instance_config"]["install_command"]
                        )
                        instance_data["instance_config"]["install_command"] = install_command_input
                        utils.write(current_instance_id, instance_data)

                with right:
                    with streamlit.container(border=True):
                        streamlit.subheader("🚀 Run Command")

                        streamlit.markdown(
                            """This command keeps your instance running.
                                It's the main script or process you want to execute.
                                **Example:**  """
                        )

                        streamlit.code("python3 app.py")
                        streamlit.divider()

                        if run_command_input := streamlit.text_input("Run Command", value=instance_data["instance_config"]["run_command"]):
                            instance_data["instance_config"]["run_command"] = run_command_input
                            utils.write(current_instance_id, instance_data)

                left2, right2 = streamlit.columns([2, 2], gap="large")

                with left2:
                    streamlit.subheader("🐋 Docker Image")

                    streamlit.markdown(
                        "A Docker image is a pre-packaged environment that includes everything your app needs to run—like the operating system, language runtime, and dependencies. When you choose an image, you're picking the foundation for your instance. For example, selecting a Python image gives you an environment with Python already set up. Make sure to pick one that fits the language or tools your app needs. "
                        + ("" if not (image := instance_data["instance_config"]["docker_image"]) else f"**Current image:** `{image}`")
                    )

                with right2:
                    docker_image_input = streamlit.text_input("Docker Image")
                    check_image_btn = streamlit.button("Check Image", use_container_width=True, disabled=(not docker_image_input))

                    if check_image_btn:
                        streamlit.session_state["docker_image"] = fetch_docker_image(docker_image_input)

                        if not (data := streamlit.session_state["docker_image"]):
                            streamlit.error('No repository found with the name "{}"'.format(docker_image_input))

                        else:
                            tag_list = requests.get(
                                f"https://registry.hub.docker.com/v2/repositories/library/{docker_image_input}/tags?page_size=10"
                            )
                            streamlit.session_state["tag_list"] = tag_list.json()["results"]
                            streamlit.rerun()

            if data := streamlit.session_state.get("docker_image", []):
                streamlit.divider()

                left, right = streamlit.columns([2, 2])
                data = data[0]

                with left, streamlit.container(border=True):

                    streamlit.subheader(f"📦 {data['repo_name']}")
                    streamlit.markdown(
                        f"""
                        {data.get("short_description", "No description")}\n
                        **Official**: {'✅' if data.get('is_official') else '❌'} |
                        **Stars**: ⭐ {data.get('star_count', 0)}
                        """
                    )

                with right, streamlit.container(border=True):
                    streamlit.subheader("🏷️ Available Tags")

                    tag_selector = streamlit.selectbox(
                        "Available Tags",
                        label_visibility="collapsed",
                        options=[tag["name"] for tag in streamlit.session_state["tag_list"]],
                    )

                    def change_docker_data() -> None:
                        instance_data["instance_config"]["docker_image"] = data["repo_name"] + ":" + tag_selector
                        utils.write(current_instance_id, instance_data)

                    streamlit.button(
                        "Use this Tag",
                        use_container_width=True,
                        on_click=lambda: (
                            partial(modifySessionState, "docker_image", [])(),
                            partial(modifySessionState, "tag_list", None)(),
                            change_docker_data(),
                        ),
                    )

            elif current_view == "file" and current_instance_id:
                # ROOT_DIR = r"C:\Users\user\OneDrive\Documents\Python\Netter Remake"
                ROOT_DIR = os.path.join(utils.INSTANCE_DIR, current_instance_id, "workspace")
                files = [
                    (f"📃 " if os.path.isfile(os.path.join(ROOT_DIR, *current_directory.split("/"), file_name)) else f"📂 ") + file_name
                    for file_name in os.listdir(os.path.join(ROOT_DIR, *current_directory.split("/")))
                ]

                files = sorted(files, key=lambda x: x.startswith("📃"))

                if current_filename:
                    try:
                        f_path = os.path.join("instances", current_instance_id, "workspace", *current_directory.split("/"), current_filename)
                        file_content = open(f_path)
                        l, r = streamlit.columns([2, 2])

                        streamlit.text_input("File name", value=current_filename)
                        save_content_btn = streamlit.button("Save Content", use_container_width=True)

                        streamlit.divider()
                        content = streamlit.text_area("Code", file_content.read(), label_visibility="collapsed", height=400)

                        if save_content_btn:
                            open(f_path, "w").write(content)
                            del streamlit.query_params["filename"]
                            streamlit.rerun()

                    except UnicodeDecodeError:
                        del streamlit.query_params["filename"]
                        streamlit.rerun()

                else:
                    file_uploader = streamlit.file_uploader(
                        "Upload files",
                        accept_multiple_files=True,
                        key=streamlit.session_state.get("file_uploader_key", 1),
                    )

                    l, m, r = streamlit.columns([4, 2, 2])

                    with l:
                        path = os.path.join(ROOT_DIR, *current_directory.split("/"))
                        file_name_input = streamlit.text_input("Upload File", label_visibility="collapsed")
                        button_disabled = (
                            (not file_name_input) or file_name_input in [name for name in os.listdir(path)] or "/" in file_name_input
                        )

                    with m:
                        create_dir_btn = streamlit.button(
                            "Create Directory",
                            use_container_width=True,
                            disabled=button_disabled,
                            on_click=lambda: os.mkdir(os.path.join(path, file_name_input)),
                        )

                    with r:
                        streamlit.button(
                            "Create File",
                            use_container_width=True,
                            disabled=button_disabled,
                            on_click=lambda: open(os.path.join(path, file_name_input), "w"),
                        )

                    streamlit.divider()

                    if file_uploader:
                        for file in file_uploader:
                            file_path = os.path.join("instances", current_instance_id, "workspace", *current_directory.split("/"), file.name)

                            with open(file_path, "wb") as f:
                                f.write(file.read())

                            if file.name.endswith(".zip"):
                                os.system("unzip " + file_path + " -d " + "instances/" + current_instance_id + "/workspace/")

                        if streamlit.session_state.get("file_uploader_key", None) is None:
                            streamlit.session_state["file_uploader_key"] = 1
                        else:
                            streamlit.session_state["file_uploader_key"] += 1

                        streamlit.rerun()

                    streamlit.write("Current directory: `{}`".format(current_directory))

                    for file in files:
                        left, right = streamlit.columns([7, 1])
                        file_path = os.path.join(ROOT_DIR, file[2:])

                        with left:

                            def set_filename(value) -> None:
                                if os.path.isdir(
                                    os.path.join("instances", current_instance_id, "workspace", *current_directory.split("/"), value)
                                ):
                                    streamlit.query_params["dir"] = current_directory + value + "/"
                                    return

                                streamlit.query_params["filename"] = value

                            streamlit.button(
                                file,
                                key=secrets.token_urlsafe(10),
                                use_container_width=True,
                                on_click=partial(set_filename, file[2:]),
                            )

                        with right:
                            path = os.path.join("instances", current_instance_id, "workspace", *current_directory.split("/"), file[2:])

                            streamlit.button(
                                "Delete",
                                key=secrets.token_urlsafe(10),
                                use_container_width=True,
                                on_click=partial(shutil.rmtree, path),
                            )
