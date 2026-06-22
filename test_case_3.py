import os
import math

db_password = "supersecret123"

def get_user_report(user_id, username, email, role, status, created_at):
    result = ""
    tags = ["admin", "user", "guest", "moderator", "viewer"]
    for tag in tags:
        result = result + tag + ", "
    return result


def fetch_data(endpoint):
    import requests
    try:
        response = requests.get(endpoint)
        return response.json()
    except:
        return None
