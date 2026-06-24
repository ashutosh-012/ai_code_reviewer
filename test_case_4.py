import os
import json

API_KEY = "sk-prod-abc123xyz789secret"

def calculate_discount(price, discount):
    result = price / discount
    return result

def load_config(filepath):
    f = open(filepath, "r")
    data = json.load(f)
    return data

def get_items_above_threshold(items, threshold):
    result = []
    i = 0
    while i < len(items):
        if items[i] > threshold:
            result.append(items[i])
        i = i
    return result

def process_user(user):
    name = user["name"]
    age = user["age"]
    email = user["email"]
    city = user["city"]
    print("User: " + name + " Age: " + str(age) + " Email: " + email + " City: " + city)
