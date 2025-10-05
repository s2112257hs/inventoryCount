import os
from flask import Flask, request, redirect, url_for, session, render_template
from supabase import create_client, Client
from flask_session import Session
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_secret_key')
app.config['PORT'] = int(os.environ.get('PORT', 5000))
Session(app)

# Initialize Supabase client
supabase: Client = create_client(os.environ.get('SUPABASE_URL'), os.environ.get('SUPABASE_KEY'))
print("Templates folder:", app.template_folder)
def require_auth(f):
    def decorated(*args, **kwargs):
        if 'user' not in session:
            next_url = request.url
            return redirect(url_for('login', next=next_url))
        try:
            supabase.auth.get_user(session.get('access_token'))
        except Exception as e:
            print(f"Token validation error: {str(e)}")
            if 'refresh_token' in session:
                try:
                    response = supabase.auth.refresh_session(session['refresh_token'])
                    if response.session:
                        session['access_token'] = response.session.access_token
                        session['refresh_token'] = response.session.refresh_token
                        supabase.postgrest.auth(response.session.access_token)
                    else:
                        session.pop('user', None)
                        session.pop('access_token', None)
                        session.pop('refresh_token', None)
                        return redirect(url_for('login', next=request.url))
                except Exception as e:
                    print(f"Token refresh error: {str(e)}")
                    session.pop('user', None)
                    session.pop('access_token', None)
                    session.pop('refresh_token', None)
                    return redirect(url_for('login', next=request.url))
            else:
                session.pop('user', None)
                session.pop('access_token', None)
                return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    decorated.__name__ = f.__name__
    return decorated

@app.route('/login', methods=['GET', 'POST'])
def login():
    next_url = request.args.get('next', url_for('photo', id='default'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        try:
            response = supabase.auth.sign_in_with_password({'email': email, 'password': password})
            if response.user:
                session['user'] = response.user.id
                session['access_token'] = response.session.access_token
                session['refresh_token'] = response.session.refresh_token
                session.permanent = True
                supabase.postgrest.auth(response.session.access_token)
                return redirect(next_url)
            else:
                return render_template("login.html", error="Invalid credentials. Please try again.", next=next_url)
        except Exception as e:
            print(f"Login error: {str(e)}")
            return render_template("login.html", error=f"Login failed: {str(e)}. Please try again.", next=next_url)
    return render_template("login.html", error=None, next=next_url)

@app.route('/logout')
def logout():
    next_url = request.args.get('next', url_for('login'))
    session.pop('user', None)
    session.pop('access_token', None)
    session.pop('refresh_token', None)
    supabase.auth.sign_out()
    return redirect(next_url)

@app.route('/photo/<id>')
@require_auth
def photo(id):
    file_path = f"Uploads/{id}.jpg"
    bucket_name = 'photos'
    try:
        files = supabase.storage.from_(bucket_name).list(path="Uploads")
        file_exists = any(file['name'] == f"{id}.jpg" for file in files)
        
        if file_exists:
            image_url = supabase.storage.from_(bucket_name).get_public_url(file_path)
            return render_template("view.html", id=id, image_url=image_url, error=None)
        else:
            return render_template("upload.html", id=id, error=None)
    except Exception as e:
        print(f"Error checking file: {str(e)}")
        return render_template("upload.html", id=id, error="Failed to check for existing photo. Please try uploading.")

@app.route('/upload/<id>', methods=['POST'])
@require_auth
def upload(id):
    if 'photo' not in request.files:
        return render_template("upload.html", id=id, error="No photo uploaded. Please select a file and try again.")
    
    photo = request.files['photo']
    if photo.filename == '':
        return render_template("upload.html", id=id, error="No file selected. Please select a file and try again.")
    
    if photo:
        try:
            print("Received file:", photo.filename, photo.content_type)
            file_path = f"Uploads/{id}.jpg"
            bucket_name = 'photos'

            if not photo.content_type.startswith('image/'):
                return render_template("upload.html", id=id, error="Only image files are allowed. Please select an image and try again.")

            file_content = photo.read()
            if len(file_content) > 2 * 1024 * 1024:
                return render_template("upload.html", id=id, error="File too large. Maximum size is 2MB. Please select a smaller file and try again.")

            print("Uploading to path:", file_path)
            response = supabase.storage.from_(bucket_name).upload(
                file_path,
                file_content,
                {
                    'content-type': photo.content_type,
                    'upsert': 'true'
                }
            )

            print("Upload response:", response)
            if hasattr(response, 'path') and response.path == file_path:
                print("Upload successful, redirecting to /photo/", id)
                return redirect(url_for('photo', id=id))
            else:
                error_message = "Upload failed: Unknown error. Please try uploading again."
                if hasattr(response, 'error') and response.error:
                    error_message = f"Upload failed: {response.error}. Please try uploading again."
                if "row-level security" in str(response).lower():
                    error_message = "Upload failed due to storage permission settings. Please try uploading again or contact support."
                print("Upload failed:", error_message)
                return render_template("upload.html", id=id, error=error_message)

        except Exception as e:
            print(f"Supabase error: {str(e)}")
            error_message = f"Error uploading to Supabase: {str(e)}. Please try uploading again."
            if "row-level security" in str(e).lower():
                error_message = "Upload failed due to storage permission settings. Please try uploading again or contact support."
            return render_template("upload.html", id=id, error=error_message)

@app.route('/delete/<id>', methods=['POST'])
@require_auth
def delete_photo(id):
    file_path = f"Uploads/{id}.jpg"
    bucket_name = 'photos'
    try:
        supabase.storage.from_(bucket_name).remove([file_path])
        print(f"Deleted photo: {file_path}")
        return redirect(url_for('photo', id=id))
    except Exception as e:
        print(f"Delete error: {str(e)}")
        error_message = f"Error deleting photo: {str(e)}. Please try again."
        if "row-level security" in str(e).lower():
            error_message = "Delete failed due to storage permission settings. Please try again or contact support."
        return render_template("view.html", id=id, image_url=supabase.storage.from_(bucket_name).get_public_url(file_path), error=error_message)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=app.config['PORT'], debug=False)