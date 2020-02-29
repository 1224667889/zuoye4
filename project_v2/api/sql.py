from flask import Flask, jsonify, abort, request ,session
import datetime
from redate import redatetime
from rerequest import *
import functools
import os
from datetime import timedelta
from flask_sqlalchemy import SQLAlchemy
import pymysql 
import pylint_flask
app = Flask(__name__)


app.config['SQLALCHEMY_DATABASE_URI']='mysql://%s:%s@%s/%s'%('root','cjtbs','localhost:4036','flask_sql_api')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS']=False
db=SQLAlchemy(app)

#备忘录模型
class Note(db.Model):
    __tablename__='notes'
    id=db.Column(db.Integer,primary_key=True)
    status=db.Column(db.Integer)
    message=db.Column(db.String(10))
    done=db.Column(db.Integer)
    #author=db.Column(db.String(20))
    content=db.Column(db.String(50))
    birth=db.Column(db.DateTime)
    deadline=db.Column(db.DateTime)
    lastchangetime=db.Column(db.DateTime)
    user_id=db.Column(db.Integer,db.ForeignKey('users.id'))
#身份模型
class Role(db.Model):
    __tablename__='roles'
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(16),unique=True)#事先录入，包括1、管理员，2、普通用户
    #关系引用,users给自己（Role模型）用，role给user模型用
    users=db.relationship('User',backref='role')
#用户模型
class User(db.Model):
    __tablename__='users'
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(16),unique=True)
    password=db.Column(db.String(18),)
    role_id=db.Column(db.Integer,db.ForeignKey('roles.id'))#代表身份丄
    notes=db.relationship('Note',backref='user')

def _notes():
    #roles=Role.query.all()
    notes=Note.query.all()
    list_out=[]
    if notes:
        for note in notes:
            note_out={
                'id':note.id,#唯一标识值
                'status':note.status,#0正常返回，非0错误返回
                'message':note.message,#错误信息
                'data':{
                    'done':note.done,#0为完成，非0完成
                    'content':note.content,#备忘录内容
                    'author':note.user.name,
                    'birth':note.birth,#创建时间
                    'deadline':note.deadline,#截止时间
                    'lastchangetime':note.lastchangetime#上次修改时间
                }
            }
            list_out.append(note_out)
    return list_out

def mynotes(name):
    user=User.query.filter_by(name=name).first()
    list_out=[]
    if user and user.notes:
        for note in user.notes:
            note_out={
                'id':note.id,#唯一标识值
                'status':note.status,#0正常返回，非0错误返回
                'message':note.message,#错误信息
                'data':{
                    'done':note.done,#0为完成，非0完成
                    'content':note.content,#备忘录内容
                    'author':note.user.name,
                    'birth':note.birth,#创建时间
                    'deadline':note.deadline,#截止时间
                    'lastchangetime':note.lastchangetime#上次修改时间
                }
            }
            list_out.append(note_out)
    return list_out   

def j(note):
    dict_out={
        'id':note.id,#唯一标识值
        'status':note.status,#0正常返回，非0错误返回
        'message':note.message,#错误信息
        'data':{
            'done':note.done,#0为完成，非0完成
            'content':note.content,#备忘录内容
            'author':note.user.name,
            'birth':note.birth,#创建时间
            'deadline':note.deadline,#截止时间
            'lastchangetime':note.lastchangetime#上次修改时间
                }
    }
    return dict_out

#删除表
db.drop_all()
#创建表，添加初始数据

db.create_all()
role1=Role(name='admin')
role2=Role(name='user')
db.session.add_all([role1,role2])
db.session.commit()

#管理员账户
user1=User(name='guanliyuanyihao',role_id=1,password='guanliyuanyihao')
user2=User(name='guanliyuanerhao',role_id=1,password='guanliyuanerhao')
user3=User(name='guanliyuansanhao',role_id=1,password='guanliyuansanhao')
db.session.add_all([user1,user2,user3])
db.session.commit()

app.config['SECRET_KEY']=os.urandom(24)   #设置为24位的字符,每次运行服务器都是不同的，所以服务器启动一次上次的session就清除
app.config['PERMANENT_SESSION_LIFETIME']=timedelta(days=7) #设置session的保存时间


