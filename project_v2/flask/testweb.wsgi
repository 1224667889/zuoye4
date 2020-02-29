import sys

#app's path
sys.path.insert(0,"C:/Users/Administrator/Desktop/project/flask")

from testweb import app

#Initialize WSGI app object
application = app
