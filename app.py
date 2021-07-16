import os
import flask
import pymongo
import gridfs
import werkzeug.utils
from flask import Flask, session, render_template, request, redirect
from hashlib import sha256
from login import is_logged_in
import dbtemplates
from datetime import date
from os import path,remove
import random
import json
from bson.objectid import ObjectId
import re
import calendar
import time

#loading config
with open('base.cfg') as file:
    passwd=file.readline().strip()
with open('secret.cfg') as file:
    secret=file.readline()

#db connection
app = Flask(__name__)
app.secret_key=secret
connection=pymongo.MongoClient("mongodb+srv://appUser:{0}@cluster0.grqow.mongodb.net/Cabbage?retryWrites=true&w=majority".format(passwd))
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
print(connection.list_database_names())
db=connection['appDB']
users=db.users
posts=db.posts
files=gridfs.GridFSBucket(db)
primfiles=gridfs.GridFS(db)
comments=db.comments


app.config['UPLOAD_FOLDER']='upload'
app.config['DOWNLOAD_FOLDER']='static'
app.config['MAX_CONTENT_PATH’']=10000000
login_hash = {}
inspection_delete=[]
comment_depth=0


@app.route('/search')
def search_db():
    query=request.args.get('query')
    #print(query)
    query=query.strip()
    if query[0]=='#':
        data=[]
        for i in range(10):
            data.extend(list(posts.find({'tags.{0}'.format(i):query[1:]})))
        return render_template('query_results.html',lst=data, user_id=session['login']['login'])
    elif query[0]=='@':
        data = list(users.find({'login': query[1:]}))
        return render_template('query_results.html', lst=data, user_id=session['login']['login'])
    else:
        data = list(posts.find({'title': {'$regex': query}}))
        print(data)
        return render_template('query_results.html', lst=data, user_id=session['login']['login'])


@app.route('/posts/<id>')
def view_user_posts(id):
    lst=list(posts.find({'login':id}))
    for pst in lst:
        pst['_id']=str(pst['_id'])
    #print(lst)
    return render_template('inspect_activity_posts.html', lst=lst, login=id, user_id=session['login']['login'])


@app.route('/comments/<id>')
def view_user_comments(id):
    lst = list(comments.find({'login': id}))
    for cmt in lst:
        cmt['_id'] = str(cmt['_id'])
    #print(lst)
    return render_template('inspect_activity_comments.html', lst=lst, login=id, user_id=session['login']['login'])

@app.route('/thread/<id>/<cid>')
def view_thread(id, cid):
    post = posts.find_one(ObjectId(id))
    comtree = []
    root= comments.find_one(ObjectId(cid))
    root['depth']=0
    comtree.append(root)
    build_thread(cid, comtree)
    #downloading media for root comment
    medd=comments.find_one(ObjectId(cid))['media']
    for comment_media in medd.values():
        if not os.path.exists(path.join(app.config['DOWNLOAD_FOLDER'], comment_media)):
            with open(path.join(app.config['DOWNLOAD_FOLDER'], comment_media), 'wb+') as my_file:
                    files.download_to_stream(ObjectId(comment_media), my_file)

    media= post['media'].values()
    for image in media:
        if not os.path.exists(path.join(app.config['DOWNLOAD_FOLDER'],image)):
            with open(path.join(app.config['DOWNLOAD_FOLDER'], image), 'wb+') as my_file:
                files.download_to_stream(ObjectId(image), my_file)
    tags=post['tags'].values()
    #print(comtree)
    return render_template('view_thread.html', title=post['title'], text=post['content'], login=post['login'], media=media, tags=tags, id=id,comms=comtree, user_id=session['login']['login'])