def is_admin(func):
    #修饰器 在原修饰器下加 @is_admin
    @functools.wraps(func)
    def inner(*args,**kwargs):
        user = session.get('role')
        if user!='admin':
            return jsonify({'result': 'NOT ADMIN'}),403
        return func(*args,**kwargs)
    return inner

def is_login(func):
    #修饰器 在原修饰器下加 @is_login
    @functools.wraps(func)
    def inner(*args,**kwargs):
        user = session.get('username')
        if not user:
            return jsonify({'result': 'NOT USER'}),403
        return func(*args,**kwargs)
    return inner

#获取所有事项
@app.route('/notebook/api/v1/notes/show/', methods=['GET'])
@app.route('/notebook/api/v1/notes/', methods=['GET'])
@app.route('/notebook/api/v1/notes/show', methods=['GET'])
@app.route('/notebook/api/v1/notes', methods=['GET'])
@is_login
def show_all():
    if session['role']=='admin':
        #身份为管理员输出全部，否则输出自己的
        return jsonify({'notes': _notes()})
    else:
        show_list=mynotes(session['username'])#用于展示的列表
        return jsonify({'notes': show_list})

#更新所有事项(输入0全未完成，输入1全完成)
@app.route('/notebook/api/v1/notes/update/require:<int:done>', methods=['PUT'])
@app.route('/notebook/api/v1/notes/require:<int:done>', methods=['PUT'])
@app.route('/notebook/api/v1/notes/update/require:<int:done>/', methods=['PUT'])
@app.route('/notebook/api/v1/notes/require:<int:done>/', methods=['PUT'])
@is_login
def updata_state_all(done):
    if session['role']=='admin':
        notes=Note.query.all()
        if done==0:
            for note in notes:
                #note['data']['done']=0
                note.done = 0
                note.lastchangetime=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                db.session.commit()
        else:
            for note in notes:
                #note['data']['done']=0
                note.done = 1
                note.lastchangetime=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                db.session.commit()
        return jsonify({'notes':_notes()})
    else:
        notes=Note.query.all()
        if done==0:
            for note in notes:
                #if note['data']['author']==session['username']:
                if note.user.name==session['username']:
                    #note['data']['done']=0
                    #show_list.append(note)
                    note.done=0
                    note.lastchangetime=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    db.session.commit()
        else:
            for note in notes:
                if note.user.name==session['username']:
                    note.done=1
                    note.lastchangetime=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    db.session.commit()
        return jsonify({'notes':mynotes(session['username'])})
    
#删除所有事项
@app.route('/notebook/api/v1/notes/delete/', methods=['DELETE'])
@app.route('/notebook/api/v1/notes/', methods=['DELETE'])
@app.route('/notebook/api/v1/notes/delete', methods=['DELETE'])
@app.route('/notebook/api/v1/notes', methods=['DELETE'])
@is_login
def delete_all():
    if session['role']=='admin':
        show_list=_notes()
        notes=Note.query.all()
        for note in notes:
            db.session.delete(note)
            db.session.commit()
        return jsonify({'notes':show_list})
    else:
        show_list=mynotes(session['username'])
        notes=Note.query.all()
        for note in notes:
            if session['username']==note.user.name:
                db.session.delete(note)
                db.session.commit()
        return jsonify({'notes':show_list})

#按id搜索事项
@app.route('/notebook/api/v1/notes/show/<int:id>', methods=['GET'])
@app.route('/notebook/api/v1/notes/<int:id>', methods=['GET'])
@app.route('/notebook/api/v1/notes/show/<int:id>/', methods=['GET'])
@app.route('/notebook/api/v1/notes/<int:id>/', methods=['GET'])
def show_id(id):
    #for note in notes:
    #    if note['id']==id:
    #        return jsonify({'note': note})
    note=Note.query.filter_by(id=id).first()
    if note:
        note_out={
            'id':note.id,#唯一标识值
            'status':note.status,#0正常返回，非0错误返回
            'message':note.message,#错误信息
            'data':{
                'done':note.done,#0为完成，非0完成
                'content':note.content,#备忘录内容
                'author':note.user.name,
                'birth':note.birth,#创建时间
                'deadline':note.deadline,#截止时间
                'lastchangetime':note.lastchangetime#上次修改时间
            }
        }
        return jsonify({'notes':note_out})
    return jsonify({'result': 'NO FOUND'}),404

