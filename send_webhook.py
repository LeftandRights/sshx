import requests
import json
import os

webhook_url = os.getenv("DISCORD_WEBHOOK")

data = {
    "content": "A new Workflow just created",
    "username": "WebhookBot",
}

response = requests.post(webhook_url, data=json.dumps(data), headers={"Content-Type": "application/json"})

if response.status_code == 204:
    print("Message sent successfully!")
else:
    print(f"Failed to send message: {response.status_code}")
