from flask import Flask,url_for,render_template,request,flash,session,redirect,url_for,Response
from flask_wtf import FlaskForm
from wtforms import StringField,PasswordField,SubmitField,SelectField,DateField,TextAreaField, FileField,DateTimeField
from wtforms.validators import DataRequired,EqualTo,Length,Regexp
from flask_sqlalchemy import SQLAlchemy
import pymysql 
import pylint_flask
from datetime import timedelta
import os,random,string
from flask_script import Manager
from PIL import Image # 导入处理图片的模块
from flask_cors import CORS
import functools
from functools import wraps
import time,threading
import json
import redis
from flask_redis import FlaskRedis
import datetime
import uuid
from flask_wtf.file import FileRequired  # 验证文件必传
from flask_wtf.file import FileAllowed  # 验证文件后缀名
import random




#----初始化数据---------------------------------------
app = Flask(__name__)
app.secret_key='lulubao'#flaskwtf用
app.config['SECRET_KEY']=os.urandom(24)   #设置为24位的字符,每次运行服务器都是不同的，所以服务器启动一次上次的session就清除
app.config['PERMANENT_SESSION_LIFETIME']=timedelta(days=7) #设置session的保存时间
#链接mysql
app.config['SQLALCHEMY_DATABASE_URI']='mysql://%s:%s@%s/%s'%('root','cjtbs','localhost:4036','flask_sql_demo')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS']=False
db=SQLAlchemy(app)
#链接redis，作为弹幕库
rd = redis.Redis(host='localhost', port=6379,db=0)
# 设置允许上传文件的类型
ALLOWD_EXTENSIONS = ['png']#允许图片类型
ALLOWDVIDEO_EXTENSIONS=['mp4']#允许视频类型
# 设置允许上传文件的大小
app.config['MAX_CONTENT_LENGTH'] = 1024*1024*512 # 512兆(视频)
# 上传路径
app.config['UPLOAD_DEST'] = os.path.join(os.getcwd(),'static\\upload')
manage = Manager(app)
#----------------------------------------------------








#-------修饰器(用于权限判断)-----------
def is_login(func):
    #修饰器 在原修饰器下加 @is_login 若无登录，则跳转至登录
    @functools.wraps(func)
    def inner(*args,**kwargs):
        user = session.get('username')
        if not user:
            return redirect('login')
        
        return func(*args,**kwargs)
    return inner

def back_login(func):
    #修饰器 在原修饰器下加 @is_login 若已登录，则跳转至首页
    @functools.wraps(func)
    def inner(*args,**kwargs):
        user = session.get('username')
        if user:
            return redirect('index')
        return func(*args,**kwargs)
    return inner

def admin_login(func):
    #修饰器 在原修饰器下加 @admin_login 若不是管理员，则跳转至首页
    @functools.wraps(func)
    def inner(*args,**kwargs):
        user = User.query.filter_by(name=session.get('username')).first()
        if user.role.name!='admin':
            return render_template('turn.html',message='用户该功能受限,即将返回主页',url='/index')
        return func(*args,**kwargs)
    return inner

def banuser(func):
    #修饰器 验证封号状态
    @functools.wraps(func)
    def inner(*args,**kwargs):
        user = User.query.filter_by(name=session.get('username')).first()
        if user.usermessage.bantime:
            if user.usermessage.bantime>datetime.datetime.now():
                return render_template('turn.html',message='用户该功能受限,即将返回主页',url='/index')
            else:
                user.usermessage.bantime=None
                db.session.commit()
                return func(*args,**kwargs)
        return func(*args,**kwargs)
    return inner
#-------------------------








#------函数库---------
#为新用户创建文件夹
def register_create(user_id):
    os.makedirs(os.getcwd()+ '/flask/static/upload/%d'%user_id)
    os.makedirs(os.getcwd()+ '/flask/static/upload/%d/head'%user_id)
    os.makedirs(os.getcwd()+ '/flask/static/upload/%d/smallhead'%user_id)
    os.makedirs(os.getcwd()+ '/flask/static/upload/%d/video'%user_id)
    os.makedirs(os.getcwd()+ '/flask/static/upload/%d/face'%user_id)

# 判断上传的文件类型是否允许上传
def allowed_file(perfix):
    #图片
    return perfix in ALLOWD_EXTENSIONS
def allowed_video(perfix):
    #视频
    return perfix in ALLOWDVIDEO_EXTENSIONS

# 生成随机文件的名称
def random_name(perfix,length=16):
    # 生成a-z 0-9 A-Z
    str = string.ascii_letters + string.digits
    return ''.join(random.sample(str, length))+'.'+perfix

#头像缩放+保存
def img_zoom(path,prefix,width=200,heigth=200):
    # 执行图片缩放，取出图片
    img = Image.open(path)
    # print(img.size)  # 获取图片宽高
    # thumbnial 缩放的意思
    img.thumbnail((width, heigth))
    pathTup = os.path.split(path)
    
    
    if prefix=='_m':
        path = os.path.join(pathTup[0],'head/',prefix+pathTup[1])
    elif prefix=='_s':
        path = os.path.join(pathTup[0],'smallhead/',prefix+pathTup[1])

    img.save(path)

