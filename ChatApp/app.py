# 構築や動作に必要なライブラリやモジュールをインポート
from flask import Flask, request, redirect, render_template, session, flash, abort, jsonify
from datetime import timedelta
import hashlib
import uuid
import re
# from flask_socketio import SocketIO, emit
# import mysql.connector
# from mysql.connector import Error
import os
from models import dbConnect

# Flask アプリケーションのインスタンスを作成
app = Flask(__name__)
app.secret_key = uuid.uuid4().hex
app.permanent_session_lifetime = timedelta(days=7)  # セッションの有効期限を7日に変更
# Socket.IO の設定
# socketio = SocketIO(app)

# 新規会員登録ページの表示
@app.route('/signup')
def signup():
    return render_template('registration/signup.html')

# 新規会員登録の処理、フォームを送信するPOSTの処理を実装
@app.route('/signup', methods=['POST'])
def userSignup():
    username = request.form.get('username')
    email = request.form.get('email')
    password1 = request.form.get('password1')
    password2 = request.form.get('password2')
    address = request.form.get('address')
    greeting = request.form.get('greeting')

    pattern = "^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"

    if username == '' or email =='' or password1 == '' or password2 == '' or address == '' or greeting == '':
        flash('空のフォームがあるようです')
    elif password1 != password2:
        flash('二つのパスワードの値が違っています')
    elif re.match(pattern, email) is None:
        flash('正しいメールアドレスの形式ではありません')
    else:
        uid = uuid.uuid4()
        # password = hashlib.sha256(password1.encode('utf-8')).hexdigest()
        password = password1  # local検証の為、一時的にハッシュ化しない
        DBuser = dbConnect.getUser(email) # メールアドレスを元にユーザー情報を検索する

        if DBuser != None:
            flash('既に登録されているようです')
        else:
            dbConnect.createUser(uid, username, email, password, address, greeting) # ユーザー情報の追加
            UserId = str(uid)
            session['uid'] = UserId
            return redirect('/')
    return redirect('/signup')

# ログインページの表示
@app.route('/login')
def login():
    return render_template('registration/login.html')

# ログイン処理、フォームを送信するPOSTの処理を実装
@app.route('/login', methods=['POST'])
def userLogin():
    email = request.form.get('email')
    password = request.form.get('password')

    if email =='' or password == '':
        flash('空のフォームがあるようです')
    else:
        user = dbConnect.getUser(email) # メールアドレスを元にユーザー情報を検索する
        if user is None:
            flash('このユーザーは存在しません')
        else:
            if password != user["password"]:  # ハッシュ化せずに平文で比較
                flash('パスワードが間違っています！')
            # hashPassword = hashlib.sha256(password.encode('utf-8')).hexdigest()
            # if hashPassword != user["password"]:
            #     flash('パスワードが間違っています！')
            else:
                session['uid'] = user["uid"]
                return redirect('/')
    return redirect('/login')

# ①チャットルーム一覧、②＋マッチング、③マッチング依頼一覧画面を表示
@app.route('/')
def home():
    uid = session.get("uid")
    if uid is None:
        return redirect('/login')
    else:
        channels = dbConnect.getChatAll() # ①②③のすべてのチャットを取得
        channels = channels[::-1]  # スライスを使ってタプルを逆順にする
    return render_template('home.html', channels=channels, uid=uid)

# ホーム画面からプロフィール画面にページの遷移
@app.route('/profile')
def profile():
    uid = session.get("uid")
    if uid is None:
        return redirect('/login')
    else:
        user = dbConnect.getUserByUid(uid)
    return render_template('profile.html', user=user)

# プロフィール画面からユーザ情報の更新
@app.route('/profile_edit', methods=['GET', 'POST'])
def profile_edit():
    uid = session.get("uid")
    if uid is None:
        return redirect('/login')

    if request.method == 'POST':
        # POSTリクエストの場合、フォームからデータを取得して更新処理を行う
        username = request.form.get('username')
        email = request.form.get('email')
        address = request.form.get('address')
        greeting = request.form.get('greeting')

        # データベースを更新
        dbConnect.updateUser(uid, username, email, address, greeting)
        
        # 更新後のプロフィール画面ページにリダイレクト
        return redirect('/profile')
    else:
        # GETリクエストの場合、ユーザー情報を取得して編集ページを表示
        user = dbConnect.getUserByUid(uid)
        return render_template('profile_edit.html', user=user)

# ホーム画面からchat_listページに画面遷移
@app.route('/chat_list')
def chat_list():
    uid = session.get("uid")
    if uid is None:
        return redirect('/login')

    channellist = dbConnect.getChatRoom(uid)
    chatlist = []
    for channel in channellist: 
        print(channel["user_ids"])
        user_numbers = channel["user_ids"].split(",")
        if uid in user_numbers:
            chatlist.append(channel)
    return render_template('chat_list.html', chat_rooms=chatlist)