@app.route('/view_post/<id>')
def view_post(id):
    post=posts.find_one(ObjectId(id))
    topcoms=[]
    for comment in comments.find({'post':id, 'reply_id':'-1'}):
        com_id=str(comment.get('_id'))
        for comment_media in comment['media'].values():
            if not os.path.exists(path.join(app.config['DOWNLOAD_FOLDER'], comment_media)):
                with open(path.join(app.config['DOWNLOAD_FOLDER'], comment_media), 'wb+') as my_file:
                    files.download_to_stream(ObjectId(comment_media), my_file)
        topcoms.append({'comment':comment, 'com_id':com_id})

    media= post['media'].values()
    for image in media:
        if not os.path.exists(path.join(app.config['DOWNLOAD_FOLDER'],image)):
            with open(path.join(app.config['DOWNLOAD_FOLDER'], image), 'wb+') as my_file:
                files.download_to_stream(ObjectId(image), my_file)
    tags=post['tags'].values()
    return render_template('view_post.html', title=post['title'], text=post['content'], login=post['login'], media=media, tags=tags, id=id,comms=topcoms, user_id=session['login']['login'])


#tagi ok, text ok, user<->post ok, img - ok
@app.route('/add_post', methods=['GET','POST'])
@is_logged_in
def add_post():

    if request.method=='GET':
        return render_template('add_post.html', user_id=session['login']['login'])
    else:
        user = session['login']
        tag=request.form.get('tags')
        if tag=='':
            tag=[]
        else:
            tag=tag.split()
        media=[]
        #print(request.files.getlist('filename'))
        if request.files.get('filename').filename !='':
            for usr_profilepic in request.files.getlist('filename'): #named user prfilepic for conveniance
                usr_profilepic.filename = usr_profilepic.filename.split('.')[0] + str(
                    int(random.random() * 1000000000000000)) + '.' + \
                                          usr_profilepic.filename.split('.')[1]
                usr_profilepic.save(
                    path.join(app.config['UPLOAD_FOLDER'], werkzeug.utils.secure_filename(usr_profilepic.filename)))
                if usr_profilepic.filename.split('.')[1] in ALLOWED_EXTENSIONS:
                    with open(path.join(app.config['UPLOAD_FOLDER'],
                                        werkzeug.utils.secure_filename(usr_profilepic.filename)), 'rb') as  pfp:
                        fid = files.upload_from_stream(str(usr_profilepic), pfp)
                        media.append(str(fid))
                    remove(
                        path.join(app.config['UPLOAD_FOLDER'], werkzeug.utils.secure_filename(usr_profilepic.filename)))#clearing upload
        post=dbtemplates.Post(user['login'], tag, media, request.form.get('text'),request.form.get('title'))
        #print(post)
        #print(post.to_dict())
        pid=posts.insert_one(post.to_dict())
        if not pid.acknowledged:
            return 'error occured while adding post'
        pid=str(pid.inserted_id)
        #print(user)
        if len(user['posts'])==0:
            user['posts']['0']=pid
        else:
            user['posts']['{0}'.format(max([int(i) for i in user['posts'].keys()])+1)]=str(pid)
        #print(user)
        #print(post.to_dict())
        users.delete_one({'login': session['login']['login']})
        users.insert_one(session['login'])
        data = users.find_one({"login": session['login']['login'], "password": session['login']['password']})
        session['login'] = dbtemplates.User(data['login'],
                                            data['password'],
                                            data['description'],
                                            data['profilepic'],
                                            dict(zip([int(i) for i in data['posts'].keys()], data['posts'].values())),
                                            dict(zip([int(i) for i in data['comments'].keys()],
                                                     data['comments'].values()))).to_dict()
        return redirect('/view_post/'+str(pid))