#按id状态更新事项
@app.route('/notebook/api/v1/notes/update/<int:id>/require:<int:done>', methods=['PUT'])
@app.route('/notebook/api/v1/notes/<int:id>/require:<int:done>', methods=['PUT'])
@app.route('/notebook/api/v1/notes/update/<int:id>/require:<int:done>/', methods=['PUT'])
@app.route('/notebook/api/v1/notes/<int:id>/require:<int:done>/', methods=['PUT'])
@is_login
def updata_state_id(id,done): 
    note=Note.query.filter_by(id=id).first()
    if note:
        if session['role']=='admin' or session['username']==note.user.name:
            if done==0:
                note.done=0
            else:
                note.done=1
            note.lastchangetime=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            db.session.commit()
            return jsonify({'notes':j(note)})
        else:
            return jsonify({'result': 'NOT ADMIN'}),403
    else:
        return jsonify({'result': 'NO FOUND'}),404

#按id删除
@app.route('/notebook/api/v1/notes/delete/<int:id>', methods=['DELETE'])
@app.route('/notebook/api/v1/notes/<int:id>', methods=['DELETE'])
@app.route('/notebook/api/v1/notes/delete/<int:id>/', methods=['DELETE'])
@app.route('/notebook/api/v1/notes/<int:id>/', methods=['DELETE'])
@is_login
def delete_id(id):
    note=Note.query.filter_by(id=id).first()
    if note:
        note_out=j(note)
        if session['role']=='admin' or session['username']==note.user.name:
            db.session.delete(note)
            db.session.commit()
            return jsonify({'notes':note_out})
        else:
            return jsonify({'result': 'NOT ADMIN'}),403
    else:
        return jsonify({'result': 'NO FOUND'}),404



#获取特定事项(发送0返回未完成，发送非0返回完成)
@app.route('/notebook/api/v1/notes/show/require:<int:done>', methods=['GET'])
@app.route('/notebook/api/v1/notes/require:<int:done>', methods=['GET'])
@app.route('/notebook/api/v1/notes/show/require:<int:done>/', methods=['GET'])
@app.route('/notebook/api/v1/notes/require:<int:done>/', methods=['GET'])
@is_login
def show_need(done):
    if session['role']=='admin':
        if done==0:
            #0为未完成
            unfinished_list=[]
            notes=Note.query.all()
            for note in notes:
                if note.done==0:
                    unfinished_list.append(j(note))
            return jsonify({'notes': unfinished_list})
        else:
            #非0完成
            finished_list=[]
            notes=Note.query.all()
            for note in notes:
                if note.done!=0:
                    finished_list.append(j(note))
            return jsonify({'notes': finished_list})
    else:
        if done==0:
            #非0完成
            finished_list=[]
            notes=Note.query.all()
            for note in notes:
                if note.done==0 and note.user.name==session['username']:
                    finished_list.append(j(note))
            return jsonify({'notes': finished_list})
        else:
            #非0完成
            finished_list=[]
            notes=Note.query.all()
            for note in notes:
                if note.done!=0 and note.user.name==session['username']:
                    finished_list.append(j(note))
            return jsonify({'notes': finished_list})
    return jsonify({'result': 'SOMETHING WRONG'}),400

#删除特定事项(发送0返回未完成，发送非0返回完成)
@app.route('/notebook/api/v1/notes/delete/require:<int:done>', methods=['DELETE'])
@app.route('/notebook/api/v1/notes/require:<int:done>', methods=['DELETE'])
@app.route('/notebook/api/v1/notes/delete/require:<int:done>/', methods=['DELETE'])
@app.route('/notebook/api/v1/notes/require:<int:done>/', methods=['DELETE'])
@is_login
def delete_need(done):
    if done!=0 or done!=1:
        done=1
    show_list=[]
    if session['role']=='admin':
        notes=Note.query.all()
        for note in notes:
            if done==note.done:
                show_list.append(j(note))
                db.session.delete(note)
                db.session.commit()
                
        return jsonify({'notes':show_list})
    else:
        notes=Note.query.all()
        for note in notes:
            if session['username']==note.user.name and done==note.done:
                show_list.append(j(note))
                db.session.delete(note)
                db.session.commit()
        return jsonify({'notes':show_list})

#获取所有数量
@app.route('/notebook/api/v1/notes/sum/', methods=['GET'])
@app.route('/notebook/api/v1/notes/sum', methods=['GET'])
@is_login
def sum_all():
    notes=Note.query.all()
    if session['role']=='admin':
        return jsonify({'sum': len(notes)})
    else:
        sum=0
        for note in notes:
            if session['username']==note.user.name:
                sum+=1
        return jsonify({'sum': sum})