#------------------









#-----定义FlaskWTF类-----
#修改密码类
class ChangeForm(FlaskForm):
    #不用用户名
    #username=StringField(u'用 户 名：',validators=[DataRequired()])
    password0=PasswordField(u'原 密 码：',validators=[DataRequired()])
    password=PasswordField(u'新 密 码：',validators=[DataRequired(),Regexp(r"^[a-zA-Z]\w{5,17}$",message="密码以字母开头，长度在6~18之间，只能包含字母、数字和下划线")])
    password2=PasswordField(u'确认密码：',validators=[DataRequired(),EqualTo('password',message='两次密码不一样')])
    submit=SubmitField(u'修改')
#登录类
class LoginForm(FlaskForm):
    username=StringField(u'用户名：',validators=[DataRequired()])
    password=PasswordField(u'密  码：',validators=[DataRequired()])
    submit=SubmitField(u'登录')
#个人资料类
class DataForm(FlaskForm):
    sex=SelectField(u'性别：',render_kw={'class':'form-control'},choices=[('保密','保密'),('男','男'),('女','女')],default="保密",coerce=str)
    birthday=DateField(u'生日：',render_kw={"id":"date",'placeholder':"请选择日期","type":"text","class":"form-control"})
    signature=TextAreaField(u'个性签名：',validators=[Length(min=0,max=30,message=u'个性签名过长')])
    submit=SubmitField(u'修改')
#注册类
class RegisterForm(FlaskForm):
    #帐号是否合法(字母开头，允许5-16字节，允许字母数字下划线)：^[a-zA-Z][a-zA-Z0-9_]{4,15}$
    #密码(以字母开头，长度在6~18之间，只能包含字母、数字和下划线)：^[a-zA-Z]\w{5,17}$
    #强密码(必须包含大小写字母和数字的组合，不能使用特殊字符，长度在 8-10 之间)：^(?=.*\d)(?=.*[a-z])(?=.*[A-Z])[a-zA-Z0-9]{8,10}$
    #强密码(必须包含大小写字母和数字的组合，可以使用特殊字符，长度在8-10之间)：^(?=.*\d)(?=.*[a-z])(?=.*[A-Z]).{8,10}$ 
    username=StringField(u'用 户 名：',validators=[DataRequired(),Regexp(r"^[a-zA-Z][a-zA-Z0-9_]{4,15}$",message="帐号字母开头，允许5-16字节，允许字母数字下划线")])
    password=PasswordField(u'密    码：',validators=[DataRequired(),Regexp(r"^[a-zA-Z]\w{5,17}$",message="密码以字母开头，长度在6~18之间，只能包含字母、数字和下划线")])
    password2=PasswordField(u'确认密码：',validators=[DataRequired(),EqualTo('password',message='两次密码不一样')])
    sex=SelectField(u'性别：',render_kw={'class':'form-control'},choices=[('保密','保密'),('男','男'),('女','女')],default="保密",coerce=str)
    signature=TextAreaField(u'个性签名：',validators=[Length(min=0,max=30,message=u'个性签名过长')])
    submit=SubmitField(u'注册')
#视频信息类
class VideoForm(FlaskForm):
    name=StringField(u'视频名称：',validators=[DataRequired(),Length(min=4,max=16,message=u'视频名称长度应在4-16字节')])
    lable=TextAreaField(u'简介：',validators=[Length(min=0,max=100,message=u'简历长度不能超过100字节')])
    style_id=SelectField(u'视频类别：',render_kw={'class':'form-control'},choices=[(1,'动画'),(2,'音乐'),(3,'舞蹈'),(4,'科技'),(5,'生活'),(6,'时尚'),(7,'娱乐'),(8,'番剧'),(9,'国创'),(10,'游戏'),(11,'数据'),(12,'鬼畜'),(13,'广告'),(14,'影视')],default="0",coerce=int)
    video=FileField(u'视频文件：',validators=[FileRequired(message=u'请上传视频！'), FileAllowed(['mp4'], message='文件格式错误')],description=u'视频文件')
    face=FileField(u'封面文件：',validators=[FileRequired(message=u'请上传封面！'), FileAllowed(['png'], message='文件格式错误')],description=u'封面文件')
    submit=SubmitField(u'提交')
#封号类
class BanForm(FlaskForm):
    username=StringField(u'用户名：',validators=[DataRequired()])
    bantime=DateTimeField(u'封号至：',render_kw={"id":"datetime",'placeholder':"请选择日期","type":"text","class":"form-control"})
    submit=SubmitField(u'封号')
#----------------------









#----mysql数据库模型构建-----
#视频标签模型
class Style(db.Model):
    __tablename__='styles'
    id=db.Column(db.Integer,primary_key=True)
    content=db.Column(db.String(10))
    videos=db.relationship('Videomessage',backref='style')
