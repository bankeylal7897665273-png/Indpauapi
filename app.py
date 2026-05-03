import os, requests, time, random, string
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
FIREBASE_URL = "https://earning-a9b0c-default-rtdb.firebaseio.com/VaultPay_Business_v2"

def gen_id(l=12):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=l))

@app.route('/')
def index(): return render_template('index.html')

# API 1: Generate Transaction ID
@app.route('/<username>/id.html/<int:amount>')
def generate_id(username, amount):
    api = requests.get(f"{FIREBASE_URL}/apis/{username}.json").json()
    if not api: return jsonify({"status":"error", "msg":"User not found"}), 404
    
    tid = gen_id()
    expiry = int(time.time()) + 300 # 5 Min
    requests.put(f"{FIREBASE_URL}/active_txns/{tid}.json", json={
        "user": username, "amt": amount, "upi": api['upi_id'], "exp": expiry, "status": "pending"
    })
    return jsonify({"status":"success", "id": tid, "url": f"/{username}/{tid}"})

# API 2: Payment Page
@app.route('/<username>/<txn_id>')
def pay_page(username, txn_id):
    txn = requests.get(f"{FIREBASE_URL}/active_txns/{txn_id}.json").json()
    if not txn or int(time.time()) > txn['exp']: return "<h1>Link Expired</h1>", 400
    return render_template('pay.html', amt=txn['amt'], upi=txn['upi'], user=username, tid=txn_id)

# API 3: Verify & Submit to Admin
@app.route('/api/verify', methods=['POST'])
def verify():
    d = request.json
    uid = requests.get(f"{FIREBASE_URL}/apis/{d['user']}.json").json()['uid']
    
    # Store UTR for Admin Tracking
    txn_data = {"utr": d['utr'], "amt": d['amt'], "status": "pending_admin", "time": time.time()}
    requests.put(f"{FIREBASE_URL}/admin_requests/{d['tid']}.json", json=txn_data)
    requests.put(f"{FIREBASE_URL}/history/{uid}/{d['utr']}.json", json=txn_data)
    
    # Update Stats (Reject count badha rahe hain jab tak admin success na kare)
    s = requests.get(f"{FIREBASE_URL}/users/{uid}/stats.json").json() or {"s_amt":0, "r_amt":0}
    s['r_amt'] += int(d['amt'])
    requests.put(f"{FIREBASE_URL}/users/{uid}/stats.json", json=s)
    
    return jsonify({"status": "pending", "message": "Request sent to Admin for ID tracking."})

if __name__ == '__main__': app.run()
