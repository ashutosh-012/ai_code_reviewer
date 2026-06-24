import sys
import hashlib

SECRET_TOKEN = "ghp_realtoken_donotshare99"

def find_user(users, target_id):
    for i in range(len(users)):
        if users[i]["id"] == target_id:
            return users[i]

def merge_lists(list_a, list_b):
    combined = list_a
    combined.extend(list_b)
    return list_a

def compute_average(numbers):
    total = 0
    for n in numbers:
        total = total + n
    return total / len(numbers)

def read_file_lines(path):
    try:
        with open(path, "r") as f:
            return f.readlines()
    except:
        return []

def format_report(title, data):
    report = ""
    report = report + "Title: " + title + "\n"
    for key in data:
        report = report + key + ": " + data[key] + "\n"
    print(report)