#视频信息模型
class Videomessage(db.Model):
    __tablename__='videomessages'
    id=db.Column(db.Integer,primary_key=True)
    user_id=db.Column(db.Integer,db.ForeignKey('users.id'))
    name=db.Column(db.String(100))
    address=db.Column(db.String(100))#内容地址
    face=db.Column(db.String(100))#封面地址
    birthday=db.Column(db.DateTime)
    like=db.Column(db.Integer)
    dislike=db.Column(db.Integer)
    collect=db.Column(db.Integer)
    lable=db.Column(db.String(100))
    style_id=db.Column(db.Integer,db.ForeignKey('styles.id'))
    comments=db.relationship('Comment',backref='videomessage')
    collects=db.relationship('Collect',backref='videomessage')
    likes=db.relationship('Like',backref='videomessage')
    dislikes=db.relationship('Dislike',backref='videomessage')
#评论模型
class Comment(db.Model):
    __tablename__='comments'
    id=db.Column(db.Integer,primary_key=True)
    user_id=db.Column(db.Integer,db.ForeignKey('users.id'))
    video_id=db.Column(db.Integer,db.ForeignKey('videomessages.id'))
    like=db.Column(db.Integer)
    dislike=db.Column(db.Integer)
    reply=db.Column(db.String(18))#被回复人
    reply_id=db.Column(db.Integer)
    content=db.Column(db.String(100))
    birthday=db.Column(db.DateTime)
#收藏模型
class Collect(db.Model):
    __tablename__='collects'
    id=db.Column(db.Integer,primary_key=True)
    user_id=db.Column(db.Integer,db.ForeignKey('users.id'))
    video_id=db.Column(db.Integer,db.ForeignKey('videomessages.id'))
#用户信息模型
class Usermessage(db.Model):
    __tablename__='usermessages'
    id=db.Column(db.Integer,db.ForeignKey('users.id'),primary_key=True)
    head=db.Column(db.String(100))
    smallhead=db.Column(db.String(100))
    signature=db.Column(db.String(30))
    sex=db.Column(db.String(4))
    bantime=db.Column(db.DateTime)
    birthday=db.Column(db.Date)
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
    usermessage=db.relationship('Usermessage',uselist=False,backref='user')
    comments=db.relationship('Comment',backref='user')
    videos=db.relationship('Videomessage',backref='user')
    collects=db.relationship('Collect',backref='user')
    likes=db.relationship('Like',backref='user')
    dislikes=db.relationship('Dislike',backref='user')
#赞模型
class Like(db.Model):
    __tablename__='likes'
    id=db.Column(db.Integer,primary_key=True)
    user_id=db.Column(db.Integer,db.ForeignKey('users.id'))
    video_id=db.Column(db.Integer,db.ForeignKey('videomessages.id'))
#踩模型
class Dislike(db.Model):
    __tablename__='dislikes'
    id=db.Column(db.Integer,primary_key=True)
    user_id=db.Column(db.Integer,db.ForeignKey('users.id'))
    video_id=db.Column(db.Integer,db.ForeignKey('videomessages.id'))
#--------------------------










#------界面显示类型----------------------

@app.route('/index',methods=['GET','POST'])
#主界面
def index():
    if request.method=='GET':
        activity=False
        if session.get('username'):
            user = User.query.filter_by(name=session.get('username')).first()
            activity=True
            session['activity']=True
            session['message_id']=user.usermessage.id
            session['message_head']=user.usermessage.head
            session['message_smallhead']=user.usermessage.smallhead
            session['message_signature']=user.usermessage.signature
            session['message_sex']=user.usermessage.sex
            session['message_bantime']=user.usermessage.bantime
            session['message_birthday']=user.usermessage.birthday
            return render_template('homepage.html',activity=activity)
        return render_template('homepage.html',activity=activity)
    if request.method=='POST':
        search_content=request.form.get('search')
        if search_content:
            return redirect(url_for('search',content=search_content))
        else:
            return redirect(url_for('index'))

@app.route('/search/content=<string:content>',methods=['GET','POST'])
#搜索界面
def search(content):
    if request.method=='POST':
        search_content=request.form.get('search')
        if search_content:
            return redirect(url_for('search',content=search_content))
        else:
            return redirect(url_for('index'))
    videos=Videomessage.query.all()
    result=[]
    for video in videos:
        if content in video.name:
            if video not in result:
                result.append(video)
        if content in video.style.content:
            if video not in result:
                result.append(video)
        if content in video.lable:
            if video not in result:
                result.append(video)
        if content in video.user.name:
            if video not in result:
                result.append(video)
    return render_template('search.html',videos=result,content=content)

@app.route('/myself')
@is_login
#个人界面
def person():
    if session['username']:
        user = User.query.filter_by(name=session.get('username')).first()
        message={
            'head':user.usermessage.head,
            'signature':user.usermessage.signature,
            'sex':user.usermessage.sex,
            'bantime':user.usermessage.bantime,
        }
        birthday=user.usermessage.birthday
        if birthday:
            message['birthday']=birthday.strftime("%Y-%m-%d")
        else:
            message['birthday']='保密'
        if user.role.name=='admin':
            #进入管理员模式
            roles=Role.query.all()
            return render_template('myself.html',role_name='admin',message=message,user_name=user.name,user=user)
        return render_template('myself.html',role_name='user',message=message,user_name=user.name,user=user)

