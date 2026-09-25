from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'siri_ya_telapp_2026'
socketio = SocketIO(app, cors_allowed_origins="*")

messages_db = []
pinned_topic = {"topic": "Bado haijawekwa", "leader": "Hakuna"}
leader_user = None

@app.route('/')
def index():
    return render_template('chart.html')

@socketio.on('join')
def handle_join(data):
    global leader_user
    username = data.get('username')
    
    if leader_user is None:
        leader_user = username

    is_leader = (username == leader_user)
    
    emit('init_data', {
        'pinned_topic': pinned_topic,
        'is_leader': is_leader,
        'history': messages_db
    })
    
    emit('notification', {'message': f'{username} amejiunga na mazungumzo.'}, broadcast=True, include_self=False)

@socketio.on('send_message')
def handle_message(data):
    msg_id = str(uuid.uuid4())[:8]
    new_msg = {
        'id': msg_id,
        'username': data.get('username'),
        'message': data.get('message'),
        'tag': data.get('tag', 'Ujumbe'),
        'time': data.get('time', '')
    }
    
    # Hifadhi kwenye kumbukumbu
    messages_db.append(new_msg)
    
    # Tuma kwa kila mtu (pamoja na aliyetuma) ili kuonekana kwenye skrini
    emit('chat_message', new_msg, broadcast=True)

@socketio.on('delete_message')
def handle_delete_message(data):
    global messages_db
    msg_id = data.get('id')
    username = data.get('username')
    
    target_msg = next((m for m in messages_db if m['id'] == msg_id), None)
    
    if target_msg:
        if target_msg['username'] == username or username == leader_user:
            messages_db = [m for m in messages_db if m['id'] != msg_id]
            emit('remove_message', {'id': msg_id}, broadcast=True)
        else:
            emit('alert_notification', {'message': 'Huwezi kufuta ujumbe wa mtu mwingine!'})

@socketio.on('set_topic')
def handle_set_topic(data):
    global pinned_topic
    topic = data.get('topic')
    username = data.get('username')
    
    if username == leader_user:
        pinned_topic = {'topic': topic, 'leader': username}
        emit('update_topic', pinned_topic, broadcast=True)
    else:
        emit('alert_notification', {'message': 'Wewe si kiongozi, huwezi kubadilisha mada!'})

if __name__ == '__main__':
  socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)