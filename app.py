import sqlite3
from flask import Flask, render_template, request, jsonify, g

app = Flask(__name__)
DATABASE = 'database.sqlite'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT CHECK(type IN ('Lost', 'Found')),
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            venue TEXT NOT NULL,
            description TEXT,
            finderName TEXT NOT NULL,
            finderRegNo TEXT NOT NULL,
            finderEmail TEXT,
            finderPhone TEXT,
            challenge TEXT NOT NULL,
            status TEXT DEFAULT 'Active'
        )''')
        db.execute('''CREATE TABLE IF NOT EXISTS claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            itemId INTEGER,
            claimantName TEXT NOT NULL,
            claimantRegNo TEXT NOT NULL,
            answer TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            FOREIGN KEY(itemId) REFERENCES items(id)
        )''')
        db.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            itemId INTEGER,
            sender TEXT NOT NULL,
            text TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(itemId) REFERENCES items(id)
        )''')
        db.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/items', methods=['GET'])
def get_items():
    db = get_db()
    item_type = request.args.get('type')
    category = request.args.get('category')
    venue = request.args.get('venue')

    query = "SELECT id, type, title, category, venue, description, challenge, status, finderName FROM items WHERE status != 'Resolved'"
    params = []

    if item_type and item_type != 'All':
        query += " AND type = ?"
        params.append(item_type)
    if category:
        query += " AND category = ?"
        params.append(category)
    if venue:
        query += " AND venue = ?"
        params.append(venue)

    query += " ORDER BY id DESC"
    cur = db.execute(query, params)
    items = [dict(row) for row in cur.fetchall()]
    return jsonify(items)

@app.route('/api/items', methods=['POST'])
def create_item():
    data = request.json
    required = ['type', 'title', 'category', 'venue', 'finderName', 'finderRegNo', 'challenge']
    if not all(data.get(k) for k in required):
        return jsonify({'error': 'Missing required fields'}), 400

    db = get_db()
    cur = db.execute(
        '''INSERT INTO items (type, title, category, venue, description, finderName, finderRegNo, finderEmail, finderPhone, challenge)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (
            data['type'], data['title'], data['category'], data['venue'],
            data.get('description', ''), data['finderName'], data['finderRegNo'],
            data.get('finderEmail', ''), data.get('finderPhone', ''), data['challenge']
        )
    )
    db.commit()
    return jsonify({'id': cur.lastid, 'message': 'Item reported successfully!'}), 201

@app.route('/api/items/<int:item_id>/resolve', methods=['POST'])
def resolve_item(item_id):
    db = get_db()
    db.execute("UPDATE items SET status = 'Resolved' WHERE id = ?", (item_id,))
    db.commit()
    return jsonify({'message': 'Item marked as resolved!'})

@app.route('/api/claims', methods=['POST'])
def submit_claim():
    data = request.json
    if not all(data.get(k) for k in ['itemId', 'claimantName', 'claimantRegNo', 'answer']):
        return jsonify({'error': 'Missing claim fields'}), 400

    db = get_db()
    db.execute(
        'INSERT INTO claims (itemId, claimantName, claimantRegNo, answer) VALUES (?, ?, ?, ?)',
        (data['itemId'], data['claimantName'], data['claimantRegNo'], data['answer'])
    )
    db.commit()
    return jsonify({'message': 'Claim verification request submitted!'}), 201

@app.route('/api/items/<int:item_id>/claims', methods=['GET'])
def get_claims(item_id):
    db = get_db()
    cur = db.execute('SELECT * FROM claims WHERE itemId = ?', (item_id,))
    claims = [dict(row) for row in cur.fetchall()]
    return jsonify(claims)

@app.route('/api/claims/<int:claim_id>/status', methods=['POST'])
def update_claim_status(claim_id):
    data = request.json
    status = data.get('status')
    if status not in ['Approved', 'Rejected']:
        return jsonify({'error': 'Invalid status'}), 400

    db = get_db()
    db.execute('UPDATE claims SET status = ? WHERE id = ?', (status, claim_id))
    db.commit()
    return jsonify({'message': f'Claim {status}'})

@app.route('/api/items/<int:item_id>/messages', methods=['GET', 'POST'])
def handle_messages(item_id):
    db = get_db()
    if request.method == 'POST':
        data = request.json
        if not data.get('sender') or not data.get('text'):
            return jsonify({'error': 'Sender and text required'}), 400
        db.execute('INSERT INTO messages (itemId, sender, text) VALUES (?, ?, ?)', (item_id, data['sender'], data['text']))
        db.commit()
        return jsonify({'message': 'Message sent'})
    
    cur = db.execute('SELECT * FROM messages WHERE itemId = ? ORDER BY id ASC', (item_id,))
    messages = [dict(row) for row in cur.fetchall()]
    return jsonify(messages)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)