@app.route('/other/<id>')
#他人信息界面
def other(id):
    user=User.query.get(id)
    if user:
        message={
            'head':user.usermessage.head,
            'signature':user.usermessage.signature,
            'sex':user.usermessage.sex,
            'bantime':user.usermessage.bantime,
        }
        birthday=user.usermessage.birthday
        if birthday:
            message['birthday']=birthday.strftime("%Y-%m-%d")
        else:
            message['birthday']='保密'
        user_name=user.name
        logining_user = session.get('username')
        if logining_user:
            activity=True
        else:
            activity=False
        return render_template('other.html',role_name='user',message=message,user_name=user_name,activity=activity,user=user)
    else:
        return render_template('turn.html',message='该用户不存在,即将返回主页',url='/index')

@app.route('/login',methods=['GET','POST'])
@back_login
#登录界面
def login():
    form=LoginForm()
    if form.validate_on_submit():
        username=form.username.data
        password=form.password.data
        user=User.query.filter_by(name=username).first()
        if user:
            if password==user.password:
                session['username'] = username
                session['password'] = password
                session['activity']=True
                session['message_id']=user.usermessage.id
                session['message_head']=user.usermessage.head
                session['message_smallhead']=user.usermessage.smallhead
                session['message_signature']=user.usermessage.signature
                session['message_sex']=user.usermessage.sex
                session['message_bantime']=user.usermessage.bantime
                session['message_birthday']=user.usermessage.birthday
                return redirect(url_for('index'))
            else:
                flash(u'密码错误')
        else:
            flash(u'用户不存在')
    else:
        if request.method=='POST':
            flash(u'参数不全')

    return render_template('login.html',form=form)

@app.route('/register',methods=['GET','POST'])
@back_login
#注册界面
def register():
    form=RegisterForm()
    if form.validate_on_submit():
        username=form.username.data
        password=form.password.data
        password2=form.password2.data
        user=User.query.filter_by(name=username).first()
        if user:
            flash('用户名已被注册')
        else:
            if password==password2:
                
                try:
                    #生成并添加用户数据
                    new_user=User(name=username,role_id=2,password=password)
                    db.session.add(new_user)
                    db.session.commit()
                    
                    #生成用户资料
                    sex=form.sex.data
                    signature=form.signature.data
                    new_user_message=Usermessage(id=new_user.id,sex=sex,signature=signature,head="/static/head.png",smallhead="/static/smallhead.png")
                    db.session.add(new_user_message)
                    db.session.commit()
                    
                    #创建用户文件夹
                    register_create(new_user.id)

                    session['username'] = username
                    session['password'] = password
                    session['activity']=True
                    session['message_id']=new_user_message.id
                    session['message_head']=new_user_message.head
                    session['message_smallhead']=new_user_message.smallhead
                    session['message_signature']=new_user_message.signature
                    session['message_sex']=new_user_message.sex
                    session['message_bantime']=new_user_message.bantime
                    session['message_birthday']=new_user_message.birthday
                    return render_template('turn.html',message='注册成功，即将返回主界面',url='/index')
                except Exception as e:
                    print(e)
                    flash('注册失败')
                    db.session.rollback()
            else:
                #flash(u'前后密码不一致')
                pass
    else:
        if request.method=='POST':
            #flash(u'输入不规范')
            pass
    
    return render_template('register.html',form=form)

