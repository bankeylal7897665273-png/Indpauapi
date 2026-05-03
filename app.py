import os, requests, time, random, string
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
FIREBASE_URL = "https://earning-a9b0c-default-rtdb.firebaseio.com/VaultPay_Business"

def gen_id(l=15):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=l))

@app.route('/')
def index(): 
    return render_template('index.html')

# 1. GENERATE ID URL
@app.route('/<username>/id.html/<int:amount>')
def generate_id(username, amount):
    api = requests.get(f"{FIREBASE_URL}/apis/{username}.json").json()
    if not api: return jsonify({"status":"error", "msg":"API Not Found"}), 404
    
    tid = gen_id()
    expiry = int(time.time()) + 300 # 5 Minute Timer
    
    # Save Transaction
    requests.put(f"{FIREBASE_URL}/active_txns/{tid}.json", json={
        "user": username, "amt": amount, "upi": api['upi_id'], 
        "exp": expiry, "status": "waiting"
    })
    return jsonify({"status":"success", "id": tid, "url": f"/{username}/{tid}"})

# 2. PAYMENT PAGE ROUTE
@app.route('/<username>/<txn_id>')
def pay_page(username, txn_id):
    txn = requests.get(f"{FIREBASE_URL}/active_txns/{txn_id}.json").json()
    if not txn or int(time.time()) > txn['exp']: 
        return "<h1>Link Expired or Invalid</h1>", 400
    
    return render_template('pay.html', amt=txn['amt'], upi=txn['upi'], user=username, tid=txn_id)

# 3. BACKGROUND AUTO-CHECKER (No UTR Box needed in UI)
@app.route('/api/check_status', methods=['POST'])
def check_status():
    d = request.json
    tid = d.get('txn_id')
    user = d.get('user')
    
    txn = requests.get(f"{FIREBASE_URL}/active_txns/{tid}.json").json()
    if not txn: return jsonify({"status": "error"}), 404
    
    current_time = int(time.time())
    
    # Check if 5 mins passed
    if current_time > txn['exp'] and txn['status'] == 'waiting':
        # Mark as Rejected
        requests.patch(f"{FIREBASE_URL}/active_txns/{tid}.json", json={"status": "rejected"})
        
        # Update Reject Stats
        uid = requests.get(f"{FIREBASE_URL}/apis/{user}.json").json()['uid']
        s = requests.get(f"{FIREBASE_URL}/users/{uid}/stats.json").json() or {"s_amt":0, "r_amt":0, "r_count":0, "s_count":0}
        s['r_amt'] += int(txn['amt'])
        s['r_count'] += 1
        requests.put(f"{FIREBASE_URL}/users/{uid}/stats.json", json=s)
        
        return jsonify({"status": "rejected", "message": "Time expired. Payment rejected."})

    # Note: Bina UTR ya Email ke auto-success verify karna namumkin hai Vercel par.
    # Asli payment detect karne ke liye aapko Firebase 'active_txns' node mein 
    # externally status 'success' karna padega (via SMS bot/admin). 
    # Yahan UI ke liye polling chal rahi hai:
    
    if txn['status'] == 'success':
        # Update Success Stats
        uid = requests.get(f"{FIREBASE_URL}/apis/{user}.json").json()['uid']
        s = requests.get(f"{FIREBASE_URL}/users/{uid}/stats.json").json() or {"s_amt":0, "r_amt":0, "r_count":0, "s_count":0}
        s['s_amt'] += int(txn['amt'])
        s['s_count'] += 1
        requests.put(f"{FIREBASE_URL}/users/{uid}/stats.json", json=s)
        return jsonify({"status": "success", "message": "Payment Received!"})
        
    return jsonify({"status": "waiting"})

if __name__ == '__main__': 
    app.run()
