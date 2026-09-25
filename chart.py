from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import time
import uuid
import os

app = Flask(__name__, template_folder='.')
app.config['SECRET_KEY'] = 'siri_nzito_sana'

# Tunaruhusu cors="*" ili browser/vifaa kutoka mtandao wowote viweze kuunganishwa
socketio = SocketIO(app, cors_allowed_origins="*")

# Hifadhi za muda (In-memory storage)
users = {}          # Hifadhi taarifa za watumiaji: sid -> {'username': jina, 'last_active': muda}
messages = []       # Hifadhi historia ya meseji
group_leader = None # Kiongozi wa kundi

# Mipangilio ya Kiotomatiki
INACTIVITY_LIMIT = 60  # Sekunde 60 za ukimya kabla ya kupewa Alert
TOPIC_DURATION = 120   # Sekunde 120 (Dakika 2) kabla mada haijafutwa yenyewe
pinned_topic = {
    "topic": "Karibu kwenye TelCom Worldwide!", 
    "leader": "System", 
    "expires_at": time.time() + 3600
}

@app.route('/')
def index():
    return render_template('tel2.html')

@socketio.on('join')
def handle_join(data):
    global group_leader
    username = data.get('username', 'Mgeni')
    sid = request.sid
    
    # Sajili mtumiaji na mwekee muda wake wa sasa
    users[sid] = {'username': username, 'last_active': time.time()}
    
    # Mtu wa kwanza kuingia anakuwa kiongozi (Leader)
    if not group_leader:
        group_leader = sid

    is_leader = (sid == group_leader)

    # Mtumie data za awali mtumiaji aliyeingia
    emit('init_data', {
        'history': messages[-50:], # Mpe meseji 50 za mwisho
        'pinned_topic': pinned_topic,
        'is_leader': is_leader
    })
    
    # Wajulishe wengine wote mtandaoni kuwa huyu amejiunga
    emit('notification', {'message': f'{username} amejiunga na kundi.'}, broadcast=True)

@socketio.on('send_message')
def handle_message(data):
    sid = request.sid
    if sid in users:
        users[sid]['last_active'] = time.time()

    msg = {
        'id': str(uuid.uuid4()),
        'username': data['username'],
        'message': data['message'],
        'tag': data.get('tag', 'Ujumbe'),
        'time': data.get('time')
    }
    messages.append(msg)
    # Tuma meseji kwa vifaa vyote duniani vilivyojiunga
    emit('chat_message', msg, broadcast=True)

@socketio.on('set_topic')
def handle_set_topic(data):
    global pinned_topic
    pinned_topic = {
        'topic': data['topic'],
        'leader': data['username'],
        'expires_at': time.time() + TOPIC_DURATION
    }
    emit('update_topic', {'topic': pinned_topic['topic'], 'leader': pinned_topic['leader']}, broadcast=True)

@socketio.on('delete_message')
def handle_delete(data):
    global messages
    msg_id = data['id']
    messages = [m for m in messages if m.get('id') != msg_id]
    emit('remove_message', {'id': msg_id}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    global group_leader
    sid = request.sid
    if sid in users:
        username = users[sid]['username']
        del users[sid]
        emit('notification', {'message': f'{username} ametoka kwenye kundi.'}, broadcast=True)
        
        if sid == group_leader:
            group_leader = list(users.keys())[0] if users else None

# === BACKGROUND TASK YAKUFANYA KAZI KIOTOMATIKI ===
def background_monitor():
    global pinned_topic
    while True:
        socketio.sleep(10)
        current_time = time.time()

        # 1. Angalia kama Mada imeisha muda wake
        if pinned_topic.get('expires_at') and current_time > pinned_topic['expires_at']:
            pinned_topic['topic'] = "Hakuna mada inayojadiliwa kwa sasa."
            pinned_topic['leader'] = "System"
            pinned_topic['expires_at'] = None
            socketio.emit('update_topic', {'topic': pinned_topic['topic'], 'leader': pinned_topic['leader']})

        # 2. Angalia wanachama walio kimya
        for sid, user_data in list(users.items()):
            if current_time - user_data['last_active'] > INACTIVITY_LIMIT:
                socketio.emit('alert_notification', {
                    'message': f"Halo {user_data['username']}, umekuwa kimya sana! Tafadhali changia hoja kwenye mada inayojadiliwa."
                }, to=sid)
                user_data['last_active'] = current_time

if __name__ == "__main__":
    socketio.start_background_task(background_monitor)
    
    # Soma PORT kutoka kwenye server ya cloud (default 5000)
    port = int(os.environ.get("PORT", 5000))
    print(f"Server ya TelCom imeanza kwenye Port {port}")
    
    # host='0.0.0.0' inaruhusu mawasiliano ya mtandao wa nje (Worldwide)
    socketio.run(app, host="0.0.0.0", port=port, debug=False)