@app.route('/upload/?<string:id>',methods=['GET','POST'])
@is_login
@banuser
#视频上传
def upload(id):
    if session['username']==User.query.get(id).name:
        filename = None
        form=VideoForm()
        if form.validate_on_submit():
            print('success')
            #if request.method == 'POST' and 'file' in request.files and 'face' in request.files:
            name=form.name.data
            lable=form.lable.data
            style_id=form.style_id.data
            if True:    
                #这个file是face
                #file = request.files.get('face')
                file=form.face.data
                print(file.filename)
                filename = file.filename
                perfix = filename.split('.')[-1]#取后缀
                if allowed_file(perfix):
                    #这个file是video
                    #file = request.files.get('file')
                    file=form.video.data
                    print(file.filename)
                    filename = file.filename
                    perfix = filename.split('.')[-1]#取后缀
                    if allowed_video(perfix):
                        
                        user=User.query.get(id)
                        id=session.get('message_id')
                        #保存视频文件
                        UPLOAD_FOLDER = ('flask/static/upload/%s/video'%id)#视频根目录
                        file_dir = os.path.join(os.getcwd(), UPLOAD_FOLDER)
                        file.filename=random_name(perfix)
                        file_path = os.path.join(file_dir, file.filename)
                        file.save(file_path)
                        video_address='/static/upload/'+str(id)+'/video/'+file.filename
                        
                        #切换封面文件
                        #file = request.files.get('face')
                        file=form.face.data
                        print(file.filename)
                        filename = file.filename
                        perfix = filename.split('.')[-1]#取后缀
                        #保存封面文件
                        UPLOAD_FOLDER = ('flask/static/upload/%s/face'%id)#封面根目录
                        file_dir = os.path.join(os.getcwd(), UPLOAD_FOLDER)
                        file.filename=random_name(perfix)
                        file_path = os.path.join(file_dir, file.filename)
                        file.save(file_path)
                        face_address='/static/upload/'+str(id)+'/face/'+file.filename

                        #提交新视频
                        new_video=Videomessage(name=name,user_id=user.id,address=video_address,face=face_address,like=0,dislike=0,collect=0,style_id=style_id,lable=lable,birthday=datetime.datetime.now())
                        db.session.add(new_video)
                        db.session.commit()
                        return render_template('turn.html',message='视频上传成功，即将返回主界面',url='/index')
                    else:
                        flash(u'视频文件类型不允许')
                else:
                    flash(u'封面文件类型不允许')
                    ''''''
        else:
            #flash(u'标题、标签长度应在6-30字符之间，且必填')
            if request.method=='POST':
                #print(form.name.data)
                #print(form.face.data)
                print(form.data)
                flash(u'有误')
        return render_template('video_upload.html',filename=filename,form=form)

@app.route('/change/?<string:id>',methods=['GET','POST'])
@is_login
#密码修改界面
def change(id):
    if session['username']==User.query.get(id).name:
        user=User.query.get(id)
        form=ChangeForm()
        if form.validate_on_submit():
            password0=form.password0.data#p0原密码
            password=form.password.data#p新密码
            password2=form.password2.data#p2确认密码
            if user:
                if user.password==password0:
                    if password==password2:
                        if password==user.password:
                            flash('新旧密码不能一致')
                        else:
                            user.password=password
                            db.session.commit()
                            return render_template('turn.html',message='密码修改成功，即将返回主界面',url='/index')
                    else:
                        flash('两次密码不一致')
                else:
                    flash(u'原密码错误')
            else:
                flash(u'用户不存在')
        else:
            if request.method=='POST':
                #flash(u'输入不规范')
                pass
        return render_template('change.html',form=form,username=session['username'])
    else:
        return redirect(url_for('index'))

@app.route('/video/<int:id>/page=<int:p>',methods=['GET','POST'])
#视频播放
def video(id,p):
    if request.method=='POST':
        pass
    else:
        video=Videomessage.query.filter_by(id=id).first()
        if video:
            try:
                video_message={
                    'video':video.address,
                    'id':id,
                    'face':video.face,
                    'name':video.name,
                    'api':'/dm/',
                    'lable':video.lable,
                    'like':video.like,
                    'dislike':video.dislike,
                    'collect':video.collect,
                    'author':video.user.name,
                    'style':video.style.content,
                    'birthday':video.birthday.strftime("%Y-%m-%d %H:%M:%S"),
                    'head':video.user.usermessage.smallhead,
                    'space':'/other/'+str(video.user.id),
                    'signature':video.user.usermessage.signature
                }
                num=len(video.comments)
                maxp=num//10+1
                if p>maxp:
                    p=maxp
                    return redirect(url_for('video',id=id,p=maxp))
                if p<1:
                    p=1
                    return redirect(url_for('video',id=id,p=1))
                if session.get('username'):
                    user=User.query.filter_by(name=session['username']).first()
                    if num==0:
                        if user.role.name=='admin':
                            return render_template('video.html',video_message=video_message,user=user,logining=True,num=num,p=p,maxp=maxp,role='admin')
                        else:
                            return render_template('video.html',video_message=video_message,user=user,logining=True,num=num,p=p,maxp=maxp,role='user')
                    else:
                        if user.role.name=='admin':
                            return render_template('video.html',video_message=video_message,user=user,logining=True,num=num,comments=video.comments,p=p,maxp=maxp,role='admin')
                        else:
                            return render_template('video.html',video_message=video_message,user=user,logining=True,num=num,comments=video.comments,p=p,maxp=maxp,role='user')
                if num==0:
                    return render_template('video.html',video_message=video_message,logining=False,num=num,p=p,maxp=maxp,role='unlogin')
                else:
                    return render_template('video.html',video_message=video_message,logining=False,num=num,comments=video.comments,p=p,maxp=maxp,role='unlogin')
            except Exception as e:
                print(e)
                return render_template('turn.html',message='视频参数不全，已取消播放，即将返回主界面',url='/index') 
        else:
            return render_template('404video.html')

