import subprocess
from flask import redirect
from flask import Flask; app = Flask(
  __name__
)

proc = subprocess.Popen(["sshx"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text = True)
link = None

for line in proc.stdout:
  if "Link" not in line:
    continue

  link = [   _ for _ in line[line.index("https://"):]   ]
  link = link[:link.index('\x1b')]
  link = "".join(link)

  print("🔗 Captured SSHX Link:", link)
  break

@app.route("/")
def index() -> None:
  return redirect(link)

if __name__ == "__main__":
  app.run(host = "0.0.0.0", port = 5000)
