class  User:
   def __init__(self, login:str, password:str, description:str,profilepic:str,posts, comments):
       self.login=login
       self.password=password
       self.description=description
       self.profilepic=profilepic
       self.posts=posts
       self.comments=comments

   def to_dict(self)->dict:
        return {'login':self.login,
                'password':self.password,
                'description':self.description,
                'profilepic':self.profilepic,
                'posts':{ '{0}'.format(i) : self.posts[i] for i in range(0, len(self.posts) ) },
                'comments':{'{0}'.format(i) : self.comments[i] for i in range(0, len(self.comments) )}
                }

class Post:
    def __init__(self,login:str,tags ,media,content:str, title:str):
        self.title=title
        self.login=login
        self.tags =tags
        self.media=media
        self.content=content

    def to_dict(self):
        return {
            'title':self.title,
            'login':self.login,
            'tags':{'{0}'.format(i) : self.tags[i] for i in range(0, len(self.tags))},
            'media':{'{0}'.format(i) : self.media[i] for i in range(0, len(self.media))},
            'content':self.content
        }


class Comment:
    def __init__(self, reply_id, media, post,content:str, login:str):
        self.login = login
        self.media=media
        self.post=post
        self.reply_id=reply_id
        self.content = content

    def to_dict(self):
        return {
            'media':{'{0}'.format(i): self.media[i] for i in range(0,len(self.media))},
            'post':self.post,
            'reply_id':self.reply_id,
            'content':self.content,
            'login':self.login
        }