@app.route('/changehead/?<string:id>',methods=['GET','POST'])
@is_login
#头像修改界面
def changehead(id):
    if session['username']==User.query.get(id).name:
        filename = None
        if request.method == 'POST' and 'file' in request.files:
            file = request.files.get('file')
            print(file.filename)
            filename = file.filename
            perfix = filename.split('.')[-1]#取后缀
            if allowed_file(perfix):
                # 判断头像类型（只能png）
                user=User.query.get(id)
                id=session.get('message_id')
                UPLOAD_FOLDER = ('flask/static/upload/%s'%id)#视频根目录
                file_dir = os.path.join(os.getcwd(), UPLOAD_FOLDER)
                file.filename=random_name(perfix)
                file_path = os.path.join(file_dir, file.filename)
                file.save(file_path)
                img_zoom(file_path,'_s',100,100)
                img_zoom(file_path,'_m')
                user.usermessage.head='/static/upload/'+str(id)+'/head/'+'_m'+file.filename
                user.usermessage.smallhead='/static/upload/'+str(id)+'/smallhead/'+'_s'+file.filename
                db.session.commit()
                #return redirect(url_for('person'))
                #task.fileName = file.filename
                session['message_head']=user.usermessage.head
                session['message_smallhead']=user.usermessage.smallhead
                return redirect(url_for('person'))
            else:
                flash('该文件类型不允许')
        return render_template('head_upload.html',filename=filename)

@app.route('/changedata/?<string:id>',methods=['GET','POST'])
@is_login
#个人资料修改界面
def changedata(id):
    if session['username']==User.query.get(id).name:
        form=DataForm()
        if form.validate_on_submit():
            #生成并添加用户数据
            user=User.query.get(id)
            user.usermessage.sex=form.sex.data
            user.usermessage.signature=form.signature.data
            if form.birthday.data:
                user.usermessage.birthday=form.birthday.data
            db.session.commit()
            session['message_signature']=user.usermessage.signature
            session['message_sex']=user.usermessage.sex
            if form.birthday.data:
                session['message_birthday']=user.usermessage.birthday
            return redirect(url_for('person'))
        else:
            if request.method=='POST':
                flash(u'错误')
    else:
        return redirect(url_for('index'))
    return render_template('data_change.html',form=form)

@app.route('/admin',methods=["GET","POST"])
@is_login
@admin_login
#管理员操作界面
def admin():
    form=BanForm()
    if request.method=='POST':
        if form.validate_on_submit():
            username=form.username.data
            bantime=form.bantime.data
            user=User.query.filter_by(name=username).first()
            if user:
                user.usermessage.bantime=bantime
                db.session.commit()
                flash(u'封号成功')
                return render_template('turn.html',message='封号成功，即将返回管理员界面',url='/admin') 
            else:
                flash(u'用户不存在')
                return render_template('turn.html',message='该用户不存在,封号失败，即将返回管理员界面',url='/admin') 
        else:
            flash(u'格式有误')
            return redirect(url_for('admin'))
    if request.method=='GET':
        admin=Role.query.first().users
        user_name=session['username']
        for user in admin:
            if user.name==session['username']:
                #进入管理员模式
                roles=Role.query.all()
                styles=Style.query.all()
                return render_template('admin.html',roles=roles,role_name='admin',user_name=user_name,styles=styles,form=form)

#-----------------------------------











#-------功能类型---------------------

@app.route('/')
#主界面接引
def hello():
    return redirect(url_for('index'))

@app.errorhandler(404)
#404界面接引
def page_not_found(error):
    return render_template('turn.html',message="发生404错误，即将返回主界面",url='/index')

@app.route('/loginout')
@is_login
#登出界面
def loginout():
    session.clear()
    return render_template('turn.html',message='已退出登录，即将返回主界面',url='/index')

@app.route('/upload')
@is_login
@banuser
#上传界面中转
def turnupload():
    return redirect(url_for('upload',id=session.get('message_id')))

@app.route('/change')
@is_login
#密码修改界面中转
def turnchange():
    return redirect(url_for('change',id=session.get('message_id')))

@app.route('/video/<int:id>',methods=['GET','POST'])
#视频界面跳转（顺便加个页码）
def turnvideo(id):
    return redirect(url_for('video',id=id,p=1))

@app.route('/changehead')
@is_login
#头像修改界面中转
def turnchangehead():
    return redirect(url_for('changehead',id=session.get('message_id')))

@app.route('/changedata')
@is_login
#个人资料修改中转
def turnchangedata():
    return redirect(url_for('changedata',id=session.get('message_id')))