@app.route('/add_comment/<post_id>/<comment_id>',methods=['POST','GET'])
@is_logged_in
def add_comment(post_id, comment_id='0'):
    if request.method=='GET':
        return render_template('add_comment.html', post_id=post_id, comment_id=comment_id, user_id=session['login']['login'])
    else:
        user=session['login']
        media=[]
        if request.files.get('filename').filename !='':
            for usr_profilepic in request.files.getlist('filename'): #named user prfilepic for conveniance
                usr_profilepic.filename = usr_profilepic.filename.split('.')[0] + str(
                    int(random.random() * 1000000000000000)) + '.' + \
                                          usr_profilepic.filename.split('.')[1]
                usr_profilepic.save(
                    path.join(app.config['UPLOAD_FOLDER'], werkzeug.utils.secure_filename(usr_profilepic.filename)))
                if usr_profilepic.filename.split('.')[1] in ALLOWED_EXTENSIONS:
                    with open(path.join(app.config['UPLOAD_FOLDER'],
                                        werkzeug.utils.secure_filename(usr_profilepic.filename)), 'rb') as  pfp:
                        fid = files.upload_from_stream(str(usr_profilepic), pfp)
                        media.append(str(fid))
                    remove(
                        path.join(app.config['UPLOAD_FOLDER'], werkzeug.utils.secure_filename(usr_profilepic.filename)))#clearing upload

        comment=dbtemplates.Comment(comment_id,media,post_id,request.form.get('text'),user['login'])
        cid=comments.insert_one(comment.to_dict())
        if not cid.acknowledged:
            return 'error occured while adding post'
        cid=str(cid.inserted_id)
        if len(user['comments']) == 0:
            user['comments']['0'] = cid
        else:
            user['comments']['{0}'.format(max([int(i) for i in user['comments'].keys()]) + 1)] = str(cid)
            # print(user)
            # print(post.to_dict())
        users.delete_one({'login': session['login']['login']})
        users.insert_one(session['login'])
        data = users.find_one({"login": session['login']['login'], "password": session['login']['password']})
        session['login'] = dbtemplates.User(data['login'],
                                            data['password'],
                                            data['description'],
                                            data['profilepic'],
                                            dict(zip([int(i) for i in data['posts'].keys()], data['posts'].values())),
                                            dict(zip([int(i) for i in data['comments'].keys()],
                                                     data['comments'].values()))).to_dict()
        return redirect('/view_post/' + str(post_id))


@app.route('/add_reply')
@is_logged_in
def add_reply():
    pass


#to be written
@app.route('/edit_post/<login>')
@is_logged_in
def create():
    return redirect('/')

#ok
@app.route('/profile/<login>')
#@app.after_request(os.remove(path.join(app.config['DOWNLOAD_FOLDER'],inspection_delete[0])))
def profile(login):
    if users.find_one({"login":login}) is None:
        return 'Such user does not exist in our resources'
    else:
        data=users.find_one({"login":login})
        picture=data['profilepic']
        description=data['description']
        inspection_delete.append(picture)
        if not os.path.exists(path.join(app.config['DOWNLOAD_FOLDER'],picture)):
            with open(path.join(app.config['DOWNLOAD_FOLDER'], picture), 'wb+') as my_file:
                files.download_to_stream(ObjectId(picture), my_file)  # ok
        #print(os.path.join(app.root_path,app.config['DOWNLOAD_FOLDER'],picture)) ok
        return render_template('inspect_profile.html',
                               Login=login,
                               Filename=picture,
                               Description=description, user_id=session['login']['login'])


