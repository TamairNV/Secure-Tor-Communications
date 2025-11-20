import os
import uuid

from flask import Blueprint
from flask import render_template, request, session, redirect, url_for, flash
from Levenshtein import distance as levenshtein_distance
from Code import GroupChat
from utils import Encryption_Manager, SQL_manager
from utils.tor import get_onion_address

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/dashboard',methods=['POST','GET'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    SQL_manager.execute_query("UPDATE users SET is_online = TRUE WHERE user_id = %s", (session['user_id'],))

    user_id = session['user_id']

    combined_query = """
    SELECT
        u.username,
        NULL as created_at, -- created_at is not relevant for friends, use NULL
        'friend' as type    -- Label this row as a 'friend'
    FROM (
        SELECT friend_id as id FROM Friend WHERE user_id = %s
        UNION -- UNION removes duplicates, if you want to keep duplicates use UNION ALL
        SELECT user_id as id FROM Friend WHERE friend_id = %s
    ) combined
    JOIN users u ON combined.id = u.user_id

    UNION ALL -- Use UNION ALL to include all rows from both selects

    SELECT
        u.username,
        fr.created_at,      -- Include created_at for friend requests
        'friend_request' as type -- Label this row as a 'friend_request'
    FROM FriendRequest fr
    JOIN users u ON fr.sender_id = u.user_id
    WHERE fr.recipient_id = %s AND fr.status = 'pending'
    """

    # Execute the combined query
    # Note: The parameters need to match the order of placeholders in the query.
    # The user_id for the friend query appears twice, and once for the friend request query.
    combined_results = SQL_manager.execute_query(
        combined_query,
        params=(user_id, user_id, user_id),
        fetch=True
    )["results"]

    # Initialize empty lists for friends and friend requests
    friends = []
    friend_requests = []

    # Iterate through the combined results and separate them based on the 'type' column
    for row in combined_results:
        # Assuming your SQL_manager returns rows as dictionaries or objects with attribute access
        # Adjust the access method (e.g., row['type'], row.type) based on your SQL_manager implementation
        row_type = row['type']  # Access the 'type' column
        username = row['username']  # Access the 'username' column

        if row_type == 'friend':
            # For friends, just add the username to the friends list
            friends.append({'username': username})
        elif row_type == 'friend_request':
            # For friend requests, add username and created_at to the friend_requests list
            created_at = row['created_at']  # Access the 'created_at' column
            friend_requests.append({'username': username, 'created_at': created_at})

    # Now your 'friends' and 'friend_requests' lists are populated
    print(friend_requests)
    print(friends)
    chats = GroupChat.get_group_chats(session['user_id'])
    session['chats'] = chats
    if request.method == 'POST':
        if 'search_group_input' in request.form and request.form['search_group_input'].strip():
            chats = sort_group_chat(chats,request.form['search_group_input'])

        if 'search_friend_input' in request.form and request.form['search_friend_input'].strip():
            friends = sort_friends(friends,request.form['search_friend_input'])


    if chats is None:
        chats = []

    return render_template('dashboard.html',
                           username=session['username'],
                           onion_address=session.get('onion_address', ''),
                           friends=friends,
                           friend_requests=friend_requests,
                           group_chats=chats)

def sort_friends(users,input):
    sorted_users = sorted(
        users,
        key=lambda word: levenshtein_distance(input, word['username'])
    )
    return sorted_users

def sort_group_chat(groups, input_name):
    print(groups)
    # Sort by name similarity first
    groups_sorted_by_name = sorted(
        groups,
        key=lambda group: levenshtein_distance(input_name, group['name'])
    )

    # Sort again: groups where input_name is a member come first
    groups_sorted = sorted(
        groups_sorted_by_name,
        key=lambda group: 0 if input_name in group['members_dict'] else 1
    )

    return groups_sorted



@auth_bp.route('/logout')
def logout():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    session.clear()
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        output = SQL_manager.execute_query(
            "SELECT p.salt,o.public_key FROM password p,users u,onion_keys o WHERE  u.username = %s AND u.user_id = p.user_id AND o.user_id = u.user_id",
            params=[username], fetch=True)["results"]
        if not output:
            return redirect(url_for('auth.login'))

        salt, pub_key = output[0]["salt"], output[0]["public_key"]

        sym_key = Encryption_Manager.hash_password(password, salt.encode())
        session["sym_key"] = sym_key
        with open(f"Data/Keys/" + username + "/" + "priv_key.pem", 'r') as f:
            enc_key = f.readline().strip()
            try:
                Encryption_Manager.decrypt_message_with_symmetric_key(sym_key, enc_key)
            except:
                flash("Username or password incorrect")
                return redirect(url_for('auth.login'))

        userData = \
            SQL_manager.execute_query(
                "SELECT * FROM users u ,onion_keys o WHERE u.username = %s AND u.user_id = o.user_id",
                params=[username, ], fetch=True)["results"]
        if userData:
            userData = userData[0]
            session['username'] = username
            session['onion_address'] = userData["onion_address"]
            session['public_key'] = userData["public_key"]
            session['user_id'] = userData["user_id"]
            return redirect(url_for('auth.dashboard'))

    return render_template('login.html')


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return redirect(url_for('auth.signup'))

        is_name_taken = \
        SQL_manager.execute_query("SELECT 1 FROM users WHERE username = %s LIMIT 1", params=(username,), fetch=True)[
            'results']

        if is_name_taken:
            flash('Username is already taken!', 'error')
            return redirect(url_for('auth.signup'))

        onion_address = get_onion_address()
        random_uuid = str(uuid.uuid4())
        keys = Encryption_Manager.generate_rsa_key_pair()

        sym_key, salt = Encryption_Manager.create_key_from_password(password)

        session['username'] = username
        session['onion_address'] = onion_address
        session['user_id'] = random_uuid

        os.makedirs("Data/Keys/" + session["username"], exist_ok=True)

        str_prv, str_pub = Encryption_Manager.keys_to_strings(keys[0], keys[1])
        with open("Data/Keys/" + session["username"] + "/" + "priv_key.pem", 'wb') as f:
            key = Encryption_Manager.encrypt_message_with_symmetric_key(sym_key, str_prv)
            f.write(key.encode())

        symmetric_key = Encryption_Manager.create_symmetric_key()
        with open(f"Data/Keys/" + session["username"] + "/" + "sym_key.pem", 'wb') as f:
            f.write(symmetric_key.encode())

        session['public_key'] = str_pub
        session['sym_key'] = symmetric_key

        SQL_manager.execute_query(
            "CALL register_user(%s, %s, %s, %s, %s)",
            params=(
                random_uuid,
                username,
                onion_address,
                str_pub,
                salt
            )
        )
        print("key added")
        return redirect(url_for('auth.dashboard'))

    return render_template('signup.html')