@app.route("/like/<int:id>", methods=["POST"])
#赞操作
def like(id):
    resp={"state":"wrong","message":"出现错误，操作不能执行","data":"0"}
    #1、判断是否登录
    if session.get('username'):
        video=Videomessage.query.filter_by(id=id).first()
        user=User.query.filter_by(name=session.get('username')).first()
        #2、是否已经点赞
        likes=user.likes
        for like in likes:
            if like.video_id==id:
                try:
                    video.like=video.like-1
                    db.session.delete(like)
                    db.session.commit()
                    resp['state']='success'
                    resp['message']='已取消赞'
                    resp['like']=str(video.like)
                    resp['dislike']=str(video.dislike)
                    return resp
                except Exception as e:
                    print(e)
                    db.session.rollback()
                    return resp

        #3、未赞，是否点踩
        dislikes=user.dislikes
        for dislike in dislikes:
            if dislike.videomessage.id==id:
                try:
                    video.dislike=video.dislike-1
                    db.session.delete(dislike)
                    db.session.commit()
                except Exception as e:
                    print(e)
                    db.session.rollback()
                    return resp
        try:
            new_like=Like(user_id=user.id,video_id=video.id)
            db.session.add(new_like)
            video.like=video.like+1
            db.session.commit()
            resp['state']='success'
            resp['message']='你赞了这个视频'
            resp['like']=str(video.like)
            resp['dislike']=str(video.dislike)
            return resp
        except Exception as e:
            print(e)
            db.session.rollback()
            return resp
    else:
        resp['message']='未登录，无法进行该操作'
        return resp

@app.route("/dislike/<int:id>", methods=["POST"])
#踩操作
def dislike(id):
    resp={"state":"wrong","message":"出现错误，操作不能执行","data":"0"}
    if session.get('username'):
        video=Videomessage.query.filter_by(id=id).first()
        user=User.query.filter_by(name=session.get('username')).first()
        dislikes=user.dislikes
        for dislike in dislikes:
            if dislike.video_id==id:
                try:
                    video.dislike=video.dislike-1
                    db.session.delete(dislike)
                    db.session.commit()
                    resp['state']='success'
                    resp['message']='已取消踩'
                    resp['like']=str(video.like)
                    resp['dislike']=str(video.dislike)
                    return resp
                except Exception as e:
                    print(e)
                    db.session.rollback()
                    return resp
        likes=user.likes
        for like in likes:
            if like.videomessage.id==id:
                try:
                    video.like=video.like-1
                    db.session.delete(like)
                    db.session.commit()
                except Exception as e:
                    print(e)
                    db.session.rollback()
                    return resp
        try:
            new_dislike=Dislike(user_id=user.id,video_id=video.id)
            db.session.add(new_dislike)
            video.dislike=video.dislike+1
            db.session.commit()
            resp['state']='success'
            resp['message']='你踩了这个视频'
            resp['like']=str(video.like)
            resp['dislike']=str(video.dislike)
            return resp
        except Exception as e:
            print(e)
            db.session.rollback()
            return resp
    else:
        resp['message']='未登录，无法进行该操作'
        return resp

@app.route("/collect/<int:id>", methods=["POST"])
#收藏操作
def collect(id):
    resp={"state":"wrong","message":"出现错误，操作不能执行","data":"0"}
    if session.get('username'):
        video=Videomessage.query.filter_by(id=id).first()
        user=User.query.filter_by(name=session.get('username')).first()
        collects=user.collects
        for collect in collects:
            if collect.video_id==id:
                try:
                    video.collect=video.collect-1
                    db.session.delete(collect)
                    db.session.commit()
                    resp['state']='success'
                    resp['message']='已取消收藏'
                    resp['data']=str(video.collect)
                    return resp
                except Exception as e:
                    print(e)
                    db.session.rollback()
                    return resp
        try:
            new_collect=Collect(user_id=user.id,video_id=video.id)
            db.session.add(new_collect)
            video.collect=video.collect+1
            db.session.commit()
            resp['state']='success'
            resp['message']='收藏成功'
            resp['data']=str(video.collect)
            return resp
        except Exception as e:
            print(e)
            db.session.rollback()
            return resp
    else:
        resp['message']='未登录，无法进行该操作'
        return resp

@app.route("/comment/<id>", methods=["POST"])
@banuser
#评论操作
def comment(id):
    if session.get('username'):
        comment=request.form.get('comment')
        if comment:
            try:
                new_comment=Comment(user_id=session.get('message_id'),video_id=id,reply=session.get('username'),reply_id=session.get('message_id'),content=comment,birthday=datetime.datetime.now(),like=0,dislike=0)
                db.session.add(new_comment)
                db.session.commit()
                return comment
            except Exception as e:
                print(e)
                db.session.rollback()
                return "wrong"
        else:
            return "no"
    else:
        return 'unlogin'

@app.route("/reply/<id>", methods=["POST"])
@banuser
#回复操作
def reply(id):
    if session.get('username'):
        comment=request.form.get('reply')
        reply_name=request.form.get('name')
        reply_id=request.form.get('id')
        if comment:
            try:
                new_comment=Comment(user_id=session.get('message_id'),video_id=id,reply=reply_name,reply_id=reply_id,content=comment,birthday=datetime.datetime.now(),like=0,dislike=0)
                db.session.add(new_comment)
                db.session.commit()
                return comment
            except Exception as e:
                print(e)
                db.session.rollback()
                return "wrong"
        else:
            return "no"
    else:
        return 'unlogin'

@app.route("/delete/<id>", methods=["POST"])
@admin_login
@banuser
#评论删除操作
def delete(id):
    if session.get('username'):
        delete_id=request.form.get('id')
        try:
            delete_comment=Comment.query.filter_by(id=delete_id).first()
            db.session.delete(delete_comment)
            db.session.commit()
            return "success"
        except Exception as e:
            print(e)
            db.session.rollback()
            return "wrong"
    else:
        return 'unlogin'

