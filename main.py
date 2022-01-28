from functools import wraps
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, flash, abort, Response
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar  # pip install Flask-Gravatar
import os

# ================================================================
# ================================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")  # https://dashboard.heroku.com/apps/gofuckyourselfapp/settings в разделе
# Config Vars
ckeditor = CKEditor(app)
Bootstrap(app)

# CONNECT TO DB
# "DATABASE_URL" environment variable if provided, but if it's None (e.g. when running locally) then we can provide sqlite:///blog.db as the alternative.
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL",  "sqlite:///blog.db")  # DATABASE_URL
# https://dashboard.heroku.com/apps/gofuckyourselfapp/settings в разделе Config Vars
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)

gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def admin_only(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            # return abort(403)
            return abort(Response('Please Log In'))
        elif current_user.id != 1:
            # return abort(403)
            return abort(Response('Admin Only!'))

        return f(*args, **kwargs)

    return wrapper


# CONFIGURE TABLES


class User(UserMixin, db.Model):  # PARENT for BlogPost and Comment
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(100))

    # ************************************
    # *********PARENT for BlogPost********
    # This will act like a List of BlogPost objects attached to each User.
    # The "author" refers to the author property in the BlogPost class.
    posts = relationship("BlogPost", back_populates="author")  # Через posts можно получить все посты юзера, например,
    # current_user.posts даст лист из объектов [<BlogPost 1>, <BlogPost 2>], а уже через каждый объект можно получить
    # доступ к данным каждого поста, например, current_user.posts[0].title даст title первого поста в
    # листе (в данном случае "Title Пост 1"), созданый юзером sasha (см. скрин db в evernote).

    # ************************************
    # *********PARENT for Comment*********
    # "comment_author" refers to the comment_author property in the Comment class.
    comments = relationship("Comment", back_populates="comment_author")


class BlogPost(db.Model):  # CHILD for User, PARENT for Comment
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)

    # =================================================================================
    # =================================================================================
    # *********CHILD for User*********
    # Create Foreign Key, "users.id" the users refers to the tablename of User.
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))  # Это в базе будет id создателя блогпоста.

    # Create reference to the User object, the "posts" refers to the posts property in the User class.
    author = relationship("User", back_populates="posts")  # сюда прилетит current_user из add_new_post(), а затем выше
    # в колонку author_id запишется полученный users.id, который возьмется из current_user.
    # Через author можно будет связться с юзером, создавшим пост, например, чтобы получить имя создателя поста, в post.html надо прописать post.author.name

    # =================================================================================
    # =================================================================================
    # *********PARENT for Comment*********
    comments = relationship("Comment", back_populates="parent_post")
    # =================================================================================
    # =================================================================================

    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)


class Comment(db.Model):  # CHILD for User and BlogPost
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)

    # ******************************
    # ********CHILD for User********
    # "users.id" The users refers to the tablename of the Users class.
    # "comments" refers to the comments property in the User class.
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    comment_author = relationship("User", back_populates="comments")  # сюда прилетит current_user из show_post(post_id),
    # а затем выше в колонку author_id запишется полученный users.id, который возьмется из current_user.

    # ******************************
    # ******CHILD for BlogPost******
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates="comments")  # сюда прилетит requested_post из show_post(post_id),
    # а затем выше в колонку post_id запишется полученный blog_posts.id, который возьмется из requested_post.


# # Create all the tables in the database
db.create_all()


# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# Для проверки зареган юзер или нет, чтобы не отображать кнопки в хедере логин и регистрация.
# Every time you call render_template(), you pass the current_user over to the template.
# current_user.is_authenticated will be True if they are logged in/authenticated after registering.
# You can check for this is header.html !!!!! Оказалось, что передавать current_user не обязателдьно работает и без него.


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts, current_user=current_user)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            # User already exists
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))

        hash_and_salted_password = generate_password_hash(form.password.data, method='pbkdf2:sha256', salt_length=8)
        new_user = User(
            email=form.email.data,
            password=hash_and_salted_password,
            name=form.name.data
        )
        db.session.add(new_user)
        db.session.commit()

        # This line will authenticate the user with Flask-Login
        login_user(new_user)
        return redirect(url_for("get_all_posts"))

    return render_template("register.html", form=form, current_user=current_user)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        # Find user by email entered.
        user = User.query.filter_by(email=email).first()

        # Check stored password hash against entered password hashed.
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("get_all_posts"))
        else:  # Password incorrect
            flash("Incorrect email or password")
            return redirect(url_for('login'))

    return render_template("login.html", form=form, current_user=current_user)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=['GET', 'POST'])
def show_post(post_id):
    form = CommentForm()
    requested_post = BlogPost.query.get(post_id)

    if form.validate_on_submit():
        if current_user.is_authenticated:
            new_comment = Comment(
                text=form.comment_text.data,
                comment_author=current_user,  # Запонится как ID текущего юзера (см. )
                parent_post=requested_post  # Запонится как ID текущего блогпоста
            )
            db.session.add(new_comment)
            db.session.commit()
            return redirect(url_for("show_post", post_id=post_id))
        else:  # юзер не залогинился, чтобы писать комменты
            flash("Log in first")
            return redirect(url_for('login'))

    return render_template("post.html", post=requested_post, form=form, gravatar=gravatar, current_user=current_user)


@app.route("/about")
def about():
    return render_template("about.html", current_user=current_user)


@app.route("/contact")
def contact():
    return render_template("contact.html", current_user=current_user)


@app.route("/new-post", methods=['GET', 'POST'])
@admin_only
def add_new_post():
    form = CreatePostForm()
    today = datetime.now().strftime('%B %d, %Y')

    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            img_url=form.img_url.data,
            author=current_user,  # Запонится, как ID текущего юзера в таблицу blog_posts в колонку author_id,
            # колонки author нету - это relationship (см. BlogPost)  !!!!!!!!!!!!!!!!!!!!!!!!
            body=form.body.data,
            date=today
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))

    return render_template("make-post.html", form=form, current_user=current_user)


@app.route("/edit-post/<int:post_id>", methods=['GET', 'POST'])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)  # 1. Получение поста для заполнения формы для редактирования.
    edit_form = CreatePostForm(  # 2. Заполнение формы данными редактитруемого поста
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form, is_edit=True, current_user=current_user)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == '__main__':
    app.run(debug=True)
