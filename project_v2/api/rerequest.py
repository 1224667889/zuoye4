
#by mirrorlied 2020/2/24
import re


def reusername(username):
    if re.match(r"^[a-zA-Z][a-zA-Z0-9_]{4,15}$",username):#帐号字母开头，允许5-16字节，允许字母数字下划线
        return 1
    else:
        return 0

def repassword(password):
    if re.match(r"^[a-zA-Z]\w{5,17}$",password):#密码以字母开头，长度在6~18之间，只能包含字母、数字和下划线
        return 1
    else:
        return 0