@app.route("/dm/v2/",methods=["GET","POST"])
#弹幕处理
def dm():
    if request.method=="GET":
        #获取弹幕消息队列
        mid = request.args.get("id")
        key="video"+str(mid)
        if rd.llen(key):
            msgs=rd.lrange(key,0,2999)
            res={
                "code":0,
                "danmaku":[json.loads(v) for v in msgs]
            }
        else:
            res={
                "code":1,
                "danmaku":[]
            }
        resp=json.dumps(res)
    if request.method=="POST":
        #添加弹幕
        data=json.loads(request.get_data())
        print(data)
        msg= {
        "__v": 0,
        "_id": datetime.datetime.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex,
        "author": data["author"],
        "time": data["time"],
        "text": data["text"],
        "color": data["color"],
        "type": data["type"],
        "ip": request.remote_addr,
        "player": [data["player"]],
        "referer":request.base_url
        }
        res = {
            "code": 0,
            "danmaku":msg,
            "msg":'发送成功'
        }
        resp=json.dumps(res)
        msg=[data["time"],data["type"],data["color"],data["author"],data["text"]]
        rd.lpush("video"+str(data["player"]),json.dumps(msg))
    return Response(resp,mimetype="application/json")

@app.route('/deletevideo',methods=["POST"])
@is_login
@admin_login
#视频删除操作
def deletevideo():
    if session.get('username'):
        delete_video_id=request.form.get('id')
        try:
            delete_video=Videomessage.query.filter_by(id=delete_video_id).first()
            for like in delete_video.likes:
                db.session.delete(like)
            for dislike in delete_video.dislikes:
                db.session.delete(dislike)
            for collect in delete_video.collects:
                db.session.delete(collect)
            for comment in delete_video.comments:
                db.session.delete(comment)
            db.session.delete(delete_video)

            db.session.commit()
            return "success"
        except Exception as e:
            print(e)
            db.session.rollback()
            return "wrong"
    else:
        return 'unlogin'

@app.route("/show",methods=["GET"])
#随机视频展示
def show():
    all_video = Videomessage.query.all()
    if all_video:
        i=random.randint(0,len(all_video)-1)
        video=all_video[i]
        resp={
            "name":video.name,
            "style":video.style.content,
            "user":video.user.name,
            "birthday":video.birthday.strftime("%Y-%m-%d %H:%M:%S"),
            "face":video.face,
            "id":video.id
        }
        return resp
    return 'null'

#-----------------------------------






'''

#-----初始化数据库（初始值已导入）-----------------------------------------

#删除表
db.drop_all()
#创建表，添加初始数据

db.create_all()
role1=Role(name='admin')
role2=Role(name='user')
db.session.add_all([role1,role2])
db.session.commit()
style1=Style(content='动画')
style2=Style(content='音乐')
style3=Style(content='舞蹈')
style4=Style(content='科技')
style5=Style(content='生活')
style6=Style(content='时尚')
style7=Style(content='娱乐')
style8=Style(content='番剧')
style9=Style(content='国创')
style10=Style(content='游戏')
style11=Style(content='数据')
style12=Style(content='鬼畜')
style13=Style(content='广告')
style14=Style(content='影视')
db.session.add_all([style1,style2,style3,style4,style5,style6,style7,style8,style9,style10,style11,style12,style13,style14])
db.session.commit()
#[(0,'动画'),(1,'音乐'),(2,'舞蹈'),(3,'科技'),(4,'生活'),(5,'时尚'),(6,'娱乐'),(7,'番剧'),(8,'国创'),(9,'游戏'),(10,'数据'),(11,'鬼畜'),(12,'广告'),(13,'影视')]
'''
'''
#管理员账户
user1=User(name='guanliyuanyihao',role_id=1,password='guanliyuanyihao')
user2=User(name='guanliyuanerhao',role_id=1,password='guanliyuanerhao')
user3=User(name='guanliyuansanhao',role_id=1,password='guanliyuansanhao')
db.session.add_all([user1,user2,user3])
db.session.commit()
#添加管理员信息
usermessage1=Usermessage(id=user1.id,signature='我是一号管理员',sex='男')
usermessage2=Usermessage(id=user2.id,signature='我是二号管理员',sex='女')
usermessage3=Usermessage(id=user3.id,signature='我是三号管理员',sex='未知')
db.session.add_all([usermessage1,usermessage2,usermessage3])
db.session.commit()


#注册文件夹（已事先注册）
#register_create(user1.id)
#register_create(user2.id)
#register_create(user3.id)

#--------------------------------------------------------------------------
'''



#------------------------------
if __name__=='__main__':
    #app.run(host='0.0.0.0',port='5000')
    app.run()
    #app.run(debug=True)
    #192.168.85.130:8090（本机域名）
#-------------------------------