#ok
@app.route('/profile/edit', methods=['POST','GET'])
@is_logged_in
def edit_profile():
    if request.method=='GET':
        return render_template('edit_profile.html',
                               Title='Gere you can edit your profile, remember to save after every change', user_id=session['login']['login'])
    elif request.method=='POST':
        if login_hash[session['login']['login']] == sha256((session['login']['login'] + str(date.today()) + secret).encode('utf-8')).hexdigest():
            if request.form.get('password',None) is not None: #change password
                session['login']['password']=sha256((request.form.get('password')+secret).encode('utf-8')).hexdigest()
                session['login'].delete_one({'login':session['login']['login']})
                session['login'].insert_one(session['login'])
                return redirect('/')
            elif request.form.get('description',None)is not None: #change description
                session['login']['description']=request.form.get('description')
                users.delete_one({'login': session['login']['login']})
                users.insert_one(session['login'])
                return redirect('/')
            elif request.files.get('filename', None) is not None: #change profile picture
                prev=session['login']['profilepic'] #for some reason prev field does not get updated here
                usr_profilepic = request.files.get('filename')
                usr_profilepic.filename = usr_profilepic.filename.split('.')[0] + str(
                    int(random.random() * 1000000000000000)) + '.' + \
                                          usr_profilepic.filename.split('.')[1]
                usr_profilepic.save(
                    path.join(app.config['UPLOAD_FOLDER'], werkzeug.utils.secure_filename(usr_profilepic.filename)))
                if usr_profilepic.filename.split('.')[1] in ALLOWED_EXTENSIONS:
                    with open(path.join(app.config['UPLOAD_FOLDER'],
                                        werkzeug.utils.secure_filename(usr_profilepic.filename)),'rb') as  pfp:
                        fid=files.upload_from_stream(str(usr_profilepic),pfp)


                    session['login']['profilepic'] =str(fid)
                    remove(
                        path.join(app.config['UPLOAD_FOLDER'], werkzeug.utils.secure_filename(usr_profilepic.filename)))#clearing upload
                    users.delete_one({'login': session['login']['login']})
                    users.insert_one(session['login'])
                    data = users.find_one({"login": session['login']['login'], "password": session['login']['password']})
                    session['login'] = dbtemplates.User(data['login'],
                                                        data['password'],
                                                        data['description'],
                                                        data['profilepic'],
                                                        dict(zip([int(i) for i in data['posts'].keys()],
                                                                 data['posts'].values())),
                                                        dict(zip([int(i) for i in data['comments'].keys()],
                                                                 data['comments'].values()))).to_dict()
                    remove(path.join(app.config['UPLOAD_FOLDER'], werkzeug.utils.secure_filename(usr_profilepic.filename)))
                    files.delete(file_id=ObjectId(prev))
                    return redirect('/')
                else:
                    return 'Image with given extension is not allowed'
        return redirect('/')




#ok
@app.route('/logout')
@is_logged_in
def logout():
    d = session['login']
    if login_hash[d['login']]==sha256((d['login'] + str(date.today()) + secret).encode('utf-8')).hexdigest():
        session.pop('logged_in')
        login_hash.pop(d['login'])
        session.pop('login')
    return redirect('/')


#ok
@app.route('/login',methods=['POST','GET'])
def login():
    if  request.method=='GET':
        return render_template('login.html')
    else:
        ulogin= request.form.get('login')
        upassword = sha256((request.form.get('password')+secret).encode('utf-8')).hexdigest()
        if not (users.find_one({"login":ulogin, "password":upassword}) is None):
            session['logged_in']=True
            data=users.find_one({"login":ulogin, "password":upassword})
            #print(data)
            session['login']=dbtemplates.User(data['login'],
                                              data['password'],
                                              data['description'],
                                              data['profilepic'],
                                              dict(zip([int(i) for i in data['posts'].keys()],
                                                       data['posts'].values())),
                                              dict(zip([int(i) for i in data['comments'].keys()],
                                                       data['comments'].values()))).to_dict()
            #print(session['login'])
            login_hash[ulogin]=sha256((ulogin + str(date.today()) + secret).encode('utf-8')).hexdigest()
            return redirect('/')
        else:
            return 'incorrect credentials'


