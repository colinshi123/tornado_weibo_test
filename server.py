import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import os.path
import time
import hashlib
import configparser
from pymongo import MongoClient
from bson.objectid import ObjectId
from tornado.options import define, options

info = configparser.ConfigParser()
info.read('config.ini')
server_port = info.get('info', 'server_port')
server_mongodb =  info.get('info','server_mongodb')
server_mongodb_port = info.get('info','server_mongodb_port')


define('port', default=server_port, help='run on the given port', type=int)

client = MongoClient(server_mongodb, int(server_mongodb_port))
db = client.colinshi

def md5(obj):
    m = hashlib.md5()   
    m.update(obj.encode('utf-8'))
    return m.hexdigest()

class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        if self.get_secure_cookie('user'):
            return self.get_secure_cookie('user').decode('utf-8')
        else:
            return self.get_secure_cookie('user')

class LoginHandler(BaseHandler):
    @tornado.web.asynchronous
    def get(self):
        self.render('login.html')

    def post(self):
        account = self.get_argument('account')
        password = self.get_argument('password')        
        if account == "" or password == "":
            self.write('<h1>账号密码不能为空</h1><ui><a href="/login">返回</a></ui>')
            #self.redirect('/login')
        elif db.user.count({'account':account,'password':md5(password)}) > 0:
            self.write('{0}登入成功'.format(account))
            self.set_secure_cookie('user',account)
            self.redirect('/')
        else:
            self.write('<h1>账号或者密码错误请重试</h1><ui><a href="/login">返回</a></ui>')
            #self.redirect('/login')
    
class WelcomeHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        weibo = db.weibo.find({'account':{'$ne':self.get_current_user()}}).sort([("td",-1)])
        self.render('index.html',**{'user':self.current_user,'weibo':weibo})

class LogoutHandler(BaseHandler): 
    def get(self):
        #if (self.get_argument('logout', None)):
        self.clear_cookie('user')
        self.redirect('/login')

class RegisterHandler(BaseHandler):
    def get(self):
        self.render('register.html')

    def post(self):
        account = self.get_argument('account')
        password = self.get_argument('password')
        email = self.get_argument('email')
        address = self.get_argument('address')
        bday = self.get_argument('bday')
        sex = self.get_argument('sex')
        if account == "" or password == "":
            self.write("账号密码不能为空")
        elif db.user.count({'account':account}) > 0:
            self.write('账号已被注册，请更换用户名')
        else:
            db.user.insert({'account':account, 'password':md5(password), 'email':email, 'address':address,
                            'bday':bday, 'sex':sex})
            self.write('{0}账号注册成功'.format(account))
            self.set_secure_cookie('user',account)
            self.redirect('/')

class UserInfoHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        users=self.get_secure_cookie('user')
        self.render('userinfo.html',**{'user':users})


class UserSelfHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        users = db.user.find()
        self.render('user_self.html',**{'users':users})

class UserListHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        follow_users = []
        for f in db.follow.find({'user':self.get_current_user()}):
            follow_users.append(f['follow_user'])
        users = db.user.find({'account':{'$ne':self.get_current_user()}})
        self.render('user_list.html',**{'users':users,'follow_users':follow_users})

class FollowHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self): 
        user = self.get_argument('follow_user',None)
        if not user:
            return self.redirect('/userlist')
        db.follow.insert({'follow_user':user,'user':self.get_current_user()})
        return self.redirect('/userlist')

    def post(self):
        user = self.get_argument('follow_user')
        db.follow.remove({'follow_user':user,'user':self.get_current_user()})
        self.redirect('/userlist')

class FollowedHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self): 
        follow_users = db.follow.find({'user':self.get_current_user()})
        self.render('follow_user_list.html',**{'follow_users':follow_users})

class AddHandler(BaseHandler):
    def post(self):
        content = self.get_argument('content')
        if content == "":
            self.write("微博内容不能为空")
        else:
            db.weibo.insert({'account':self.get_current_user(),'content':content,'td':time.time()})
            self.write('微博发布成功')
        self.redirect('/')

class WeiboListHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        #从数据库查询并按照td倒叙
        weibo = db.weibo.find({'account':{'$ne':self.get_current_user()}}).sort([("td",-1)])
        self.render("weibolist.html",**{"weibo":weibo})

class WeiboSelfHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        #从数据库查询并按照td倒叙
        weibo = db.weibo.find({'account':self.get_current_user()}).sort([("td",-1)])
        self.render("weibolist.html",**{"weibo":weibo})
    @tornado.web.authenticated
    def post(self):
        if self.get_current_user():
            weibo_id=self.get_argument('id')
            db.weibo.remove({'account':self.get_current_user(),'_id':ObjectId(weibo_id)})
            self.redirect('/weiboself')
        else:
            self.redirect('/login')

class WhoLikeMeHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        likeme = db.follow.find({'follow_user':self.get_current_user()}).sort([("td",-1)])   
        self.render("wholikeme.html",**{"likeme":likeme})

if __name__== "__main__":
    tornado.options.parse_command_line()

    settings = {"cookie_secret": "bZJc2sWbQLKos6GkHn/VB9oXwQt8S0R0kRvJ5/xJ89E=",
                'xsrf_cookies' : True,
                'template_path': os.path.join(os.path.dirname(__file__),'templates'),
                'static_path': os.path.join(os.path.dirname(__file__),'statics'),
                'static_url_prefix':'/statics/',
                'login_url': '/login',
                'debug': True}

    url = [(r'/', WelcomeHandler),
           (r'/register', RegisterHandler),
           (r'/login',LoginHandler),
           (r'/logout',LogoutHandler),
           (r'/userinfo',UserInfoHandler),
           (r'/userself',UserSelfHandler),
           (r'/userlist',UserListHandler),
           (r'/follow',FollowHandler),
           (r'/wholikeme',WhoLikeMeHandler),
           (r'/add',AddHandler),
           (r'/weibolist',WeiboListHandler),
           (r'/weiboself',WeiboSelfHandler),
            ]
    application = tornado.web.Application(url, **settings)
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()