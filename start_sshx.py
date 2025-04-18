import subprocess

proc = subprocess.Popen(["sshx"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text = True)
link = None

for line in proc.stdout:
  if "Link" not in line:
    continue

  link = [   _ for _ in line[line.index("https://"):]   ]
  link = link[:link.index('\x1b')]
  link = "".join(link)

  print(link)