#获取特定数量
@app.route('/notebook/api/v1/notes/sum/require:<int:done>', methods=['GET'])
@app.route('/notebook/api/v1/notes/sum/require:<int:done>/', methods=['GET'])
@is_login
def sum_need(done):
    #notes=Note.query.all()
    if session['role']=='admin':
        notes=_notes()
    else:
        notes=mynotes(session['username'])
    done_sum=0
    will_sum=0
    for note in notes:
        if note['data']['done']!=0:
            done_sum+=1
        else:
            will_sum+=1
    if done==0:
        return jsonify({'sum': will_sum})
    else:
        return jsonify({'sum': done_sum})

#添加一条新的待办事项(POST)
@app.route('/notebook/api/v1/notes/upload/', methods=['POST'])
@app.route('/notebook/api/v1/notes/', methods=['POST'])
@app.route('/notebook/api/v1/notes/upload', methods=['POST'])
@app.route('/notebook/api/v1/notes', methods=['POST'])
@is_login
def add_new():
    if not request.form or not 'content' in request.form or not 'deadline' in request.form:
        note={
            'status':1,
            'message':'INCOMPLETE INFORMATION'
        }
        return jsonify({'notes': note}), 400
    else:
        #print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        result=redatetime(request.form['deadline'])
        '''
        if len(notes)==0:
            id=0
        else:
            id=notes[-1]['id'] + 1
        '''

        if result and result > datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'):#输入时间通过验证且大于现在时间
            
            note_sql=Note(status=0,message='SUCCESS',done=0,content=request.form['content'],user_id=User.query.filter_by(name=session['username']).first().id,birth=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),lastchangetime=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),deadline=result)
            db.session.add(note_sql)
            db.session.commit()
            note = {
                'id': note_sql.id,
                'status':0,
                'message':'SUCCESS',
                'data':{
                    'done':0,#0为未完成，非0完成
                    'content':request.form['content'],#备忘录内容
                    'author':session['username'],
                    'birth':datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),#创建时间
                    'deadline':result#截止时间
                }
            }
            return jsonify({'notes': note}), 201
        else:
            note={
                'status':1,
                'message':'WRONG DEADLINE'
            }
            return jsonify({'notes': note}), 400
            
#登陆
@app.route('/notebook/api/v1/notes/login/', methods=['POST'])
@app.route('/notebook/api/v1/notes/login', methods=['POST'])
def login():
    username=request.form['username']
    password=request.form['password']
    user=User.query.filter_by(name=username).first()
    if user:
        if password==user.password:
            session['username']=username
            session['role']=user.role.name
            user_out={
                'name':session['username'],
                'role':session['role']
            }
            return jsonify({'result': user_out})
        else:
            return jsonify({'result': 'MESSAGE WRONG'}),403
    else:
        return jsonify({'result': 'MESSAGE WRONG'}),403

#登出
@app.route('/notebook/api/v1/notes/loginout/', methods=['POST'])
@app.route('/notebook/api/v1/notes/loginout', methods=['POST'])
@is_login
def loginout():
    user_out={
        'name':session['username'],
        'role':session['role']
    }
    session.clear()
    return jsonify({'result': user_out})

#注册
@app.route('/notebook/api/v1/notes/register/', methods=['POST'])
@app.route('/notebook/api/v1/notes/register', methods=['POST'])
def register():
    if not request.form or not 'username' in request.form or not 'password' in request.form:
        return jsonify({'result':'INCOMPLETE INFORMATION' }), 400
    else:
        username=request.form['username']
        password=request.form['password'] 
        user=User.query.filter_by(name=username).first()
        if user:
            return jsonify({'result': 'REGISTED'}),403
        else:  
            #校验
            if repassword(password) and reusername(username):
                new_user=User(name=username,password=password,role_id=2)
                db.session.add(new_user)
                db.session.commit()
                session['username']=username
                session['role']='user'
                user_out={
                    'name':session['username'],
                    'role':session['role']
                }
                return jsonify({'result': user_out})
            else:
                return jsonify({'result': 'MESSAGE WRONG'}),403




if __name__ == '__main__':
    #app.run(host='0.0.0.0',port='8090')
    app.run()
