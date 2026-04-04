from flask import Flask, request, jsonify
import json
import os

app = Flask(__name__)

USERS_FILE = os.path.join(os.path.dirname(__file__), 'users.json')

def load_users():
    with open(USERS_FILE, 'r') as f:
        return json.load(f)['users']

@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"error": "Missing username or password"}), 400
    
    username = data['username']
    password = data['password']
    
    users = load_users()
    for user in users:
        if user['username'] == username and user['password'] == password:
            return jsonify({
                "status": "success",
                "message": "Login successful",
                "user": {
                    "username": user['username'],
                    "role": user['role']
                }
            }), 200
            
    return jsonify({"status": "error", "message": "Invalid credentials"}), 401

@app.route('/auth/users/<username>', methods=['GET'])
def get_user(username):
    users = load_users()
    for user in users:
        if user['username'] == username:
            return jsonify({
                "username": user['username'],
                "role": user['role']
            }), 200
    return jsonify({"error": "User not found"}), 404

if __name__ == '__main__':
    # Listen on all interfaces, port 5001
    app.run(host='0.0.0.0', port=5001)
