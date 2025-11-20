import os
import uuid
from datetime import datetime
from pickle import GLOBAL

from flask import Blueprint, flash
from flask import render_template, request, jsonify, session, redirect, url_for

from Code import GroupChat
from utils import Encryption_Manager, SQL_manager

chat_bp = Blueprint('chat', __name__)


def get_group_chat_messages(user_id,group_chat_id,username,sym_key):

    messages = GroupChat.get_group_chat_messages(user_id,group_chat_id,username,sym_key)

    return sorted(messages, key=lambda x: x['sent_at'])


def get_messages(friend):
    messages = []
    query = """
    SELECT ok.* 
    FROM onion_keys ok
    JOIN users u ON ok.user_id = u.user_id
    WHERE u.username = %s
    ORDER BY ok.last_updated DESC
    LIMIT 1
    """

    session['current_chat_data'] = SQL_manager.execute_query(
        query,
        params=(friend,),
        fetch=True
    )["results"][0]
    session['current_chat_data']['username'] = friend

    waiting_messages = SQL_manager.execute_query(
        "SELECT message,send_at FROM message WHERE receiver_id = %s AND sender_id = %s ORDER BY send_at DESC",
        params=(session["user_id"], session["current_chat_data"]["user_id"]), fetch=True)["results"]

    os.makedirs("Data/Chat_data/" + session["username"], exist_ok=True)
    with open("Data/Chat_data/" + session["username"] + "/" + session['current_chat_data']['username'], 'a') as f:
        for message in waiting_messages:
            f.write(message["send_at"].strftime("%I:%M%p on %B %d, %Y") + "\n" + friend + "\n" + str(
                clean_message(message["message"])) + "\n")

    SQL_manager.execute_query("DELETE FROM message WHERE receiver_id = %s AND sender_id = %s",
                              params=(session["user_id"], session["current_chat_data"]["user_id"]))

    with open("Data/Chat_data/" + session["username"] + "/" + session['current_chat_data']['username'], 'r') as f:
        lines = f.readlines()
        for i in range(0, len(lines), 3):
            if lines[i + 1].strip() == session["username"]:
                encrypted_message = lines[i + 2]
                message = Encryption_Manager.decrypt_message_with_symmetric_key(session["sym_key"], encrypted_message)
            else:
                message_line = lines[i + 2].strip()
                message = Encryption_Manager.decrypt_with_private_key(
                    Encryption_Manager.read_private_key(session["username"], session['sym_key']),
                    message_line[2:len(message_line) - 1])

            m = {
                "sent_at": lines[i].strip(),
                "sender": lines[i + 1].strip(),
                "message": message
            }
            messages.append(m)

    return messages


@chat_bp.route('/chat/<friend>', methods=['GET', 'POST'])
def chat(friend):

    if 'username' not in session:
        return redirect(url_for('index'))

    messages = get_messages(friend)

    return render_template('chat.html',
                           friend=friend,
                           messages=messages)


def clean_message(message):
    if message[0] == 'b':
        return message[2:len(message) - 2]
    return message


@chat_bp.route('/send-message', methods=['POST'])
def send_message():
    if 'username' not in session:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    print(session['current_chat_data'])

    # is_online = SQL_manager.execute_query("SELECT is_online FROM users WHERE user_id = %s", (session['current_chat_data']['user_id'],), fetch=True)["results"][0]
    request_message = request.form.get('message')
    encrypted_message = Encryption_Manager.encrypt_with_public_key_pem(session['current_chat_data']['public_key'],
                                                                       request_message)

    print("sending data to database")
    SQL_manager.execute_query("INSERT INTO message (sender_id, receiver_id, message) VALUES (%s,%s,%s)",
                              params=(session['user_id'], session['current_chat_data']['user_id'], encrypted_message))

    syKey = session["sym_key"]

    with open("Data/Chat_data/" + session["username"] + "/" + session['current_chat_data']['username'], 'a') as f:
        f.write(datetime.now().strftime("%I:%M%p on %B %d, %Y") + "\n" + session[
            'username'] + "\n" + Encryption_Manager.encrypt_message_with_symmetric_key(syKey, request_message) + "\n")

    messages = get_messages(session['current_chat_data']['username'])
    return redirect(url_for('chat.chat', friend=session['current_chat_data']['username'], messages=messages))
    # return render_template('chat.html',friend=session['current_chat_data']['username'],messages =messages)


@chat_bp.route("/send_group_chat_message", methods=['POST'])
def send_group_chat_message():
    if 'username' not in session:
        return redirect(url_for('index'))
    request_message = request.form.get('message')

    GroupChat.send_message(session['current_group_chat_data']['group_chat_id'], request_message, session['user_id'],
                           session['sym_key'],session['username'])
    messages = GroupChat.get_group_chat_messages(session['user_id'],
                                                 session['current_group_chat_data']['group_chat_id'],
                                                 session['username'], session['sym_key'])

    session['current_group_chat_data']['messages'] = messages
    return redirect(url_for('chat.open_group_chat',group_chat_id=session['current_group_chat_data']['group_chat_id'],username = session['username']))

@chat_bp.route("/open_group_chat/<group_chat_id>")
def open_group_chat(group_chat_id):
    session['opened_group_chat_time'] = datetime.now()
    if 'username' not in session:
        return redirect(url_for('index'))

    messages = get_group_chat_messages(session['user_id'], group_chat_id, session['username'],
                                      session['sym_key'])

    people = GroupChat.get_group_members(group_chat_id)
    name = "NONE"
    for chat in session['chats']:
        if chat['ID'] == group_chat_id:
            name = chat['name']
            break
    session['group_chat_id'] = group_chat_id
    session['current_group_chat_data'] = {"messages": messages, "people": people, "group_chat_id": group_chat_id,
                                          'name': name}

    return render_template("group_chat.html", messages=messages, people=people, group_chat_name=name,username = session['username'])


@chat_bp.route('/create_group_chat', methods=['POST', 'GET'])
def create_group_chat():
    user_id = session['user_id']
    friends = SQL_manager.execute_query(
        """
        SELECT u.username ,u.is_online,u.user_id
        FROM (
            SELECT friend_id as id FROM Friend WHERE user_id = %s
            UNION
            SELECT user_id as id FROM Friend WHERE friend_id = %s
        ) combined
        JOIN users u ON combined.id = u.user_id
        """,
        params=(user_id, user_id),
        fetch=True
    )["results"]

    if request.method == 'POST':
        gc_name = request.form.get('group_name')
        selected_friends = request.form.getlist('selected_friends')

        if not gc_name:
            flash('Group name is required', 'error')
            return redirect(url_for('chat.create_group_chat'))

        if len(selected_friends) < 1:
            flash('You must select at least one friend', 'error')
            return redirect(url_for('chat.create_group_chat'))

        friend_ids = ""
        friend_member_uuid = ""
        for friend in selected_friends:
            friend_ids += friend + ","
            friend_member_uuid += str(uuid.uuid4()) + ","

        friend_ids += session['user_id']
        friend_member_uuid += str(uuid.uuid4())

        random_uuid = str(uuid.uuid4())

        SQL_manager.execute_query(
            "CALL create_group_chat(%s, %s, %s, %s)",
            params=(
                random_uuid,
                gc_name,
                friend_ids,
                friend_member_uuid
            )
        )
        print("group chat created")
        return redirect(url_for('auth.dashboard'))

    return render_template('create_group_chat.html', friends=friends)
