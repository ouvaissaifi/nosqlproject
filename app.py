from flask import Flask, render_template, request, session, make_response, url_for, redirect
import datetime
import uuid
import pymongo

class Database(object):
    uri = 'mongodb://127.0.0.1:27017'
    DATABASE = None

    @staticmethod
    def initialize():
        client = pymongo.MongoClient(Database.uri)
        Database.DATABASE = client['amo_blogs']

    @staticmethod
    def insert(collection, data):
        Database.DATABASE[collection].insert(data)

    @staticmethod
    def delete_one(collection, query):
        Database.DATABASE[collection].delete_one(query)

    @staticmethod
    def find(collection, query):
        return Database.DATABASE[collection].find(query)

    @staticmethod
    def find_one(collection, query):
        return Database.DATABASE[collection].find_one(query)

class Blog(object):
    def __init__(self, title, author_id, author, description, _id=None):
        self.title = title
        self.author_id = author_id
        self.author = author
        self.description = description
        self._id = uuid.uuid4().hex if _id is None else _id

    def new_post(self, title, content, date=datetime.datetime.utcnow()):
        post = Posts(title, self._id, self.author, content, created_date=date)
        post.save_to_mongo()

    def get_posts(self):
        return Posts.from_blog(self._id)

    def save_to_mongo(self):
        Database.insert(collection='blogs', data=self.json())

    def json(self):
        return {
            'title': self.title,
            'author_id': self.author_id,
            'author': self.author,
            'description': self.description,
            '_id': self._id
        }

    @classmethod
    def from_mongo(cls, _id):
        blog_data = Database.find_one(collection='blogs',
                                      query={'_id': _id})
        return cls(**blog_data)

    @classmethod
    def find_all(cls):
        user_data = Database.find('blogs', {})
        return [cls(**data) for data in user_data]

    @classmethod
    def find_by_user_id(cls, author_id):
        user_data = Database.find('blogs', {'author_id': author_id})
        return [cls(**data) for data in user_data]

    def delete_blog(self):
        Database.delete_one('blogs', {"_id": self._id})

class Posts(object):
    def __init__(self, title, blog_id, author, content, _id=None, created_date=datetime.datetime.utcnow()):
        self._id = uuid.uuid4().hex if _id is None else _id
        self.title = title
        self.blog_id = blog_id
        self.author = author
        self.content = content
        self.created_date = created_date

    def save_to_mongo(self):
        Database.insert(collection='posts', data=self.json())

    def json(self):
        return (
            {
                'blog_id': self.blog_id,
                '_id': self._id,
                'title': self.title,
                'author': self.author,
                'content': self.content,
                'created_date': self.created_date
            }
        )

    @classmethod
    def from_mongo(cls, id):
        data = Database.find_one('posts', {'_id': id})
        if data is not None:
            return cls(**data)

    @staticmethod
    def from_blog(id):
        return [post for post in Database.find(collection='posts',
                                               query={'blog_id': id})]

    def delete_post(self):
        Database.delete_one('posts', {"_id": self._id})

class User(object):
    def __init__(self, email, password, _id=None):
        self.email = email
        self.password = password
        self._id = self._id = uuid.uuid4().hex if _id is None else _id

    @classmethod
    def find_by_email(cls, email):
        data = Database.find_one('users', {'email': email})
        if data is not None:
            return cls(**data)

    @classmethod
    def find_by_id(cls, _id):
        data = Database.find_one('users', {'_id': _id})
        if data is not None:
            return cls(**data)

    @staticmethod
    def login_check(email, password):
        user = User.find_by_email(email)
        if user is not None:
            return user.password == password
        else:
            return False

    @staticmethod
    def register(email, password):
        user = User.find_by_email(email)
        if user is None:
            new_user = User(email, password)
            new_user.save_to_mongo()
            session['email'] = email
            return True
        return False

    @staticmethod
    def login(email):
        session['email'] = email

    @staticmethod
    def logout():
        session['email'] = None

    def get_blogs(self):
        return Blog.find_by_user_id(self._id)

    def new_blog(self, title, description):
        blog = Blog(title=title,
                    author_id=self._id,
                    author=self.email,
                    description=description)
        blog.save_to_mongo()

    @staticmethod
    def new_post(blog_id, title, content, date=datetime.datetime.utcnow()):
        blog = Blog.from_mongo(blog_id)
        blog.new_post(title=title,
                      content=content,
                      date=date)

    def json(self):
        return {
            'email': self.email,
            '_id': self._id,
            'password': self.password
        }

    def save_to_mongo(self):
        Database.insert(collection='users',
                        data=self.json())

app = Flask(__name__)
app.secret_key = 'amo_blogs_secrettkey'

@app.before_first_request
def initialize_database(): #initialise database
    Database.initialize()

@app.route('/')
def home():
    blogs = Blog.find_all()
    return render_template('home.html', blogs=blogs)

@app.route('/login')
def login_form():
    return render_template('login.html')

@app.route('/register')
def register_form():
    return render_template('register.html')

@app.route('/logout')
def logout():
    User.logout()
    return redirect(url_for('home'))

@app.route('/auth/register', methods=['POST'])
def register():
    email = request.form['email']
    password = request.form['password']
    User.register(email, password)
    return redirect(url_for('login_form'))

@app.route('/auth/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']
    if User.login_check(email, password):
        User.login(email=email)
        return redirect(url_for('home'))
    else:
        session['email'] = None
        return redirect(url_for('login_form'))

@app.route('/profile')
def profile():
    user = User.find_by_email(session['email'])
    blogs = user.get_blogs()
    if user is not None:
        return render_template('profile.html', blogs=blogs,
                           email=user.email)
    else:
        return redirect(url_for('home'))

@app.route('/blogs/new', methods=['POST', 'GET'])
def new_blog():
    if request.method == 'GET':
        return render_template('new_blog.html')
    else:
        title = request.form['title']
        description = request.form['description']
        user = User.find_by_email(session['email'])
        blog = Blog(title, user._id, user.email, description)
        blog.save_to_mongo()
        return redirect(url_for('profile'))

@app.route('/blogs/delete/<string:blog_id>')
def delete_blog(blog_id):
    blog = Blog.from_mongo(blog_id)
    blog.delete_blog()
    return redirect(url_for('profile'))

@app.route('/posts/<string:blog_id>')
def blog_posts(blog_id):
    blog = Blog.from_mongo(blog_id)
    posts = blog.get_posts()
    user = User.find_by_email(session['email'])
    return render_template('blog_posts.html', posts=posts,
                           title=blog.title, blog_id=blog._id,
                           current_user=user.email if user is not None else None,
                           author=blog.author)


@app.route('/posts/new/<string:blog_id>', methods=['POST', 'GET'])
def new_post(blog_id):
    if request.method == 'GET':
        return render_template('new_post.html', blog_id=blog_id)
    else:
        title = request.form['title']
        content = request.form['content']
        user = User.find_by_email(session['email'])
        post = Posts(title, blog_id, user.email, content)
        post.save_to_mongo()
        return make_response(blog_posts(blog_id))

@app.route('/posts/delete/<string:post_id>')
def delete_post(post_id):
    post = Posts.from_mongo(post_id)
    post.delete_post()
    return make_response(blog_posts(post.blog_id))

if __name__ == '__main__':
    app.run(debug=True)