#ok
@app.route('/create_account',methods=['POST','GET'])
def create_account():
    if request.method=='GET':
        return render_template('register.html', title='Log in:', user_id=session['login']['login'])
    else:
        #print(request.form)
        #print(request.files)
        usr_login = request.form.get('login')
        usr_password = sha256((request.form.get('password')+secret).encode('utf-8')).hexdigest()
        usr_descr=request.form.get('description')
        usr_profilepic=request.files.get('filename')
        usr_profilepic.filename = usr_profilepic.filename.split('.')[0] + str(int(random.random()*1000000000000000)) + '.' + \
                                   usr_profilepic.filename.split('.')[1]
        #print(usr_profilepic)
        usr_profilepic.save(
            path.join(app.config['UPLOAD_FOLDER'],werkzeug.utils.secure_filename(usr_profilepic.filename)))
        user = dbtemplates.User(usr_login, usr_password, usr_descr, usr_profilepic.filename, {},{})

        if user.profilepic.split('.')[1] in ALLOWED_EXTENSIONS:
            if users.find_one({"login": user.login}) is None:
                if user.login != '' and user.password != '':

                    with open(path.join(app.config['UPLOAD_FOLDER'],
                                        werkzeug.utils.secure_filename(usr_profilepic.filename)),'rb') as  pfp:
                        fid=files.upload_from_stream(user.profilepic,pfp)

                    user.profilepic=str(fid)
                    user_dict = user.to_dict()
                    users.insert_one(user_dict)
                    remove(path.join(app.config['UPLOAD_FOLDER'],werkzeug.utils.secure_filename(usr_profilepic.filename)))
                    session['logged_in'] = True
                    session['login'] = user.to_dict()
                    login_hash[usr_login] = sha256((user.login + str(date.today()) + secret).encode('utf-8')).hexdigest()
                    #print(login_hash[usr_login])
                    return redirect('/')

            else:
                return render_template('register.html',
                                       title='Such account already exists, please choose other credentials:',
                                       user_id=session['login']['login'])
        else:
            return 'Unexpected file extension'


#ok
@app.route('/delete_account/<login>',methods=['POST','GET'])
def delete_account(login):
    if request.method=='GET':
        return render_template('authorise.html',
                               path='delete_account',
                               login=login,
                               title='Enter your credentials in order to delete account',
                               user_id=session['login']['login'])
    else:
        usr_login = request.form.get('login')
        usr_password = sha256((request.form.get('password') + secret).encode('utf-8')).hexdigest()
        if users.find_one({"login":usr_login}) is None:
            return 'Such user does not exist in our resources'
        else:
            if not (users.find_one({"login": usr_login, "password": usr_password}) is None) and login==usr_login:
                users.delete_one({'login':login})
                #print(session['login']['profilepic'])
                #print(primfiles.exists({"_id":ObjectId(session['login']['profilepic'])}))
                files.delete(file_id=ObjectId(session['login']['profilepic']))
                return redirect('/logout')
            else:
                return 'Such user does not exist in our resources'




@app.route('/')
@is_logged_in
def feed():
    for element in os.listdir(path.join(app.root_path, app.config['DOWNLOAD_FOLDER']) ):
        elapsed=os.path.getmtime(path.join(app.root_path,app.config['DOWNLOAD_FOLDER'], element))
        curr= calendar.timegm(time.gmtime())
        print(curr)
        print(elapsed)
        print(abs(elapsed-curr))
        if abs(elapsed-curr)>60:
            print('ok')
            os.remove(path.join(app.root_path,app.config['DOWNLOAD_FOLDER'], element))
    fresh_posts = list(posts.find())
    if len(fresh_posts)<10:
        return render_template('newest.html', new_posts=fresh_posts)
    else:
        return render_template('newest.html', new_posts = fresh_posts[-10:],  user_id=session['login']['login'])






if __name__ == '__main__':
    app.run(debug=True  )


def build_thread(cid, comtree):
    offset=0
    for index, item in enumerate(comtree):
        if str(item['_id'])==cid:
            root_index=index
            root=item
            break
    comms=list(comments.find({'reply_id':cid}))
    comms=comms[::-1]
    #print(comms)
    if len(comms)==0:
        return comtree
    else:
        for comment in comms:
            comment['depth']=root['depth']+1
            #com_id = str(comment.get('_id'))
            for comment_media in comment['media'].values():
                if not os.path.exists(path.join(app.config['DOWNLOAD_FOLDER'], comment_media)):
                    with open(path.join(app.config['DOWNLOAD_FOLDER'], comment_media), 'wb+') as my_file:
                        files.download_to_stream(ObjectId(comment_media), my_file)
                comtree.insert(root_index+1,comment)
        build_thread(str(comment['_id']),comtree)
        return comtree