# チャット画面からGETとPOSTの処理を実装 追加7/28夜間追加
@app.route('/chat', methods=['GET', 'POST'])
def chat():
    uid = session.get("uid")
    if uid is None:
        return redirect('/login')
    
    chat_id = request.args.get('room_id')  # URL パラメータからチャットIDを取得
    if chat_id:
        if request.method == 'GET':
            # メッセージの取得
            messages = dbConnect.getMessagesByChatRoom(uid, chat_id)
            return render_template('chat.html', chat_id=chat_id, messages=messages)

        if request.method == 'POST':
            # メッセージの投稿
            message = request.form.get('message')
            if message:
                dbConnect.createMessage(uid, chat_id, message)
                return redirect(f'/chat?room_id={chat_id}')
    else:
        # チャットIDが指定されていない場合、チャットルームの一覧を表示
        chats = dbConnect.getChatRoomList(uid)
        return render_template('chat_list.html', chats=chats)

# 「matching」URLのエンドポイント　7/31に処理を新規追加した
@app.route('/matching', methods=['GET', 'POST'])
def matching():
    if request.method == 'POST':
        address = request.json.get('address')
        if address:
            users = dbConnect.getUsersByAddress(address)  # データを取得
            # 各ユーザーが辞書であることを確認し、キーを使用してアクセス
            return jsonify([{
                'uid': user.get('uid'),            # ユーザーID (修正)
                'name': user.get('username'),      # ユーザー名
                'address': user.get('address'),    # ユーザーの住所
                'greeting': user.get('greeting')   # 挨拶
            } for user in users])
        return jsonify({'error': '住所が指定されていません'}), 400
    else:
        return render_template('matching.html')

# 「matching」URLのエンドポイント
# @app.route('/matching', methods=['GET', 'POST'])
# def matching():
#     if request.method == 'POST':
#         address = request.json.get('address')
#         if address:
#             users = dbConnect.getUsersByAddress(address)  # データを取得
#             # デバッグ用に返すデータの形式を確認
#             # print('Retrieved users:', users)
#             # 各ユーザーが辞書であることを確認し、キーを使用してアクセス
#             return jsonify([{
#                 'name': user.get('username'),       # ユーザー名
#                 'address': user.get('address'),    # ユーザーの住所
#                 'greeting': user.get('greeting')    # 挨拶
#             } for user in users])
#         return jsonify({'error': '住所が指定されていません'}), 400
#     else:
#         return render_template('matching.html')

# チャットルームを作成するエンドポイント
# @app.route('/create_chatroom', methods=['POST'])
# def create_chatroom():
#     uid = session.get("uid")
#     if uid is None:
#         return jsonify({'error': 'ログインが必要です'}), 403

#     data = request.json
#     name = data.get('name')
#     address = data.get('address')
#     user_ids = data.get('user_ids', '')  # ここでデフォルト値として空文字列を設定

#     # デバッグ出力
#     print(f"Received data: name={name}, address={address}, user_ids={user_ids}")

#     if not name or not address or not user_ids:
#         return jsonify({'error': '名前、住所、およびユーザーIDが必要です'}), 400

#     # user_ids がカンマ区切りの文字列であることを確認し、リストに変換
#     user_ids_list = user_ids.split(',')
#     if uid not in user_ids_list:
#         user_ids_list.append(uid)  # ログインユーザーの UID を追加
#     user_ids_string = ','.join(user_ids_list)  # 再びカンマ区切りの文字列に変換

#     try:
#         chatroom_id = dbConnect.createChatroom(uid, name, address, user_ids)

#         if chatroom_id:
#             return jsonify({'success': True, 'chatroom_id': chatroom_id}), 200
#         else:
#             return jsonify({'error': 'チャットルームの作成に失敗しました'}), 500
#     except Exception as e:
#         print(f"エラーが発生しました: {str(e)}")
#         return jsonify({'error': 'サーバーエラー'}), 500

@app.route('/create_chatroom', methods=['POST'])
def create_chatroom():
    data = request.get_json()
    print(f"Received data: {data}")  # デバッグ用ログ

    name = data.get('name')
    address = data.get('address')
    uid = data.get('uid')  # 修正: フロントエンドから送信された uid を取得
    
    print(f"Received UID: {uid}")  # デバッグ用ログ

    logged_in_user_id = session.get('uid')

    if not logged_in_user_id:
        return jsonify({"message": "ログインしていません"}), 401
    
    if not uid:
        return jsonify({"message": "UID is required"}), 400

    # user_ids の生成
    user_ids = ','.join(map(str, [logged_in_user_id, uid]))
    print(f"Generated user_ids string: {user_ids}")  # デバッグ用ログ

    abstract = f"Chatroom for {name} at {address}"

    try:
        dbConnect.createChatroom(uid=generate_unique_id(), name=name, abstract=abstract, user_ids=user_ids)
        return jsonify({"message": "チャットルームが作成されました"}), 200
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"message": "チャットルームの作成に失敗しました"}), 500

def generate_unique_id():
    return str(uuid.uuid4())


# マッチングリクエスト一覧ページの表示
@app.route('/request_list.html')
def request_list():
    return render_template('request_list.html')

@app.route('/logout')
def logout():
    return render_template('registration/login.html')

if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=False)